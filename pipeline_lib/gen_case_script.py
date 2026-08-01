"""Generate script.json + panel_prompts.json for one case via the Anthropic
API, matching the exact schema and quality bar established manually for
SHADOW GASP issue 01 (NORJAK / D.B. Cooper):

  - 25+ genuinely substantive story pages (mix of "splash" and "grid" page
    types), not padding — each page should carry a real fact/beat.
  - Every FLUX image prompt must explicitly forbid text/signage/newspapers/
    posters/book titles, learned the hard way: FLUX hallucinates garbled
    fake text whenever a scene implies anything readable exists in it.

Usage:
    CASE="..." python gen_case_script.py --out-dir path/to/case/comic
"""
import argparse
import json
import os
import re
import urllib.request

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-5"


def cache_get(key):
    """Check the Worker's private KV for an already-generated script.

    cases/ is deliberately never committed to this public repo (see
    pipeline.yml), so a retry after a LATER step fails (Kaggle auth, OCR,
    Gumroad) used to silently re-call Claude for a script that already came
    back fine -- real API cost for a repeat run. The Worker's KV is private
    (not browsable the way repo content is), so it's a safe place to cache
    just the script+prompts JSON across retries of the SAME case+page-count.
    Best-effort: caching is a cost optimization, not correctness-critical, so
    any failure here (missing secrets, Worker down) just falls through to a
    fresh generation instead of crashing the build.
    """
    worker_url, secret = os.environ.get("WORKER_URL"), os.environ.get("WORKER_SHARED_SECRET")
    if not worker_url or not secret:
        return None
    try:
        req = urllib.request.Request(
            f"{worker_url.rstrip('/')}/script-cache/get",
            data=json.dumps({"key": key}).encode(),
            headers={"Content-Type": "application/json", "X-Shared-Secret": secret},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"WARNING: script cache lookup failed ({e.code}) -- generating fresh")
        return None
    except Exception as e:
        print(f"WARNING: script cache lookup failed ({e}) -- generating fresh")
        return None


def cache_save(key, result):
    worker_url, secret = os.environ.get("WORKER_URL"), os.environ.get("WORKER_SHARED_SECRET")
    if not worker_url or not secret:
        return
    try:
        req = urllib.request.Request(
            f"{worker_url.rstrip('/')}/script-cache/save",
            data=json.dumps({"key": key, "script": result["script"], "panel_prompts": result["panel_prompts"]}).encode(),
            headers={"Content-Type": "application/json", "X-Shared-Secret": secret},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30):
            pass
    except Exception as e:
        print(f"WARNING: failed to cache script for future retries ({e}) -- not fatal")

