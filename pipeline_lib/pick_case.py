"""Pick the next true-crime / dark-history case to turn into a comic.

Two sources, chosen with --source:

  published (DEFAULT) -- a case that ALREADY has a short published on YouTube and does not yet
      have a comic. This is the sales path: the short is the advertisement, the comic is the
      product, and the audience that watched the short is the audience being sold to. Costs no
      Anthropic call at all -- it is a lookup over cases_used.json, not a generation.

  new -- ask Claude for a case the channel has never covered in any form. This was the original
      (and previously the only) behaviour. It is the opposite of the sales path: it deliberately
      excludes every published short, so the resulting comic has no existing audience.

The default is `published` because a comic on a case nobody has seen has to build its own
demand from zero -- the same thing that left the KDP catalogue at zero sales.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LEDGER_PATH = os.path.join(REPO_ROOT, "cases_used.json")

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
    # Read lazily, not at import: --source published makes no API call at all and must run
    # without the key present.
    api_key = os.environ["ANTHROPIC_API_KEY"]
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode(),
        headers={
            "x-api-key": api_key,
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
    for block in data["content"]:
        if block.get("type") == "text":
            return block["text"]
    raise RuntimeError(f"No text block in Anthropic API response: {json.dumps(data)[:1000]}")


def emit(case, hook, video_id=""):
    print(json.dumps({"case": case, "hook": hook, "videoId": video_id}, indent=2))
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"case={case}\n")
        f.write(f"hook={hook}\n")
        # Carried so the comic can be cross-linked back to the short it came from -- the short
        # is the only place this comic has a ready-made audience.
        f.write(f"video_id={video_id}\n")


def pick_published(ledger, order):
    """Next case that has a published short but no comic yet. No API call."""
    candidates = [c for c in ledger["cases"] if c.get("videoId") and not c.get("comicAt")]
    if not candidates:
        total = sum(1 for c in ledger["cases"] if c.get("videoId"))
        sys.exit(
            f"No published short is left without a comic (all {total} are done).\n"
            "Either name a case explicitly, or re-run with --source new to have Claude "
            "propose a case the channel has never covered."
        )
    # publishedAt is an ISO string, so a plain sort is chronological. Oldest first: those shorts
    # have had the longest to accumulate an audience. There is no view data in this ledger, so
    # this is a proxy for reach, not a measurement of it -- rank by actual views if that ever
    # gets wired in.
    candidates.sort(key=lambda c: c.get("publishedAt") or "", reverse=(order == "newest"))
    chosen = candidates[0]

    # Mark the EXISTING entry rather than appending a new one. Appending would put the same case
    # in the ledger twice, and the `new` source treats every entry as already-used -- so a
    # duplicate would silently shrink the pool it picks from.
    chosen["comicAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_ledger(ledger)

    remaining = len(candidates) - 1
    print(
        f"Source: published short -> comic. {remaining} published shorts still have no comic.",
        flush=True,
    )
    hook = f"Comic companion to the published short ({chosen['videoId']})."
    emit(chosen["case"], hook, chosen["videoId"])


def pick_new(ledger):
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
        "comicAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    save_ledger(ledger)

    print("Source: newly proposed case (no published short, no existing audience).", flush=True)
    emit(chosen["case"], chosen["hook"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["published", "new"], default="published",
                    help="published: a case whose short is already on YouTube and has no comic "
                         "yet (default). new: ask Claude for a case never covered at all.")
    ap.add_argument("--order", choices=["oldest", "newest"], default="oldest",
                    help="For --source published: which end of the back catalogue to work from.")
    args = ap.parse_args()

    ledger = load_ledger()
    if args.source == "published":
        pick_published(ledger, args.order)
    else:
        pick_new(ledger)


if __name__ == "__main__":
    main()
