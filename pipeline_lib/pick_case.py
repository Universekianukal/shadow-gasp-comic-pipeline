"""Pick the next true-crime / dark-history case to turn into a comic,
deduped against cases_used.json (the ledger of all 74 shorts + any comics
already produced).

Uses the Anthropic API to propose candidates (no web browsing available here,
so it draws on the model's own knowledge — same constraint that applies to
Claude writing this manually, made explicit in the prompt so it only proposes
well-documented cases it's confident about).
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LEDGER_PATH = os.path.join(REPO_ROOT, "cases_used.json")

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-5"


def load_ledger():
    if not os.path.exists(LEDGER_PATH):
        return {"cases": []}
    with open(LEDGER_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_ledger(ledger):
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)


def call_claude(system, user, max_tokens=2000):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode(),
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {e.read().decode()}") from e
    if "content" not in data:
        raise RuntimeError(f"Unexpected Anthropic API response: {json.dumps(data)[:1000]}")
    return data["content"][0]["text"]


def main():
    ledger = load_ledger()
    used_cases = [c["case"] for c in ledger["cases"]]

    system = (
        "You pick the next true-crime or dark-history case for a documentary "
        "comic series (SHADOW GASP). Only propose real, well-documented cases "
        "you have high confidence about — enough public detail exists to write "
        "25+ genuinely substantive comic pages without inventing facts. Never "
        "propose a case that's a near-duplicate of one already used."
    )
    user = (
        "Already-used cases (do not repeat or closely duplicate any of these):\n"
        + "\n".join(f"- {c}" for c in used_cases)
        + "\n\nPropose exactly 3 new candidate cases, ranked best-first. "
        "For each, give: case name, one-sentence hook, and a rough confidence "
        "(high/medium) that enough real detail exists for 25+ pages. "
        "Respond as JSON: {\"candidates\": [{\"case\": ..., \"hook\": ..., \"confidence\": ...}]}"
    )

    text = call_claude(system, user)
    start, end = text.find("{"), text.rfind("}") + 1
    result = json.loads(text[start:end])

    candidates = [c for c in result["candidates"] if c["confidence"] == "high"] or result["candidates"]
    chosen = candidates[0]

    ledger["cases"].append({
        "videoId": None,
        "case": chosen["case"],
        "publishedAt": None,
        "source": "auto-picked",
    })
    save_ledger(ledger)

    print(json.dumps(chosen, indent=2))
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"case={chosen['case']}\n")
        f.write(f"hook={chosen['hook']}\n")


if __name__ == "__main__":
    main()