SCHEMA_SPEC_TEMPLATE = """
Return a single JSON object with exactly two top-level keys: "script" and
"panel_prompts".

"script" must match this schema (values are examples of shape/tone):
{
  "series": "SHADOW GASP",
  "issue_no": "NN",
  "title": "SHORT PUNCHY TITLE",
  "subtitle": "one-line factual subtitle",
  "tagline": "ONE PUNCHY HOOK LINE",
  "panels_dir": "panels",
  "output": "TITLE_issue.pdf",
  "subject": "one sentence, what this comic covers",
  "promo_badge": "ONE or TWO words in caps for a gold badge on the promo graphic, stating the single most striking factual angle of the case — e.g. \"UNSOLVED\", \"COVER-UP\", \"17,000 DEAD\", \"STILL MISSING\". Never invent; must be literally true.",
  "promo_inside": ["FOUR short all-caps phrases naming what the issue actually covers, e.g. \"6 NAMED SUSPECTS\", \"FBI CASE FILES\", \"FORENSIC EVIDENCE\", \"THE RANSOM MONEY\""],
  "promo_hook": "ONE scroll-stopping sentence (max ~90 chars) stating the real hook of the case in plain language, aimed at someone who has never heard of it. State the mystery, do not tease vaguely. Example: \"He jumped from a plane with $200,000. Nobody ever found him.\"",
  "keywords": "comma, separated, seo, keywords",
  "cover": {"image": "cover.jpg", "logo": "SHADOW GASP", "issue_line": "ISSUE NN", "title": "...", "tagline": "..."},
  "title_page": {
    "heading": "...", "credits": ["SHADOW GASP — ISSUE NN", "", "A true account of ...", "", "Story adapted from the Shadow Gasp documentary script.", "Art generated with AI image tools; lettering and layout assembled from the Shadow Gasp comic builder."],
    "disclaimer": "Based on real events... Dialogue is dramatized...",
    "masthead": [["story","Shadow Gasp"],["art","AI-generated, art-directed"],["letters & design","Shadow Gasp comic builder"]],
    "indicia": [
      "SHADOW GASP #NN: TITLE. First printing, 2026. Published by Shadow Gasp Comics.",
      "Entire contents copyright © 2026 Shadow Gasp Comics. All rights reserved. No part of this publication may be reproduced or transmitted, in any form or by any means, without the prior written permission of the publisher, except for short excerpts for review purposes.",
      "This is a work of documentary comics based on real events and public accounts. Interior art was generated with AI image tools and art-directed, edited and composited for publication; lettering, colour and layout are original to this edition.",
      "PRINTED IN [COUNTRY TK]  ·  kianukal@theverdictcourier.com"
    ]
  },
  "pages": [
    {"page": 3, "title": "...", "type": "splash", "panel": {"file": "p01_splash.jpg", "shape": "SPLASH", "caption": "...", "dialogue": []}},
    {"page": 4, "title": "...", "type": "grid", "rows": [[{"file": "p02_1.jpg", "shape": "LANDSCAPE", "caption": "...", "bleed": ["left","right","top"]}], [{"file":"p02_2.jpg","shape":"PORTRAIT","caption":"..."},{"file":"p02_3.jpg","shape":"LANDSCAPE","caption":"..."}]]}
  ],
  "back_matter": {"heading": "WHAT WAS REAL", "pages": 2, "lines": ["FACT ONE...", "", "FACT TWO..."], "sources": ["source 1", "source 2"]},
  "back_cover": {"logo": "SHADOW GASP", "quote": "\\"A PUNCHY QUOTE\\"", "footer": "SHADOW GASP — TRUE CRIME. TOLD IN INK.", "blurb": "...", "publisher": "Shadow Gasp Press", "price": "$2.99", "rating": "T", "isbn": ""}
}

REQUIREMENTS for "pages":
- At least __TARGET_PAGES__ entries (pages numbered sequentially starting at 3).
  If the real case doesn't have enough documented material to reach this
  honestly, write as many genuine, non-padded pages as the facts support and
  say so in a code comment at the very end of your response after the JSON
  (outside the JSON object) — do not invent details to hit the number.
- shape must be one of SPLASH, PORTRAIT, LANDSCAPE, SQUARE.
- Every fact must be something you have real confidence is true — do not
  invent quotes, statistics, or events. If uncertain, keep the caption
  vaguer rather than fabricate specifics.
- TOTAL PANEL COUNT across all pages must be at least __TARGET_PANELS__
  (roughly 2.2 panels per page on average — measured from a real published
  issue in this series, NOT a made-up number). Do NOT satisfy the page count
  by making every page a single panel — that is flat and undramatic, and is
  not how a real print comic paces a scene. If a real case doesn't have
  enough distinct FACTS to reach __TARGET_PAGES__ genuine beats, that's fine
  — decompress the beats you do have across more panels each (a wide
  establishing shot, then a reaction, then a close-up) rather than either
  inventing new beats or leaving every page at one panel.
- A "grid" page must contain at least 2 panels. If a beat only deserves one
  image, mark it "splash" — a "grid" page with a single row of one panel is
  not allowed, it's just a mislabeled splash.
- Distribute panel counts the way a real comic paces itself, NOT uniformly.
  For reference, a real 27-page/59-panel issue in this series broke down as:
  ~15% single-panel splash pages (reserved for genuine dramatic beats: an
  opening image, a major reveal, a death, the ending), ~59% two-panel pages
  (the default rhythm for an ordinary story beat), ~19% three-panel pages,
  and ~7% four-panel pages (for busy/expository moments — a montage, a list
  of names, a fast sequence). Match that shape, not a flat repeated count.

"panel_prompts" must be a JSON array with ONE entry per unique "file" that
appears anywhere in "script" (cover.jpg plus every panel file), PLUS three extra
entries: "promo_bg.jpg" (shape "SQUARE"), "store_banner.jpg" (shape
"LANDSCAPE") and "store_thumb.jpg" (shape "SQUARE"). store_banner is the
wide hero image on the sales page and store_thumb is the small square
storefront tile, so store_thumb must be a single bold simple subject that
still reads when shrunk to a tiny tile. The promo_bg entry: a wide atmospheric
establishing image of the case's setting/mood with NO people in close-up and
lots of empty space (it gets darkened and used as a background behind large
promo text, so it must read at a glance and not compete with type), each:
{"file": "p02_1.jpg", "shape": "LANDSCAPE", "prompt": "..."}

REQUIREMENTS for every prompt:
- Start with: "Noir true-crime comic panel, ink outlines, halftone shading, [era] palette."
- Describe the scene concretely: named location type (INTERIOR/EXTERIOR + room/setting), who's in it, what's happening, matching the shape's framing.
- NEVER include or imply any of: newspapers, headlines, signs, storefront signage, banners, posters, book titles, wanted posters, marquees, labels, gauges with markings, currency serial numbers, map annotations, dialogue bubbles, or any other element that implies readable text exists in the scene.
- ALWAYS end with this exact sentence: "Absolutely no text, no letters, no writing, no readable words anywhere in the image — every surface is blank or too weathered/blurred to read."
"""


