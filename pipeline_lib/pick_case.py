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
import unicodedata
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


VIDEO_REPO_RAW = "https://raw.githubusercontent.com/Universekianukal/shadow-gasp-pipeline/main"
VIDEO_LEDGER_URL = f"{VIDEO_REPO_RAW}/_pipeline/cases_used.json"
VIDEO_STATE_URL = f"{VIDEO_REPO_RAW}/_pipeline/batch/state.json"


def _fetch_json(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def norm_case(s):
    """Case names for joining across the two repos.

    The same case is spelled differently in each file -- state.json writes "The Sodder Fire — Five
    Children" with an em dash where the video ledger stores U+0097 for the same book. A plain ==
    join therefore reports published days as unpublished. Strip punctuation, control characters
    and spacing down to comparable words.
    """
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(" " if unicodedata.category(ch)[0] in ("P", "C", "Z") else ch for ch in s)
    return " ".join(s.lower().split())


def sync_from_video_repo(ledger):
    """Refresh this repo's copy of the published-video list from the video pipeline's own.

    ⚠️ THIS FILE IS A COPY AND IT ROTS. Both repos carry a cases_used.json; the video pipeline's
    is the authority on what has been published, and this one is a snapshot that nothing was
    refreshing. Measured 2026-09-03: the video repo listed 107 videos, this one 74 -- 33
    published shorts, everything from 2026-07-30 on, that the comic pipeline simply could not
    see. Two consequences, both silent: pick_case chose from a pool five weeks stale, and
    stage_and_deliver could not find those cases' videos, so their comics shipped with no funnel
    button and no way to reach the audience they were made for.

    Additive only. `comicAt` and any local entry are preserved -- the video repo knows what was
    published, this repo knows what has been drawn, and neither may overwrite the other.
    """
    try:
        remote = _fetch_json(VIDEO_LEDGER_URL)
    except Exception as e:
        print(f"WARNING: could not sync the video ledger ({e}) -- using the local copy", flush=True)
        return ledger

    have = {norm_case(c.get("case", "")) for c in ledger["cases"]}
    added = filled = 0
    for c in remote.get("cases", []):
        key = norm_case(c.get("case", ""))
        if not key:
            continue
        if key not in have:
            ledger["cases"].append({"videoId": c.get("videoId"), "case": c["case"],
                                    "publishedAt": c.get("publishedAt")})
            have.add(key)
            added += 1
        elif c.get("videoId"):
            # Already known locally, but the video may have gone out since this copy was taken.
            local = next(x for x in ledger["cases"] if norm_case(x.get("case", "")) == key)
            if not local.get("videoId"):
                local["videoId"] = c["videoId"]
                local["publishedAt"] = local.get("publishedAt") or c.get("publishedAt")
                filled += 1
    if added or filled:
        save_ledger(ledger)
    total = sum(1 for c in ledger["cases"] if c.get("videoId"))
    print(f"ledger sync: +{added} new case(s), {filled} newly published; "
          f"{total} videos known", flush=True)
    return ledger


def pick_upcoming(ledger, lead):
    """A case whose short has NOT gone out yet, so the comic is ready when the short lands.

    ⭐ The sales logic the user asked for: a comic published alongside a brand-new short rides
    that short's launch traffic, while a comic for a video from five weeks ago is sold to an
    audience that has already moved on. The back catalogue never stops being available; a launch
    day happens once.

    Upcoming = a day in the video pipeline's state.json that is PREGENERATED (`done`) but has no
    videoId in either ledger. Day numbers publish in ascending order, so the lowest such day is
    the next to go out.

    ⚠️ This picks by QUEUE POSITION, not by date. Neither repo records a publish date for a day
    that has not published yet, and the video ledger's own publishedAt stops at 2026-08-15, so
    "the one going out tomorrow" cannot be computed from the data -- only "the next one due".
    `lead` skips that many days further down the queue when the immediate next is already in
    production.
    """
    state = _fetch_json(VIDEO_STATE_URL).get("days", {})
    published = {norm_case(c["case"]) for c in ledger["cases"] if c.get("videoId")}

    # Cases that already HAVE a comic. `pick_published` has always filtered on this; the first
    # version of pick_upcoming set comicAt without ever reading it, so `--lead 0` would hand back
    # the same day every time and rebuild a book that already exists.
    drawn = {norm_case(c.get("case", "")) for c in ledger["cases"] if c.get("comicAt")}

    pending = []
    for k in sorted(state, key=lambda k: int(k)):
        day = state[k]
        if not day.get("done"):
            continue                       # not pregenerated: no art, no script, not imminent
        key = norm_case(day.get("case", ""))
        if key in published:
            continue                       # already out
        if key in drawn:
            continue                       # already has a comic
        pending.append((int(k), day["case"]))

    if not pending:
        sys.exit("No pregenerated day is still unpublished -- nothing upcoming to get ahead of.")

    # Days far below the publishing frontier are stalled, not upcoming: they were skipped and
    # left behind. Work from the frontier -- the highest day that HAS published -- so a comic is
    # made for a short that is genuinely about to land.
    frontier = max((int(k) for k in state
                    if norm_case(state[k].get("case", "")) in published), default=0)
    ahead = [p for p in pending if p[0] > frontier] or pending
    if lead >= len(ahead):
        sys.exit(f"Only {len(ahead)} upcoming day(s) past day {frontier}; --lead {lead} is "
                 f"beyond the queue.")
    day_no, case = ahead[lead]

    stalled = [p[0] for p in pending if p[0] <= frontier]
    print(f"Source: UPCOMING short -> comic. Publishing frontier is day {frontier}; "
          f"{len(ahead)} pregenerated day(s) are still ahead of it.", flush=True)
    if stalled:
        print(f"  (ignoring day(s) {stalled} -- below the frontier, so stalled rather than due)",
              flush=True)
    print(f"  chosen: day {day_no} -- {case}", flush=True)

    entry = next((c for c in ledger["cases"] if norm_case(c.get("case", "")) == norm_case(case)),
                 None)
    if entry is None:
        entry = {"videoId": None, "case": case, "publishedAt": None}
        ledger["cases"].append(entry)
    entry["comicAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_ledger(ledger)

    # No videoId yet by definition. stage_and_deliver's ledger lookup will find it on a later
    # rebuild once the short is out; until then the draft simply carries no funnel button.
    emit(case, f"Comic companion to the upcoming short (day {day_no}).", "")


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
    ap.add_argument("--source", choices=["published", "upcoming", "new"], default="published",
                    help="published: a case whose short is already on YouTube and has no comic "
                         "yet (default). upcoming: a case whose short has NOT gone out yet, so "
                         "the comic lands with the short's launch traffic. new: ask Claude for a "
                         "case never covered at all.")
    ap.add_argument("--order", choices=["oldest", "newest"], default="oldest",
                    help="For --source published: which end of the back catalogue to work from.")
    ap.add_argument("--lead", type=int, default=0,
                    help="For --source upcoming: how many days further down the queue to go. 0 "
                         "is the next short due, 1 the one after it. Use it when the next short "
                         "publishes too soon for a comic to be finished and reviewed.")
    args = ap.parse_args()

    ledger = load_ledger()
    # Always refresh from the video repo first. Every source reads this file: `published` picks
    # from it, `upcoming` diffs against it, and `new` excludes everything in it -- so a stale
    # copy quietly corrupts all three.
    ledger = sync_from_video_repo(ledger)
    if args.source == "published":
        pick_published(ledger, args.order)
    elif args.source == "upcoming":
        pick_upcoming(ledger, args.lead)
    else:
        pick_new(ledger)


if __name__ == "__main__":
    main()
