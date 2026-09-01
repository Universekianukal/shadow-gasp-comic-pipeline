"""Generate script.json + panel_prompts.json for one case via the Anthropic
API, matching the exact schema and quality bar established manually for
SHADOW GASP issue 01 (NORJAK / D.B. Cooper):

  - 25+ genuinely substantive story pages (mix of "splash" and "grid" page
    types), not padding — each page should carry a real fact/beat.
  - Every FLUX image prompt must OMIT text-bearing objects rather than forbid
    them. ⚠️ REVERSED 2026-08-31 after measuring it: the old rule here said to
    "explicitly forbid text/signage/newspapers/posters/book titles", and that
    instruction was itself the cause of the garbled text it was meant to stop.
    FLUX has no negative prompt, so the banned nouns were read as things to
    draw. Proof: on Heaven's Gate, an A/B at fixed seed gave "MERSIOT" /
    "R IACE UNISEJUTY" / "FRCFR" WITH the ban sentence and clean blank
    surfaces WITHOUT it -- while 2000 steps of LoRA training aimed at the same
    defect changed nothing. The ban also overflowed CLIP's 77-token limit, so
    only T5 ever saw it. Same bug existed a second time in generate_panels.py's
    anti-matte clause ("no frame, no border, no keyline, no matte"), which was
    producing the mattes it banned: removing it took that book from 30 matted
    panels to 0 exhausted re-rolls.

Usage:
    CASE="..." python gen_case_script.py --out-dir path/to/case/comic
"""
import argparse
import json
import os
import re
import sys
import urllib.request

# The workflow invokes this as `python pipeline_lib/gen_case_script.py` from the repo root, so
# pipeline_lib is NOT on sys.path and a bare import would fail -- at 04:00, unattended.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_profiles  # noqa: E402

# Read lazily inside call_claude, not here: with COMIC_LLM_PROVIDER=fireworks this module
# must import and run with no Anthropic key present at all.
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
            headers={"Content-Type": "application/json", "X-Shared-Secret": secret,
                     # Cloudflare answers 403 "error code: 1010" to urllib's default
                     # Python-urllib/3.x agent, so the request never reaches the Worker at
                     # all. Same bug already fixed twice on the notify path.
                     "User-Agent": "shadow-gasp-comic-pipeline"},
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
            headers={"Content-Type": "application/json", "X-Shared-Secret": secret,
                     # Cloudflare answers 403 "error code: 1010" to urllib's default
                     # Python-urllib/3.x agent, so the request never reaches the Worker at
                     # all. Same bug already fixed twice on the notify path.
                     "User-Agent": "shadow-gasp-comic-pipeline"},
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