def call_claude(system, user, max_tokens=16000):
    """Stream the response instead of waiting for one big blocking read.

    A large --target-pages request needs a large max_tokens budget, and a
    64000-token generation can genuinely take longer than a flat request
    timeout to finish (hit exactly this on a 75pp build: 5-minute read
    timeout, still generating -> TimeoutError, zero output). Streaming turns
    the timeout into a per-chunk idle bound instead of a total-duration cap,
    so a slow-but-still-progressing generation doesn't get killed early.
    """
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "stream": True,
        }).encode(),
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    block_types = {}
    text_parts = []
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            for raw_line in r:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[len("data: "):])
                etype = event.get("type")
                if etype == "content_block_start":
                    block_types[event["index"]] = event["content_block"].get("type")
                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if block_types.get(event["index"]) == "text" and delta.get("type") == "text_delta":
                        text_parts.append(delta.get("text", ""))
                elif etype == "error":
                    raise RuntimeError(f"Anthropic API streaming error: {event}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {e.read().decode()}") from e
    text = "".join(text_parts)
    if not text:
        raise RuntimeError(f"No text content in streamed response (block types seen: {block_types})")
    return text


def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in Claude's response")
    return json.loads(match.group(0))


def generate(system, user, max_tokens=16000, attempts=3):
    """Call Claude and parse its JSON, retrying on malformed OR missing output.

    Two distinct failure modes, both retried here:
    1. Malformed JSON (usually an unescaped quote inside dialogue text) --
       the same failure mode already hit and fixed in MindUnlocked's
       _gen_video_content.py. A bare retry of the same prompt usually clears it.
    2. Empty response (call_claude's own "No text block" RuntimeError) -- seen
       on a 75-page request: the model spent its whole max_tokens budget on
       extended thinking and never got to write the actual answer, so the
       response has a "thinking" block but no "text" block at all. Retrying
       alone won't fix this if max_tokens is genuinely too small for the
       requested page count -- see the scaling in main() -- but IS still
       worth retrying since the model doesn't always think that long.
    """
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            text = call_claude(system, user, max_tokens=max_tokens)
            result = extract_json(text)
            missing = [k for k in ("script", "panel_prompts") if k not in result]
            if missing:
                raise ValueError(f"JSON parsed but missing key(s): {missing}")
            return result
        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
            last_err = e
            print(f"WARNING: attempt {attempt}/{attempts} failed ({e}) -- retrying" if attempt < attempts else f"FAILED: attempt {attempt}/{attempts} ({e})")
    raise RuntimeError(f"Claude never returned a usable script after {attempts} attempts: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--case", default=os.environ.get("CASE"))
    ap.add_argument("--case-id", default=None, help="Slug used as the script-cache key (falls back to --case if omitted)")
    ap.add_argument("--issue-no", default="01")
    ap.add_argument("--target-pages", type=int, default=25)
    args = ap.parse_args()
    if not args.case:
        raise SystemExit("Provide --case or set CASE env var")

    os.makedirs(os.path.join(args.out_dir, "panels"), exist_ok=True)

    cache_key = f"{args.case_id or args.case}:{args.issue_no}:{args.target_pages}"
    result = cache_get(cache_key)
    if result:
        print(f"Using cached script for '{cache_key}' -- no Anthropic API call made")
    else:
        system = (
            "You are writing one issue of SHADOW GASP, a true-crime/dark-history "
            "documentary comic series. You write ONLY well-documented real facts — "
            "never invent details about real people or events. Output raw JSON only, "
            "no markdown fences, no commentary before the JSON. One optional short "
            "plain-text note is allowed AFTER the JSON object only if you had to "
            "write fewer pages than requested due to limited real source material."
        )
        # 2.2 panels/page is measured from a real published issue in this
        # series (27pp/59 panels), not a guess -- see the panel-density fix
        # in REQUIREMENTS below. A prior 75pp run satisfied "at least 75
        # pages" with ~1 panel/page (88 total, should have been ~165 at the
        # bare density floor) by exploiting the fact that only page count,
        # not panel count, was ever enforced. +50 buffer on top of the bare
        # floor (user's call) so there's real surplus to cut weaker panels
        # from during art-directing, not just exactly enough.
        target_panels = round(args.target_pages * 2.2) + 50
        schema_spec = (SCHEMA_SPEC_TEMPLATE
                        .replace("__TARGET_PAGES__", str(args.target_pages))
                        .replace("__TARGET_PANELS__", str(target_panels)))
        user = (
            f"Case: {args.case}\nIssue number: {args.issue_no}\n\n"
            f"{schema_spec}\n\nWrite the full comic now for this case."
        )

        # 16000 was sized for the 25pp default and silently starved a 75pp
        # request (Claude spent its whole budget on extended thinking and
        # never emitted a text block at all). Scale with PANEL count now,
        # not page count -- panel_prompts is one entry per panel, and the
        # panel-density fix means panel count can run ~2x page count, so
        # sizing off pages alone would under-budget again.
        max_tokens = min(64000, max(16000, target_panels * 500))
        result = generate(system, user, max_tokens=max_tokens)
        cache_save(cache_key, result)

    script_path = os.path.join(args.out_dir, f"script_issue{args.issue_no}.json")
    prompts_path = os.path.join(args.out_dir, "panel_prompts.json")

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(result["script"], f, indent=2, ensure_ascii=False)
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(result["panel_prompts"], f, indent=2, ensure_ascii=False)

    n_pages = len(result["script"]["pages"])
    n_panels = len(result["panel_prompts"])
    print(f"Wrote {script_path} ({n_pages} story pages) and {prompts_path} ({n_panels} panels)")
    if n_pages < args.target_pages:
        print(f"WARNING: only {n_pages} pages generated (< {args.target_pages} requested) — "
              f"this case may not have enough documented material.", file=os.sys.stderr)


if __name__ == "__main__":
    main()
