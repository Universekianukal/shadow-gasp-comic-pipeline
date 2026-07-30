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
- Vary pacing: mostly "grid" pages, with "splash" pages at key turning
  points (opening, a major reveal, the ending).

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
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {e.read().decode()}") from e
    if "content" not in data:
        raise RuntimeError(f"Unexpected Anthropic API response: {json.dumps(data)[:1000]}")
    for block in data["content"]:
        if block.get("type") == "text":
            return block["text"]
    raise RuntimeError(f"No text block in Anthropic API response: {json.dumps(data)[:1000]}")


def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group(0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--case", default=os.environ.get("CASE"))
    ap.add_argument("--issue-no", default="01")
    ap.add_argument("--target-pages", type=int, default=25)
    args = ap.parse_args()
    if not args.case:
        raise SystemExit("Provide --case or set CASE env var")

    os.makedirs(os.path.join(args.out_dir, "panels"), exist_ok=True)

    system = (
        "You are writing one issue of SHADOW GASP, a true-crime/dark-history "
        "documentary comic series. You write ONLY well-documented real facts — "
        "never invent details about real people or events. Output raw JSON only, "
        "no markdown fences, no commentary before the JSON. One optional short "
        "plain-text note is allowed AFTER the JSON object only if you had to "
        "write fewer pages than requested due to limited real source material."
    )
    schema_spec = SCHEMA_SPEC_TEMPLATE.replace("__TARGET_PAGES__", str(args.target_pages))
    user = (
        f"Case: {args.case}\nIssue number: {args.issue_no}\n\n"
        f"{schema_spec}\n\nWrite the full comic now for this case."
    )

    text = call_claude(system, user)
    result = extract_json(text)

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