JSON VALIDITY -- this breaks whole builds, so treat it as a hard rule:
- NEVER put a double quote (") inside any string value: no captions, no dialogue, no taglines,
  no quotes-within-quotes. Use single quotes for quoted speech inside a caption, e.g.
  'We're just changing vehicles.' -- never "We're just changing vehicles."
  A single stray " ends its string early and makes the ENTIRE response unparseable. Three
  separate 50-page generations were lost to exactly this, each one a full paid call.
- Do not use literal newlines, tabs or backslashes inside string values either.

REQUIREMENTS for every prompt:
- Start with EXACTLY this, filling in the era: "Noir true-crime comic panel, ink outlines,
  halftone shading, [era] palette. Heavy black ink and deep shadow retained even in bright
  daylight, strong tonal contrast, never washed out or high-key."
  The second sentence is NOT optional. It is the difference between the shipped 80-page
  Heaven's Gate art and the Hanford run, whose prompts omitted it and produced flat pale grey
  pages -- one splash measured 0.04 saturation, effectively a blank sheet. Without an explicit
  floor on contrast the model drifts to washed-out mid-grey across a whole book.
- Describe the scene concretely: named location type (INTERIOR/EXTERIOR + room/setting), who's in it, what's happening, matching the shape's framing.
- The composition MUST match the panel's real shape. A SPLASH is a TALL full page, so never
  describe one as a "wide establishing vista" -- Hanford did exactly that and FLUX drew a wide
  scene across the top third and left two-thirds of the page empty. Tall shapes get vertical
  compositions; wide shapes get horizontal ones.
- NEVER include or imply any of: newspapers, headlines, signs, storefront signage, banners, posters, book titles, wanted posters, marquees, labels, gauges with markings, currency serial numbers, map annotations, dialogue bubbles, or any other element that implies readable text exists in the scene. (This rule is for YOU, when choosing what to put in the scene. Do not repeat the list inside the prompt itself -- see the next rule for why.)
- ALWAYS end with this exact sentence: "All visible surfaces are smooth and unmarked."
- NEVER write a negative instruction into the prompt -- no "no text", no "without lettering", no "avoid signs". FLUX has no negative prompt: the image model reads every noun you write as a thing to DRAW, so "no lettering on signs, banners, posters" reliably produces signs, banners and posters covered in garbled letters. This was measured, not assumed: an A/B on known-bad panels with the same seed produced "MERSIOT"/"FRCFR"/"CTIVPLIN" with the negation sentence and no letterforms at all without it. State what IS there, positively, and simply omit the objects you do not want.
- KEEP EACH PROMPT UNDER ABOUT 60 WORDS. CLIP, one of FLUX's two text encoders, truncates at 77 tokens. Anything past that is seen only by T5 -- which is how the old trailing ban ended up invisible to half the model while still summoning the objects it named.
"""


# Sliced, not copied, so the art-direction rules can never drift between the one-call path and
# the split path -- including the mandatory contrast clause the shipped books rely on.
STYLE_RULES = SCHEMA_SPEC_TEMPLATE[SCHEMA_SPEC_TEMPLATE.index("REQUIREMENTS for every prompt:"):]

PROMPT_SYSTEM = (
    "You write FLUX image prompts for SHADOW GASP, a documentary true-crime comic series. "
    "You are given a fixed list of panels with their shapes and the caption each will carry. "
    "Write one prompt per panel, matching the panel's shape and depicting what its caption "
    "describes. Return valid JSON only -- no markdown fences, no commentary."
)


class Truncated(RuntimeError):
    """The model stopped because it ran out of output budget, not because it finished.

    Distinct from a malformed response because it is recoverable: the same prompt with more room
    (or split into smaller calls) succeeds. Never swallow it -- truncated JSON parses as valid
    right up to the point it stops, which is exactly how this hid for five generations.
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
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    block_types = {}
    text_parts = []
    stop_reason = None
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
                elif etype == "message_delta":
                    # WHY the model stopped, which nothing here used to look at.
                    #
                    # When the response hits the token ceiling the API says so, plainly, in
                    # this event. Ignoring it meant a truncated response was returned as if it
                    # were complete, and the failure surfaced hundreds of lines later as
                    # "Expecting ',' delimiter" from json.loads -- an error that points at
                    # punctuation and says nothing about running out of room. Five whole-book
                    # generations were spent chasing a stray quote that was never there.
                    stop_reason = (event.get("delta") or {}).get("stop_reason")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {e.read().decode()}") from e
    text = "".join(text_parts)
    if not text:
        raise RuntimeError(f"No text content in streamed response (block types seen: {block_types})")
    if stop_reason == "max_tokens":
        raise Truncated(
            f"response hit the {max_tokens:,}-token ceiling after {len(text):,} characters, so "
            "the JSON is cut off mid-structure. Raise max_tokens or ask for less in one call.")
    return text


def repair_json(raw, max_fixes=200):
    """Parse model JSON, repairing the one defect that actually happens: a bare quote.

    A 50-page script is ~100KB of JSON containing hundreds of captions and lines of dialogue.
    One unescaped " inside any of them ends its string early, and the parser then fails on the
    next token with "Expecting ',' delimiter". That is what killed the 50pp run at char 96369
    after three full attempts -- roughly 30 minutes and three paid generations thrown away over
    a single character.

    Rather than reroll the whole book, escape the offending quote and re-parse. The quote that
    broke it is the last one before the error position, because the parser reads right up to the
    premature end of string and only then sees something it cannot use. Bounded, and falls back
    to raising the original error so a genuinely broken response is never silently accepted.
    """
    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError as e:
        # Bind it out of the except block: Python unbinds the `as` name on exit, so keeping the
        # original error for the give-up path needs an explicit reference.
        first = e

    text, fixes = raw, 0
    while fixes < max_fixes:
        try:
            obj = json.loads(text, strict=False)
            print(f"repaired {fixes} unescaped quote(s) in the model's JSON", flush=True)
            return obj
        except json.JSONDecodeError as e:
            j = text.rfind('"', 0, e.pos)
            if j <= 0:
                break
            text = text[:j] + '\\"' + text[j + 1:]
            fixes += 1
    raise first


def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in Claude's response")
    blob = match.group(0)
    try:
        return repair_json(blob)
    except json.JSONDecodeError as e:
        _dump_parse_failure(blob, e)
        raise


def call_model(system, user, max_tokens=16000, provider=None):
    """Route the script call to whichever provider is configured.

    Anthropic stays the default because it wrote every issue so far. The escape hatch exists
    because the API refused outright mid-build -- "Your credit balance is too low" -- and a
    pipeline that can only ever use one billing account stops dead when that account does.

    On the OpenAI-compatible providers this delegates to pipeline_lib/llm.py, which already
    handles the failure mode this exact prompt provokes: a reasoning model spending its entire
    token budget thinking and returning empty content. It caps reasoning_effort and escalates
    the budget on truncation. Do not replace it with a bare requests.post.
    """
    provider = (provider or os.environ.get("COMIC_LLM_PROVIDER")
                or "anthropic").strip().lower()
    if provider in ("", "anthropic"):
        return call_claude(system, user, max_tokens=max_tokens)

    import llm as LLM  # local import so the Anthropic path needs no extra module
    client = LLM.LLM(
        provider=provider,
        # generate() already retries this call 3x. Leaving llm.py's own 4x in place made one
        # timeout cost 12 attempts and ~2 hours of runner time before failing.
        max_retries=1,
        model=(os.environ.get("COMIC_LLM_MODEL") or "").strip() or None,
    )
    print(f"script provider: {client.provider} ({client.model})", flush=True)
    return client.text(user, system=system, max_tokens=max_tokens)


EXTRA_FILES = [("promo_bg.jpg", "SQUARE"), ("store_banner.jpg", "LANDSCAPE"),
               ("store_thumb.jpg", "SQUARE")]


def panels_from_script(script):
    """Every image the book needs, in page order, with the context a prompt writer needs.

    This is the CONTRACT between the two calls. The prompt writer never invents a filename --
    it is handed this list and must return exactly one entry per row. Panel filenames are
    positional, so a prompt writer left to guess would silently pair art with the wrong caption.
    """
    out = [{"file": script.get("cover", {}).get("image", "cover.jpg"), "shape": "PORTRAIT",
            "context": f"Front cover. {script.get('title','')} -- {script.get('tagline','')}"}]
    for page in script.get("pages", []):
        cells = ([page["panel"]] if page.get("type") == "splash" and page.get("panel")
                 else [c for row in page.get("rows", []) for c in row])
        for c in cells:
            out.append({
                "file": c["file"],
                "shape": c.get("shape", "LANDSCAPE"),
                "context": " ".join(x for x in [
                    f"Page {page.get('page')} ({page.get('title','')}).",
                    c.get("caption", ""), c.get("caption2", "")] if x).strip(),
            })
    for fn, shape in EXTRA_FILES:
        out.append({"file": fn, "shape": shape,
                    "context": f"Marketing image for {script.get('title','')}."})
    # De-duplicate while preserving order: a file repeated in the script needs one prompt.
    seen, uniq = set(), []
    for p in out:
        if p["file"] not in seen:
            seen.add(p["file"])
            uniq.append(p)
    return uniq


def generate_prompts(script, provider, chunk_size=80, attempts=2):
    """Second call: one prompt per panel, in bounded chunks.

    Split from the script call because a single response carrying both is ~100KB, and JSON
    failure probability scales with length -- five whole-book generations were lost to one bad
    character. A chunk that fails costs 80 prompts, not the book, and the script survives it.
    """
    panels = panels_from_script(script)
    style = STYLE_RULES.replace("__TITLE__", script.get("title", ""))
    collected, missing = {}, list(panels)

    for start in range(0, len(panels), chunk_size):
        batch = panels[start:start + chunk_size]
        listing = "\n".join(
            f'{i + 1}. file="{p["file"]}" shape={p["shape"]} :: {p["context"][:220]}'
            for i, p in enumerate(batch))
        user = (f"{style}\n\nWrite one FLUX image prompt for each of these {len(batch)} panels "
                f"from the comic \"{script.get('title','')}\".\n\n{listing}\n\n"
                'Return ONLY: {"panel_prompts": [{"file": "...", "shape": "...", '
                '"prompt": "..."}]} with exactly one entry per numbered item above, in the same '
                "order, using the EXACT file names given. No extra entries, none missing.")
        want = {p["file"] for p in batch}
        for attempt in range(1, attempts + 1):
            try:
                raw = call_model(PROMPT_SYSTEM, user, max_tokens=min(32000, len(batch) * 320),
                                 provider=provider)
                got = extract_json(raw).get("panel_prompts", [])
                names = {g.get("file") for g in got}
                if names != want:
                    raise ValueError(
                        f"panel set mismatch: {len(want - names)} missing, "
                        f"{len(names - want)} unexpected")
                for g in got:
                    collected[g["file"]] = g
                break
            except (json.JSONDecodeError, ValueError, RuntimeError) as e:
                print(f"  prompts chunk {start // chunk_size + 1} attempt {attempt}/{attempts} "
                      f"failed ({e})", flush=True)
                if attempt == attempts:
                    raise
        print(f"  prompts: {len(collected)}/{len(panels)} done", flush=True)

    # Emit in the canonical panel order, not whatever order the model replied in.
    return [collected[p["file"]] for p in panels if p["file"] in collected]


def _dump_parse_failure(raw, err):
    """Show the actual bad characters, and keep the response.

    Three 50-page generations were spent discovering only that the JSON was invalid -- the error
    said WHERE but never WHAT, and the raw response was discarded each time, so every diagnosis
    cost another paid call. Print a window around the failure and save the text.
    """
    pos = getattr(err, "pos", 0) or 0
    lo, hi = max(0, pos - 220), min(len(raw), pos + 220)
    print(f"--- JSON parse failed at char {pos}: {err} ---", flush=True)
    print(f"...{raw[lo:pos]}>>>HERE>>>{raw[pos:hi]}...", flush=True)
    try:
        path = os.path.join(os.environ.get("RUNNER_TEMP", "."), "bad_script_response.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw)
        print(f"raw response saved to {path} ({len(raw)} chars)", flush=True)
    except Exception:
        pass


# 2, not 3. Every attempt is a full paid generation of a 50-page book, and all three attempts
# have failed identically both times this misfired -- a third reroll of the same prompt buys
# nothing but cost.
def generate(system, user, max_tokens=16000, attempts=2,
             require=("script", "panel_prompts"), provider=None):
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
            text = call_model(system, user, max_tokens=max_tokens, provider=provider)
            result = extract_json(text)
            missing = [k for k in require if k not in result]
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
    ap.add_argument("--profile", default="",
                    help="Layout profile to force (chamber/cinematic/classic/documentary/"
                         "mosaic/staccato). Empty = derive it from the case id, which is what "
                         "the daily scheduled run does.")
    args = ap.parse_args()
    if not args.case:
        raise SystemExit("Provide --case or set CASE env var")

    os.makedirs(os.path.join(args.out_dir, "panels"), exist_ok=True)

    # The profile is part of the key because it changes the generation PROMPT (tier structures,
    # splash rate, bleed share). Without it, rebuilding the same case at the same page count in
    # a different style would hit the cache and silently return the previous style's script --
    # the build would report "cinematic" and deliver the mosaic pages it had already paid for.
    _profile_key = layout_profiles.profile_for(args.case_id or args.case, args.profile)
    cache_key = f"{args.case_id or args.case}:{args.issue_no}:{args.target_pages}:{_profile_key}"
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
        # Panel budget follows the issue's layout profile, floored at the original 2.2/page so a
        # profile can never argue the book down below the density that floor was protecting.
        _prof = layout_profiles.profile_for(args.case_id or args.case, args.profile)
        _per_page = max(2.2, layout_profiles.avg_panels_per_page(_prof))
        target_panels = round(args.target_pages * _per_page) + 50
        schema_spec = (SCHEMA_SPEC_TEMPLATE
                        .replace("__TARGET_PAGES__", str(args.target_pages))
                        .replace("__TARGET_PANELS__", str(target_panels)))
        # Per-issue page architecture. Without this every comic in the catalogue shares one
        # rhythm and the series reads as a template -- the previous issue came out ~85%
        # two-panel pages. The profile is derived from the case id, so it is stable across
        # re-runs of the same case and different between neighbouring cases.
        layout_block = layout_profiles.prompt_block(args.case_id or args.case, args.profile)
        print(layout_block, flush=True)

        user = (
            f"Case: {args.case}\nIssue number: {args.issue_no}\n\n"
            f"{layout_block}\n{schema_spec}\n\nWrite the full comic now for this case."
        )

        # 16000 was sized for the 25pp default and silently starved a 75pp
        # request (Claude spent its whole budget on extended thinking and
        # never emitted a text block at all). Scale with PANEL count now,
        # not page count -- panel_prompts is one entry per panel, and the
        # panel-density fix means panel count can run ~2x page count, so
        # sizing off pages alone would under-budget again.
        max_tokens = min(64000, max(16000, target_panels * 500))

        split = (os.environ.get("COMIC_SPLIT_GENERATION", "true").lower() != "false")
        if split:
            # TWO sequential calls instead of one.
            #
            # A combined response is ~100KB and JSON has no partial validity, so one stray
            # character destroys the whole book -- five paid whole-book generations were lost
            # that way at 35pp and 50pp. Splitting halves each payload and, more importantly,
            # means a failure in the prompts leaves the script intact to retry against.
            #
            # Strictly sequential, never concurrent: the prompt writer is HANDED the script's
            # finished panel list. Generating both at once would let it invent prompts for
            # panels the script had not settled, and panel filenames are positional, so the
            # mismatch would surface as art sitting silently under the wrong caption.
            script_provider = os.environ.get("COMIC_SCRIPT_PROVIDER") or None
            prompts_provider = os.environ.get("COMIC_PROMPTS_PROVIDER") or None
            script_user = user + (
                "\n\nIMPORTANT: return ONLY the \"script\" key this time. Do NOT include "
                "\"panel_prompts\" -- the image prompts are written in a separate pass from "
                "the panel list you produce here."
            )
            print(f"[1/2] script  (provider: {script_provider or 'default'})", flush=True)
            script_only = generate(system, script_user, max_tokens=max_tokens,
                                   require=("script",), provider=script_provider)
            print(f"[2/2] prompts (provider: {prompts_provider or 'default'})", flush=True)
            prompts = generate_prompts(script_only["script"], prompts_provider)
            result = {"script": script_only["script"], "panel_prompts": prompts}
        else:
            result = generate(system, user, max_tokens=max_tokens)
        cache_save(cache_key, result)

    script_path = os.path.join(args.out_dir, f"script_issue{args.issue_no}.json")
    prompts_path = os.path.join(args.out_dir, "panel_prompts.json")

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(result["script"], f, indent=2, ensure_ascii=False)
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(result["panel_prompts"], f, indent=2, ensure_ascii=False)

    n_pages = len(result["script"]["pages"])
    # Measure what actually came back against the profile. A distribution stated only in prose
    # is not enforced anywhere -- that is exactly how "59% two-panel" became ~85% two-panel on
    # the last issue. This does not block the build; it makes the drift visible in the log so a
    # bad rhythm is caught before 25 pages of art get generated from it.
    ok, report = layout_profiles.audit(result["script"], args.case_id or args.case,
                                       override=args.profile)
    print("\n".join(report), flush=True)
    if not ok:
        print("WARNING: page-type mix is off target for this profile (see above). The art will "
              "still build; re-run the script step if the rhythm matters for this issue.",
              flush=True)

    n_panels = len(result["panel_prompts"])
    print(f"Wrote {script_path} ({n_pages} story pages) and {prompts_path} ({n_panels} panels)")
    if n_pages < args.target_pages:
        print(f"WARNING: only {n_pages} pages generated (< {args.target_pages} requested) — "
              f"this case may not have enough documented material.", file=os.sys.stderr)


if __name__ == "__main__":
    main()
