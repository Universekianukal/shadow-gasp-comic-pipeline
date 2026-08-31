#!/usr/bin/env python3
"""
Work out the size every panel SHOULD have been drawn at, and write it into the
prompt pack.

The art for issue 02 came back at 16:9 and 9:16 because that is what the
generator defaults to. Neither tiles a comic page. A 6.625 x 10.1875in trim has
a live area of 0.63:1, so a full-width tier wants 1.92:1 when three stack up and
1.27:1 when two do — and a single 16:9 panel can physically cover only about a
third of the page no matter how it is laid out. That is the empty space in the
book, and no layout engine can solve it: the art has to be drawn to the page.

This script inverts the layout. Instead of fitting pages to whatever the art
happens to be, it solves the page FIRST — the way it would be ruled up by hand —
and reports the size each panel must be to fill its cell exactly. Feed the
numbers back to the generator and the crop budget, the empty space and the
letterboxing all go away together.

    python3 spec_panels.py            # write spec_panels.md, update prompts
    python3 spec_panels.py --dry-run  # report only

Row heights are weighted by how many panels share the row: a row holding one
panel is a beat and is given more height than a row of three. That keeps the
pages from reading as a mechanical grid while still tiling to 100%.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_comic as B                                       # noqa: E402

INCH = 72.0

# The heights a tier may be given, as multiples of an even share. A page is not
# a grid of equal bands — it is a few beats at different volumes — so the tier
# height is something the planner CHOOSES, not a constant.
#
# It matters more than it sounds. With a fixed height per tier, a two-panel page
# has exactly one legal answer: two equal bands, each 1.27:1. That is why the
# first spec asked for thirty 1.27 panels and declared almost the whole book a
# redraw. Let the planner make one tier twice the other and the same page
# becomes a 0.95 panel over a 1.90 tier — a far better page, and the 1.90 half
# is drawable from the 16:9 art that already exists.
WEIGHTS = (0.72, 1.0, 1.4, 1.9)

# Tallest tier may be at most this many times the shortest. Past it the short
# tier stops being a tier and becomes a strip.
WEIGHT_SPREAD = 2.6

# How close two tier structures must be in cost before they count as equally good pages, at
# which point the AUTHORED structure wins. Set from the real cost spread for a six-panel page:
# the workable structures ([1,2,3], [3,3], [2,2,2], [3,1,2]) sit within a few hundredths of each
# other, while structures that demand unreadable slivers are an order of magnitude worse. Too
# small and the planner overrides every authored page and the whole book becomes one shape; too
# large and it accepts a genuinely bad rule-up because the script asked for it.
STRUCTURE_TOL = 0.05

# Press resolution. Everything below is quoted at this; the art currently in the
# book is 1280px wide, which lands around 210 DPI at printed size.
DPI = 300

# Generators like multiples of 8. Rounding here rather than at the far end keeps
# the quoted aspect and the quoted pixels from disagreeing.
QUANT = 8


def px(inches):
    return int(round(inches * DPI / QUANT)) * QUANT


def ratio(a):
    """Nearest tidy n:m for a decimal aspect, for the human-readable sheet."""
    best, err = None, 1e9
    for m in range(1, 33):
        n = round(a * m)
        if n < 1:
            continue
        e = abs(a - n / m)
        if e < err - 1e-9:
            best, err = (n, m), e
    return "%d:%d" % best


# The band of aspects a comic panel can sit in and still read as a panel. Below
# the floor it is a slot and the art has nowhere to stage a shot; above the
# ceiling it is a letterbox strip. Anything inside is fair game.
ASPECT_FLOOR = 0.58
ASPECT_CEIL = 2.30

# How hard the planner leans on reusing the art that already exists.
#
# Set to zero: the whole book is being redrawn, so there is nothing to reuse and
# nothing to compromise for. While this was non-zero the plan was bending pages
# around the shape of art that happened to exist — accepting a worse tier here to
# save a redraw there. That is the same bargain that produced the original
# problem, just running in the other direction. With every panel being generated
# to spec, the page can be ruled up for the page's sake alone.
REUSE = 0.0

# Weight on the caption-fit term. Heavier than REUSE: a panel that cannot hold
# its words is a worse fault than one that has to be drawn again.
TEXT = 1.2


def lay(shape, avail_w, avail_h, gutter, weights=None):
    """Cells for one row-structure, tiling the live area exactly."""
    weights = list(weights or [1.0] * len(shape))
    free = avail_h - gutter * (len(shape) - 1)
    heights = [free * w / sum(weights) for w in weights]

    out = []
    y = B.MARGIN + avail_h
    for k, h in zip(shape, heights):
        y -= h
        w = (avail_w - gutter * (k - 1)) / k
        x = B.MARGIN
        for _ in range(k):
            out.append([x, y, w, h])
            x += w + gutter
        y -= gutter
    return out


def plan_page(n, authored, avail_w, avail_h, gutter, have=None, words=None, explain=False):
    """
    Choose the row structure to DRAW to.

    The structure in the script cannot be trusted for this. It was authored
    against a solver that stretched rows to fill the page, so it happily puts two
    panels side by side in a single full-height tier — which, ruled up honestly,
    asks for a 0.31 panel. That is not a panel, it is a slot, and specifying art
    at that shape would bake the original mistake into the artwork itself.

    So every structure is generated and scored on the shapes it asks the artist
    for: panels inside the readable band cost nothing, and anything outside is
    penalised by how far outside it falls, measured in log space so a 3.0 and a
    0.33 are equally wrong. The authored structure wins ties, because when it is
    workable the script's pacing should stand.
    """
    # ⚠️ NORMALISE THE AUTHORED STRUCTURE TO A TUPLE.
    # `shapes` below are built as tuples, while `authored` arrives from script JSON as a LIST,
    # and in Python (1,2,3) != [1,2,3]. So the "authored structure wins ties" rule in the
    # ranking key below could never fire -- not once, for any page, in any book. Every page
    # silently took the planner's single favourite structure for its panel count, which is why
    # a 75-page issue came out with 88% of its pages sharing one shape. Measured after the fix:
    # all six zero-cost six-panel structures ([1,2,3] [1,3,2] [2,1,3] [2,3,1] [3,1,2] [3,2,1])
    # are honoured when authored.
    if authored is not None:
        authored = tuple(authored)

    shapes = []

    def walk(left, acc):
        if left == 0:
            shapes.append(tuple(acc))
            return
        for k in range(1, min(3, left) + 1):
            acc.append(k)
            walk(left - k, acc)
            acc.pop()

    walk(n, [])

    import itertools
    import math

    def cost(shape, weights):
        c = 0.0
        for i, (x, y, w, h) in enumerate(
                lay(shape, avail_w, avail_h, gutter, weights)):
            a = w / h
            if a < ASPECT_FLOOR:
                c += (math.log(ASPECT_FLOOR / a)) ** 2
            elif a > ASPECT_CEIL:
                c += (math.log(a / ASPECT_CEIL)) ** 2

            # Prefer a shape the art on disk can already fill. Two structures can
            # both be good pages; if one of them also means the panel does not
            # have to be drawn again, that is the one to specify. This is what
            # keeps the spec from calling for eighty-odd redraws when half the
            # book is a 7% adjustment away from fitting.
            if have and i < len(have) and have[i]:
                c += REUSE * (math.log(a / have[i])) ** 2

            # A cell also has to hold its caption. Three panels abreast is a
            # fine tier for three wordless beats and a bad one for three
            # hundred-character captions, which is how page 5 ended up with its
            # narration in columns two words wide. The planner is told what each
            # beat has to say so it can rule the page around the words as well
            # as the pictures.
            if words and i < len(words) and words[i]:
                if w < words[i]:
                    c += TEXT * (math.log(words[i] / w)) ** 2
        # Aspect sanity alone drives every page to the same answer: stack
        # everything full width and each panel lands at a comfortable 1.9. Legal,
        # and forty-three pages of it reads like a slideshow. A page wants a
        # change of rhythm in it — one tier that breaks into two or three against
        # tiers that run the full measure — so a structure whose rows are all the
        # same width pays a small penalty. It only ever decides ties; a shape
        # that asks for an unreadable panel still loses on the band cost above.
        if len(set(shape)) == 1 and len(shape) > 1:
            c += 0.03
        return c

    def weightings(k):
        """Tier-height patterns worth trying for a k-tier page."""
        if k == 1:
            return [(1.0,)]
        out = []
        for combo in itertools.product(WEIGHTS, repeat=k):
            if max(combo) / min(combo) > WEIGHT_SPREAD:
                continue
            out.append(combo)
        return out

    ranked = []
    best, best_c = None, None
    for shape in shapes:
        for weights in weightings(len(shape)):
            c = cost(shape, weights)
            ranked.append((c, shape, weights))
            # Equal tiers win ties, so a page only gains a dominant panel when
            # that genuinely serves the art rather than by numerical accident.
            #
            # ⚠️ COST IS BANDED, not compared exactly. With round(c, 6) the
            # "authored wins ties" rule never fired -- two structures had to cost
            # the same to six decimals -- so EVERY authored structure was
            # overridden and every six-panel page in the book came out as
            # (1,2,3). Measured: [3,3], [2,2,2], [3,1,2] and [1,3,2] were all
            # discarded in favour of the same single winner, which is precisely
            # the uniform-page problem the layout profiles exist to solve.
            # Banding says: when two structures are within STRUCTURE_TOL of each
            # other they are equally good ruled-up pages, so let the author's
            # pacing decide. Structures that genuinely ask for unreadable
            # slivers are far worse than the band and still lose.
            key = (round(c / STRUCTURE_TOL), len(set(weights)) > 1,
                   shape != authored, len(shape))
            if best_c is None or key < best_c:
                best, best_c = (shape, weights), key
    if explain:
        ranked.sort(key=lambda t: t[0])
        return best, ranked
    return best


def solve_target(rows, avail_w, avail_h, gutter, have=None, words=None):
    """Cells for a page, on the structure it should have been ruled up on."""
    authored = tuple(len(r) for r in rows)
    n = sum(authored)
    shape, weights = plan_page(n, authored, avail_w, avail_h, gutter, have, words)
    return lay(shape, avail_w, avail_h, gutter, weights), shape


def apply_bleed(cell, edges, ri, ci, n_rows, n_cols):
    """
    Grow a cell off the trim on any edge it bleeds from. Bleeding art has to be
    DRAWN oversize — an edge that runs off the page needs the extra 0.125in of
    bleed plus the margin it crosses, or the printer's guillotine takes picture
    the artist meant to keep.
    """
    x, y, w, h = cell
    if isinstance(edges, str):
        edges = [edges]
    edges = edges or []
    facing = {"left": ci == 0, "right": ci == n_cols - 1,
              "top": ri == 0, "bottom": ri == n_rows - 1}
    b = B.BLEED

    if facing["left"] and "left" in edges:
        w += x + b
        x = -b
    if facing["right"] and "right" in edges:
        w = B.PAGE_W + b - x
    if facing["bottom"] and "bottom" in edges:
        h += y + b
        y = -b
    if facing["top"] and "top" in edges:
        h = B.PAGE_H + b - y
    return x, y, w, h


def collect(doc):
    avail_w = B.PAGE_W - 2 * B.MARGIN
    specs = {}
    plans = {}

    for pg in doc["pages"]:
        avail_h = B.PAGE_H - 2 * B.MARGIN
        if B.is_act(pg):
            avail_h -= B.ACT_BAND_H

        if pg.get("type") == "splash":
            # A splash is the whole sheet plus bleed on all four sides.
            bx, by, bw, bh = -B.BLEED, -B.BLEED, \
                B.PAGE_W + 2 * B.BLEED, B.PAGE_H + 2 * B.BLEED
            specs[pg["panel"]["file"]] = dict(
                page=pg["page"], role="splash", bleed=["all"],
                w_in=bw / INCH, h_in=bh / INCH)
            continue

        flat = [p for row in pg["rows"] for p in row]
        have = []
        for p in flat:
            f = os.path.join(HERE, "panels", p["file"])
            have.append(B.art_aspect(f) if os.path.exists(f) else None)
        words = [B.text_width(p) for p in flat]
        cells, shape = solve_target(pg["rows"], avail_w, avail_h, B.GUTTER,
                                    have, words)

        plans[pg["page"]] = shape

        i = 0
        for ri, k in enumerate(shape):
            for ci in range(k):
                panel = flat[i]
                x, y, w, h = apply_bleed(cells[i], panel.get("bleed"),
                                         ri, ci, len(shape), k)
                specs[panel["file"]] = dict(
                    page=pg["page"],
                    role="%d of %d in tier %d/%d" % (ci + 1, k,
                                                     ri + 1, len(shape)),
                    bleed=panel.get("bleed") or [],
                    w_in=w / INCH, h_in=h / INCH)
                i += 1
    return specs, plans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=os.path.join(HERE, "script_issue04.json"))
    ap.add_argument("--prompts", default=os.path.join(HERE, "panel_prompts.json"))
    ap.add_argument("--sheet", default=os.path.join(HERE, "spec_panels.md"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    B.register_fonts()
    with open(args.script, encoding="utf-8") as fh:
        doc = json.load(fh)

    specs, plans = collect(doc)

    panels_dir = os.path.join(HERE, "panels")
    rows_out = []
    for name, s in sorted(specs.items(),
                          key=lambda kv: (kv[1]["page"], kv[0])):
        w, h = px(s["w_in"]), px(s["h_in"])
        target = w / float(h)

        have = ""
        p = os.path.join(panels_dir, name)
        if os.path.exists(p):
            a = B.art_aspect(p)
            have = "%.2f" % a
            s["current_aspect"] = round(a, 3)
            # How much of a correctly drawn panel the current file can cover.
            s["covers"] = round(min(a, target) / max(a, target), 3)

        s.update(target_aspect=round(target, 3),
                 target_ratio=ratio(target),
                 target_px=[w, h],
                 target_in=[round(s["w_in"], 3), round(s["h_in"], 3)],
                 dpi=DPI)
        del s["w_in"], s["h_in"]
        rows_out.append((name, s, have))

    # ---- human-readable sheet ------------------------------------------
    lines = [
        "# PARADISE — panel dimension spec",
        "",
        "Trim %.4f x %.4f in, bleed %.3f in, live area %.3f x %.3f in (%.3f:1)."
        % (B.PAGE_W / INCH, B.PAGE_H / INCH, B.BLEED / INCH,
           (B.PAGE_W - 2 * B.MARGIN) / INCH, (B.PAGE_H - 2 * B.MARGIN) / INCH,
           (B.PAGE_W - 2 * B.MARGIN) / (B.PAGE_H - 2 * B.MARGIN)),
        "",
        "Pixel sizes are at %d DPI, the press standard. Anything smaller prints"
        " soft; the current art is 1280px wide, which lands near 210 DPI."
        % DPI,
        "",
        "`covers` is the fraction of the target cell the CURRENT file can fill"
        " without distortion — the rest is either empty page or lost to crop.",
        "",
        "| panel | page | position | target | pixels @%dDPI | bleed | now | covers |"
        % DPI,
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, s, have in rows_out:
        lines.append("| `%s` | %s | %s | %s (%.2f) | %d x %d | %s | %s | %s |" % (
            name, s["page"], s["role"], s["target_ratio"], s["target_aspect"],
            s["target_px"][0], s["target_px"][1],
            ",".join(s["bleed"]) or "—", have or "—",
            ("%.0f%%" % (100 * s["covers"])) if "covers" in s else "—"))

    sheet = "\n".join(lines) + "\n"

    if args.dry_run:
        print(sheet)
        return

    with open(args.sheet, "w", encoding="utf-8") as fh:
        fh.write(sheet)

    # ---- fold into the prompt pack -------------------------------------
    with open(args.prompts, encoding="utf-8") as fh:
        prompts = json.load(fh)

    hit = 0
    for entry in prompts:
        s = specs.get(entry.get("file"))
        if not s:
            continue
        entry["target_aspect"] = s["target_aspect"]
        entry["target_ratio"] = s["target_ratio"]
        entry["target_px"] = s["target_px"]
        entry["target_in"] = s["target_in"]
        entry["dpi"] = s["dpi"]
        entry["page"] = s["page"]
        entry["position"] = s["role"]
        if s["bleed"]:
            entry["bleed_edges"] = s["bleed"]
            entry["bleed_note"] = (
                "runs off the trim — keep all subject matter %0.2fin inside "
                "the bleeding edge" % (B.BLEED / INCH * 2))
        hit += 1

    with open(args.prompts, "w", encoding="utf-8") as fh:
        json.dump(prompts, fh, indent=2, ensure_ascii=False)

    # Stamp the target back onto the script too. The builder uses it as the
    # fallback for art that does not exist yet, so a placeholder build previews
    # the finished pages instead of a 16:9 guess.
    for pg in doc["pages"]:
        # Splash pages keep their panel under "panel", not in "rows". Stamping
        # only the grid panels left every splash without a target, so the
        # builder fell back to its declared shape — LANDSCAPE — and drew a 1.78
        # band across the middle of a 0.66 page with black above and below. A
        # splash is the one panel that must fill the sheet.
        for panel in ([pg["panel"]] if pg.get("panel") else []) + \
                     [p for row in pg.get("rows", []) for p in row]:
            s = specs.get(panel["file"])
            if s:
                panel["target_aspect"] = s["target_aspect"]
                panel["target_px"] = s["target_px"]

        # Write the planned tier structure back as the page's rows, and mark the
        # page planned so the builder stops re-deriving one.
        #
        # Two planners disagreeing is worse than either alone. This module rules
        # the page up around the art it is asking for; the builder rules it up
        # around the art that exists. While the two are out of step — which is
        # the whole of the period before the new panels are drawn — the builder
        # was overriding tiers this module had deliberately chosen, and page 6
        # lost the top third of itself to a three-across tier the builder
        # refused to keep. The plan is the drawing brief, so the plan wins.
        shape = plans.get(pg["page"])
        if shape:
            flat = [p for row in pg["rows"] for p in row]
            rows, i = [], 0
            for k in shape:
                rows.append(flat[i:i + k])
                i += k
            pg["rows"] = rows
            pg["planned"] = True
    with open(args.script, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)

    under = [n for n, s, _ in rows_out if s.get("covers", 1) < 0.9]
    print("wrote %s" % os.path.basename(args.sheet))
    print("annotated %d of %d prompt entries" % (hit, len(prompts)))
    print("%d panels are the wrong shape for their cell by more than 10%%:"
          % len(under))
    for n in under:
        print("   %s" % n)


if __name__ == "__main__":
    main()
