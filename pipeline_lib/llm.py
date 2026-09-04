"""Swappable LLM adapter.

The provider is a config value, not a hardcoded import, so the design model can be
chosen (or changed) without touching any pipeline stage. Providers:

  auto       - pick the first provider whose key is present; falls back to mock
  anthropic  - needs ANTHROPIC_API_KEY
  fireworks  - needs FIREWORKS_API_KEY. OpenAI-compatible, so it reuses that
               transport, and far cheaper per project than the frontier APIs.
  openai     - needs OPENAI_API_KEY
  mock       - deterministic placeholder design, no network, no cost

`mock` exists so the full build (validation + diagrams + PDF + Telegram) can be
exercised end to end for free. Every pipeline stage must work under `mock`, which is
also how the scheduled workflow is smoke-tested without spending on tokens.

`auto` exists because the opposite happened: the only scheduled run this project ever
made failed outright with "ANTHROPIC_API_KEY is not set". A missing key should degrade
the run, not delete it.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
import time
from dataclasses import dataclass

import requests

# provider -> (base_url, api_key_env, default_model)
OPENAI_COMPATIBLE = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o"),
    # glm-5p2 was chosen by comparison on a real brief, not by reputation: kimi-k3 and
    # deepseek-v4-pro leaked their reasoning scratchpad into the output and qwen3p8-max
    # returned nothing within the budget. Catalogues move - check with
    # `python -m maker.llm list-models fireworks` before switching.
    "fireworks": ("https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY",
                  "accounts/fireworks/models/glm-5p2"),
}

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    **{p: m for p, (_, _, m) in OPENAI_COMPATIBLE.items()},
}

PROVIDERS = ("anthropic", "mock", *OPENAI_COMPATIBLE)

# Order matters: the most capable key wins when several are present.
AUTO_ORDER = ("anthropic", "fireworks", "openai")


class LLMError(RuntimeError):
    pass


class Truncated(LLMError):
    """Output stopped at the token limit, so the result is incomplete.

    Distinct from a plain LLMError because it is recoverable: the same call with a
    larger budget usually succeeds. It must never be swallowed - a truncated design
    parses as valid JSON right up to the point it stops.
    """


def resolve_provider(provider: str, *, verbose: bool = True) -> str:
    """Turn `auto` into a provider that can actually run."""
    if provider and provider != "auto":
        return provider
    for name in AUTO_ORDER:
        env = "ANTHROPIC_API_KEY" if name == "anthropic" else OPENAI_COMPATIBLE[name][1]
        if os.environ.get(env):
            if verbose:
                print(f"provider: {name} (auto, {env} present)", flush=True)
            return name
    if verbose:
        print("provider: mock (auto, no LLM key found)", flush=True)
    return "mock"


@dataclass
class LLM:
    provider: str = "mock"
    model: str | None = None
    max_retries: int = 4
    # Current reasoning models will happily think past any budget you give them: on the
    # real netlist prompt glm-5p2 produced 102,699 characters of reasoning and STILL
    # returned no content at a 32,000-token cap. Capping the effort is what makes the
    # call terminate. Design quality is protected by the netlist validator and its
    # repair rounds, not by how long the model deliberates - and a design that never
    # arrives cannot be repaired.
    reasoning_effort: str | None = "low"

    # Absolute ceiling for the automatic budget escalation below.
    MAX_OUTPUT_TOKENS = 64000

    def __post_init__(self) -> None:
        self.provider = resolve_provider((self.provider or "mock").lower(),
                                         verbose=False)
        if self.provider not in PROVIDERS:
            raise LLMError(f"unknown provider {self.provider!r}; "
                           f"choose from {', '.join(PROVIDERS)}")
        self.model = (self.model
                      or os.environ.get(f"{self.provider.upper()}_MODEL")
                      or DEFAULT_MODELS.get(self.provider))

    # -- public ---------------------------------------------------------------

    def text(self, prompt: str, *, system: str = "", max_tokens: int = 4000) -> str:
        """Return a completion, growing the budget if the output was truncated.

        How much budget a request needs is not knowable up front: it depends on how
        long the model chooses to think, which varies per prompt. Start at the
        caller's estimate and double on truncation rather than guessing a multiplier
        that is wasteful for most calls and still too small for some.
        """
        if self.provider == "mock":
            return _mock_text(prompt, max_tokens)

        budget = max_tokens
        for attempt in range(3):
            try:
                return self._retry(lambda: self._call(prompt, system, budget))
            except Truncated:
                if budget >= self.MAX_OUTPUT_TOKENS or attempt == 2:
                    raise
                budget = min(budget * 2, self.MAX_OUTPUT_TOKENS)
                print(f"  . output truncated, retrying with max_tokens={budget:,}",
                      flush=True)
        raise Truncated("exhausted budget escalation")

    def json(self, prompt: str, *, system: str = "", max_tokens: int = 4000,
             shape: dict | list | None = None) -> dict | list:
        """Return parsed JSON, re-prompting once if the model emits prose around it."""
        if self.provider == "mock":
            return _mock_json(prompt, shape)
        system = (system + "\n\nRespond with valid JSON only. No markdown fences, "
                  "no commentary before or after.").strip()
        raw = self.text(prompt, system=system, max_tokens=max_tokens)
        try:
            return _loads_loose(raw)
        except ValueError:
            fixed = self.text(
                "The following was meant to be JSON but will not parse. "
                "Return only the corrected JSON:\n\n" + raw,
                system=system, max_tokens=max_tokens)
            return _loads_loose(fixed)

    # -- transport ------------------------------------------------------------

    def _retry(self, fn):
        # ⚠️ A DROPPED CONNECTION IS NOT A FAILED GENERATION.
        #
        # Callers set max_retries=1 on purpose: every attempt is a full paid generation of a
        # 50-page book, and nesting this loop inside gen_case_script's own once cost 12 attempts
        # and ~2 hours. But that also meant a connection the server closed BEFORE producing
        # anything got no retry at all -- it cost nothing to redo, and was treated as gravely as
        # a model that answered badly. On 2026-09-04 that turned one dropped socket into a dead
        # build.
        #
        # So transport failures that cannot have consumed a generation get their own small
        # allowance, independent of max_retries. A read timeout is deliberately NOT in this set:
        # the model may well have been mid-answer, so retrying it does cost real money.
        cheap = (requests.exceptions.ConnectionError,
                 requests.exceptions.ChunkedEncodingError)
        attempts = max(self.max_retries, 3)
        delay = 2.0
        last = None
        for attempt in range(attempts):
            try:
                return fn()
            except LLMError:
                raise
            except Exception as exc:  # network / 429 / 5xx
                last = exc
                spent = attempt + 1
                # Past the caller's budget, only a free-to-retry transport error may continue.
                if spent >= self.max_retries and not isinstance(exc, cheap):
                    break
                if spent >= attempts:
                    break
                print(f"  . {type(exc).__name__} on attempt {spent}/{attempts}, retrying in "
                      f"{delay:.0f}s", flush=True)
                time.sleep(delay)
                delay *= 2
        raise LLMError(f"LLM call failed after {self.max_retries} attempts: {last}")

    def _call(self, prompt: str, system: str, max_tokens: int) -> str:
        if self.provider == "anthropic":
            key = _require_key("ANTHROPIC_API_KEY")
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": max_tokens,
                      "system": system or None,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=300)
            _raise_for_status(r)
            return "".join(b.get("text", "") for b in r.json()["content"])

        # Everything else speaks the OpenAI chat-completions dialect.
        base, key_env, _ = OPENAI_COMPATIBLE[self.provider]
        key = _require_key(key_env)
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        payload = {"model": self.model, "max_tokens": max_tokens, "messages": msgs}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        r = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}",
                     "content-type": "application/json"},
            # 600s was not enough for a 150-panel comic script: CI hit a read timeout on every
            # attempt while the same call finished locally in under 20 minutes.
            #
            # ⚠️ SPLIT, not one number. A single 1800s value has to cover both "how long may the
            # model take to answer" and "how long do we wait to find out the server is gone" --
            # and the second question needs a far smaller answer. On 2026-09-04 Fireworks dropped
            # one connection and then stalled: the run sat 30 minutes on a dead socket, burned
            # the outer 2-attempt budget, and produced nothing in 36 minutes of runner time.
            #
            # (connect, read): a connection that will not open in 30s is not opening. The read
            # budget stays generous because a real 50-page generation legitimately takes many
            # minutes -- but it is the STREAM-IDLE gap that matters, not total call duration, so
            # a server that goes silent is now detected in minutes rather than half an hour.
            json=payload, timeout=(30, 900))
        _raise_for_status(r)
        data = r.json()
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError):
            raise LLMError(f"{self.provider} returned no completion. "
                           f"Response: {str(data)[:400]}") from None

        # Reasoning models spend the budget thinking before they write, and put that
        # thinking in a separate field while still billing it against max_tokens. If
        # the budget runs out first, `content` comes back empty or cut short - which
        # would otherwise reach the netlist validator as a malformed design.
        reasoning = choice["message"].get("reasoning_content") or ""
        finish = choice.get("finish_reason")

        if not content.strip():
            # Empty output that stopped at the limit is the MOST recoverable form of
            # truncation, not a fatal error: the model thought until the budget was
            # gone and never got to the answer. Classifying it as fatal is what stops
            # the escalation above from ever firing for the worst case of the exact
            # problem it exists to solve.
            if finish == "length":
                raise Truncated(
                    f"{self.model} spent its entire {max_tokens:,}-token budget on "
                    f"reasoning ({len(reasoning)} chars) and returned no content.")
            hint = (f" It produced {len(reasoning)} chars of reasoning; raise "
                    "max_tokens or pick a non-reasoning model." if reasoning else "")
            raise LLMError(
                f"{self.model} returned empty content (finish_reason={finish!r}).{hint}")

        if finish == "length":
            raise Truncated(
                f"{self.model} hit the token limit mid-output, so this text is "
                f"truncated. Raise max_tokens"
                + (" - a reasoning model needs headroom for thinking on top of the "
                   "answer itself." if reasoning else "."))

        return content


def _require_key(name: str) -> str:
    key = os.environ.get(name)
    if not key:
        raise LLMError(
            f"{name} is not set. Export it, or run with --provider mock for a free dry run.")
    return key


def _raise_for_status(r: requests.Response) -> None:
    if r.status_code >= 400:
        # 4xx other than 429 will not improve on retry - fail loudly and immediately.
        detail = r.text[:500]
        if 400 <= r.status_code < 500 and r.status_code != 429:
            raise LLMError(f"HTTP {r.status_code}: {detail}")
        raise RuntimeError(f"HTTP {r.status_code}: {detail}")


def _loads_loose(raw: str) -> dict | list:
    """Parse JSON that may be wrapped in ``` fences or trailing prose."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost brace/bracket span.
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = s.find(open_c), s.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"could not parse JSON from: {raw[:300]}")


# -- mock provider ------------------------------------------------------------

_LOREM = (
    "The distinction matters more than it first appears. When people describe this problem "
    "they tend to reach for the nearest explanation, and the nearest explanation is almost "
    "always the one that costs them the least to believe. That is the trap. What follows is "
    "the less comfortable reading, and the one that actually predicts what happens next. "
)


def _mock_text(prompt: str, max_tokens: int) -> str:
    """Deterministic filler sized roughly to the token budget."""
    seed = hashlib.sha256(prompt.encode()).hexdigest()[:8]
    words = max(120, int(max_tokens * 0.6))
    body = (_LOREM * ((words // 60) + 1))
    paras = textwrap.wrap(body, 520)[: max(3, words // 90)]
    return f"[mock:{seed}]\n\n" + "\n\n".join(paras)


def _mock_json(prompt: str, shape: dict | list | None):
    """Return the caller-declared shape so downstream stages get real structure."""
    if shape is not None:
        return shape
    return {"mock": True}


# -- CLI ----------------------------------------------------------------------

def list_models(provider: str) -> list[str]:
    """Ask the provider what this account can actually reach.

    Worth running before a scheduled build: a retired model id fails the run after the
    prompt has already been billed, and catalogues change faster than defaults do.
    """
    if provider not in OPENAI_COMPATIBLE:
        raise LLMError(f"list-models supports {', '.join(OPENAI_COMPATIBLE)}")
    base, key_env, _ = OPENAI_COMPATIBLE[provider]
    r = requests.get(f"{base}/models",
                     headers={"Authorization": f"Bearer {_require_key(key_env)}"},
                     timeout=60)
    _raise_for_status(r)
    return sorted(m.get("id", "") for m in r.json().get("data", []))


def _main(argv: list[str]) -> int:
    import sys

    if len(argv) >= 2 and argv[1] == "list-models":
        for mid in list_models(argv[2] if len(argv) > 2 else "fireworks"):
            print(mid)
        return 0

    if len(argv) >= 2 and argv[1] == "test":
        llm = LLM(provider=argv[2] if len(argv) > 2 else "fireworks",
                  model=argv[3] if len(argv) > 3 else None)
        print(f"provider={llm.provider} model={llm.model}")
        print("---")
        print(llm.text("Name three components in a simple LED torch circuit. "
                       "No preamble.", max_tokens=2000).strip()[:600])
        return 0

    print("usage:\n"
          "  python -m maker.llm list-models [provider]\n"
          "  python -m maker.llm test [provider] [model]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import sys

    try:
        raise SystemExit(_main(sys.argv))
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
