"""Diagnose WHY the script step stopped working, without paying for a 2-hour build.

Written 2026-09-05 after glm-5p2 failed four consecutive fresh generations across ~8
hours at both 25 and 35 target pages, while status.fireworks.ai reported every system
operational. Two failure signatures were seen and they look different but are the same
thing -- the server accepts the request and never produces output:

  * RemoteDisconnected at ~5m04-5m13s  (the 35pp runs)
  * a silent read timeout at the full 900s  (the 25pp run)

The build logs cannot separate the candidate causes, because every observation costs a
paid ~2h run and changes two variables at once. This does it in about two minutes:

  A  tiny non-streaming    -- is the deployment alive AT ALL?
  B  medium non-streaming  -- does a normal-sized answer come back?
  C  large non-streaming   -- reproduce the failure at real script size
  D  large STREAMING       -- the same request with stream=true

D is the one that matters. If C hangs and D succeeds, the cause is a non-streaming
response-time limit somewhere between us and the model, and the fix is to stream --
not to shrink the book, change model, or change provider. If D also hangs, the
deployment itself cannot serve this workload and no client-side change will help.

Read every result before concluding: A failing means nothing below it is informative.
"""
import json
import os
import sys
import time

import requests

BASE = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = os.environ.get("COMIC_LLM_MODEL") or "accounts/fireworks/models/glm-5p2"
KEY = os.environ.get("FIREWORKS_API_KEY")

# Roughly the shape of the real script call: a long system prompt and a request for a
# large structured answer. Not the real prompt -- the point is size and output length,
# and a synthetic one keeps this reproducible when the real prompt changes.
BIG_SYSTEM = (
    "You write true-crime documentary comic scripts. Output strict JSON only, no "
    "markdown fences and no commentary. " + ("Follow the house style closely. " * 200)
)
BIG_USER = (
    "Write a comic script as JSON: {\"script\": [{\"page\": 1, \"panels\": "
    "[{\"art\": \"...\", \"caption\": \"...\"}]}]}. Produce 35 pages, roughly 5 "
    "panels per page, each panel with a detailed art description and a caption. "
    "Do not stop early; produce all 35 pages."
)


def _post(payload, read_timeout, stream=False):
    return requests.post(
        BASE,
        headers={"Authorization": f"Bearer {KEY}", "content-type": "application/json"},
        json=payload, timeout=(30, read_timeout), stream=stream)


def run(label, *, max_tokens, system, user, read_timeout, stream):
    """One probe. Never raises -- a probe that dies must still report, or the run tells
    us nothing about the probes after it."""
    payload = {"model": MODEL, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "reasoning_effort": "low"}
    if stream:
        payload["stream"] = True

    print(f"\n=== {label} ===", flush=True)
    print(f"    max_tokens={max_tokens:,} stream={stream} read_timeout={read_timeout}s",
          flush=True)
    t0 = time.time()
    try:
        r = _post(payload, read_timeout, stream=stream)
        if r.status_code >= 400:
            print(f"    HTTP {r.status_code} after {time.time()-t0:.1f}s: {r.text[:300]}",
                  flush=True)
            return
        if not stream:
            data = r.json()
            el = time.time() - t0
            txt = (data.get("choices", [{}])[0].get("message", {}).get("content") or "")
            fin = data.get("choices", [{}])[0].get("finish_reason")
            print(f"    OK in {el:.1f}s -- {len(txt):,} chars, finish_reason={fin}",
                  flush=True)
            return

        # Streaming: time-to-first-byte is the whole point. A non-streaming request
        # sends nothing until the answer is complete, which is exactly the silence that
        # an intermediary kills; streaming should produce a chunk within seconds.
        first = None
        chunks = chars = 0
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            body = line[6:]
            if body.strip() == "[DONE]":
                break
            if first is None:
                first = time.time() - t0
                print(f"    first byte at {first:.1f}s", flush=True)
            chunks += 1
            try:
                d = json.loads(body)
                chars += len(d["choices"][0].get("delta", {}).get("content") or "")
            except Exception:
                pass
        el = time.time() - t0
        print(f"    OK in {el:.1f}s -- {chunks:,} chunks, {chars:,} chars, "
              f"ttfb={first if first is None else round(first,1)}s", flush=True)
    except Exception as exc:
        print(f"    FAILED after {time.time()-t0:.1f}s: {type(exc).__name__}: "
              f"{str(exc)[:300]}", flush=True)


def main():
    if not KEY:
        sys.exit("FIREWORKS_API_KEY is not set")
    print(f"model: {MODEL}", flush=True)

    # Does the account see the model at all? A 404/permission problem here would explain
    # everything downstream and costs one cheap GET to rule out.
    try:
        t0 = time.time()
        r = requests.get("https://api.fireworks.ai/inference/v1/models",
                         headers={"Authorization": f"Bearer {KEY}"}, timeout=(30, 60))
        ids = [m.get("id") for m in (r.json().get("data") or [])] if r.ok else []
        print(f"models endpoint: HTTP {r.status_code} in {time.time()-t0:.1f}s, "
              f"{len(ids)} models; target listed: {MODEL in ids}", flush=True)
    except Exception as exc:
        print(f"models endpoint FAILED: {type(exc).__name__}: {str(exc)[:200]}", flush=True)

    run("A  tiny, non-streaming", max_tokens=50, system="Answer in one word.",
        user="Say hi.", read_timeout=120, stream=False)
    run("B  medium, non-streaming", max_tokens=8000,
        system="You write clearly.",
        user="Write about 1500 words on the history of forensic fingerprinting.",
        read_timeout=600, stream=False)
    run("C  large, non-streaming (reproduces the build failure)", max_tokens=64000,
        system=BIG_SYSTEM, user=BIG_USER, read_timeout=600, stream=False)
    run("D  large, STREAMING (the candidate fix)", max_tokens=64000,
        system=BIG_SYSTEM, user=BIG_USER, read_timeout=600, stream=True)

    # E exercises llm.py ITSELF, not a hand-rolled request. D proving that raw SSE works
    # says nothing about whether our stream reader reassembles it correctly -- and a
    # reassembly bug would surface as corrupt JSON two hours into a paid build.
    print("\n=== E  llm.py end-to-end (real SSE through _read_stream) ===", flush=True)
    try:
        import llm as _llm
        c = _llm.LLM(provider="fireworks", max_retries=1,
                     model=MODEL if MODEL else None)
        t0 = time.time()
        got = c.text("Write about 1200 words on the history of forensic fingerprinting.",
                     system="You write clearly.", max_tokens=8000)
        print(f"    OK in {time.time()-t0:.1f}s -- {len(got):,} chars, "
              f"stream={c.stream}", flush=True)
        print(f"    head: {got[:120]!r}", flush=True)
        if not got.strip():
            print("    !! EMPTY -- the stream reader is not assembling content", flush=True)
    except Exception as exc:
        print(f"    FAILED: {type(exc).__name__}: {str(exc)[:300]}", flush=True)

    print("\nRead A first: if A failed, nothing below it is informative.", flush=True)


if __name__ == "__main__":
    main()
