#!/usr/bin/env python
"""
SHADOW GASP comic builder.

Reads script_issue02.json + the panel art in ../panels and lays out a print-shaped
comic PDF: cover, title page, story pages (grids + splashes) with caption boxes,
speech/thought/broadcast balloons and SFX lettering, then back matter + back cover.

    python build_comic.py                      # build with defaults
    python build_comic.py --script other.json  # different issue
    python build_comic.py --guides             # draw layout guides for proofing

Missing art does not stop the build — the panel renders as a marked placeholder so
you can proof lettering and layout before the art regen lands.
"""

import argparse
import io
import json
import os
import shutil
import sys
import textwrap

from PIL import Image
from reportlab.lib.colors import Color, black, white
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import frontback as FB
import lettering as LT

HERE = os.path.dirname(os.path.abspath(__file__))

# --- page geometry (US comic trim) -----------------------------------------
#
# TRIM is the finished page. BLEED is the extra the printer cuts into, so a
# full-bleed splash has no white hairline if the guillotine wanders. Everything
# in the book is laid out in TRIM coordinates: when --bleed is on, the canvas is
# larger and the whole page is translated by one bleed, so no drawing code has to
# know the difference. Digital output stays at trim, with no marks.
TRIM_W, TRIM_H = 6.625 * inch, 10.1875 * inch
BLEED = 0.125 * inch

# The slug is the unprinted margin OUTSIDE the bleed that exists purely to hold
# the printer's marks. Without it the MediaBox stops at the bleed, the crop marks
# are drawn into the bleed itself, and the guillotine takes them off with the
# waste — which is how issue 02 shipped with marks that were both invisible
# (dark-on-black) and clipped by the page edge.
SLUG = 0.25 * inch

MARK_LEN = 0.16 * inch          # crop mark arm
MARK_GAP = BLEED + 0.03 * inch  # marks start clear of the bleed, in the slug

PAGE_W, PAGE_H = TRIM_W, TRIM_H
MARGIN = 0.30 * inch
GUTTER = 0.085 * inch

# --- palette ---------------------------------------------------------------
# Colours live in the lettering engine so covers, captions and balloons can never
# drift apart. Re-exported here for the front and back matter.
INK = LT.INK
CREAM = LT.CREAM
ACCENT = LT.ACCENT
PAPER = Color(0.09, 0.09, 0.10)        # page background behind gutters
BALLOON = LT.BALLOON
NEWSPRINT = LT.NEWSPRINT

ASPECT = {
    "LANDSCAPE": 16 / 9,
    "PORTRAIT": 3 / 4,
    "SQUARE": 1.0,
    "SPLASH": 9 / 16,
}

FONT_BODY = "Montserrat-Bold"
FONT_HEAVY = "Montserrat-ExtraBold"
FONT_SFX = "ImpactSFX"

# The resolved house lettering style. Built in main() once the page size and the
# fonts are known; every point size in the book derives from it, so a different
# trim re-proportions the whole issue instead of breaking it.
SPEC = None

# Panels that arrived with a baked-in matte and were auto-trimmed. Reported after
# the build so a recurring generator fault is visible instead of silent.
MATTED = []

# Set by --art-only. Suppresses all builder lettering for art that already has
# balloons and captions painted in.
ART_ONLY = False

# Set by --bleed. Grows the canvas, shifts the origin, and turns on crop marks.
BLEED_ON = False


def bleed_rect():
    """The full painted area — trim plus bleed on all four sides."""
    b = BLEED if BLEED_ON else 0
    return -b, -b, PAGE_W + 2 * b, PAGE_H + 2 * b


# True once to_cmyk() has run. Everything colour-literal routes through ink()
# and switches on this, so the vector layer is single-space.
PRESS = False


def ink(r, g, b, alpha=1):
    """
    A colour literal in the ACTIVE output space.

    In screen mode this is plain Color(). Under --cmyk it converts through the
    same rich-black axis the palette uses, adding undercolour in proportion to
    how dark the value is. That matters because a press PDF that mixes DeviceRGB
    and DeviceCMYK hands half the book to the RIP's own guess: the two crimsons
    end up different reds, and neutral greys drift green.
    """
    if not PRESS:
        return Color(r, g, b, alpha=alpha)

    from reportlab.lib.colors import CMYKColor
    k = 1.0 - max(r, g, b)
    if k >= 0.999:
        return CMYKColor(0.60, 0.40, 0.40, 1.00, alpha=alpha)
    c_ = (1.0 - r - k) / (1.0 - k)
    m_ = (1.0 - g - k) / (1.0 - k)
    y_ = (1.0 - b - k) / (1.0 - k)
    und = 0.55 * k          # undercolour, so darks build rich rather than flat K
    return CMYKColor(min(1.0, c_ + und), min(1.0, m_ + und * 0.72),
                     min(1.0, y_ + und * 0.68), k, alpha=alpha)


def to_cmyk():
    """
    Re-cast the palette for press.

    Two things matter and only two. First, a large area of 100% K alone prints as
    a washed grey-brown; it needs a rich black build with cyan under it. Second,
    the series crimson has to be a named ink value rather than whatever the RIP
    guesses from RGB, or it drifts between issues.

    The panel ART is deliberately left as RGB. Converting JPEGs to CMYK without an
    output profile is a guess, and a worse guess than the printer's own RIP makes
    with a real profile — so that conversion belongs at the printer, not here.
    """
    from reportlab.lib.colors import CMYKColor
    import lettering as _LT

    global PRESS
    PRESS = True

    rich_black = CMYKColor(0.60, 0.40, 0.40, 1.00)
    paper = CMYKColor(0.62, 0.45, 0.42, 0.96)
    crimson = CMYKColor(0.00, 0.86, 0.85, 0.16)
    cream = CMYKColor(0.02, 0.05, 0.16, 0.00)
    balloon = CMYKColor(0.00, 0.01, 0.04, 0.00)
    newsprint = CMYKColor(0.03, 0.07, 0.20, 0.02)

    global INK, CREAM, ACCENT, PAPER, BALLOON, NEWSPRINT
    INK = _LT.INK = rich_black
    CREAM = _LT.CREAM = cream
    ACCENT = _LT.ACCENT = crimson
    BALLOON = _LT.BALLOON = balloon
    NEWSPRINT = _LT.NEWSPRINT = newsprint
    PAPER = paper

    # frontback took its own copies of these at import time, before this ran.
    # Without this the cast page, the "what was real" spread, the floorplan and
    # the timeline all kept printing the RGB palette while the story pages used
    # the CMYK one — the same crimson as two different reds in one book.
    FB.INK = rich_black
    FB.CREAM = cream
    FB.ACCENT = crimson
    FB.NEWSPRINT = newsprint
    FB.BODY = ink(0.80, 0.78, 0.74)
    FB.DIM = ink(0.55, 0.54, 0.52)
    FB.RULE = ink(0.30, 0.29, 0.28)

    # The SFX palette is per-kind (gun / fire / glass / impact / quiet) and was
    # also built at import time. Converting it here keeps the last RGB objects
    # out of the press file — a fire SFX is the one place a wrong colour space
    # shows immediately, because that orange is at the edge of CMYK gamut.
    for kind in _LT.SFX_KINDS.values():
        for key in ("fill", "outline", "halo"):
            col = kind.get(key)
            if col is not None and hasattr(col, "red"):
                kind[key] = ink(col.red, col.green, col.blue,
                                alpha=getattr(col, "alpha", 1))

# Placement resolution for panel art. 300 is press standard; anything above it is
# weight in the file that no printer can use.
TARGET_DPI = 300

# Placement JPEG quality. 85 is the usual print/screen compromise.
JPEG_QUALITY = 85


# --- Panel-sizing helpers, used by spec_panels ------------------------------
#
# spec_panels.py was ported into pipeline_lib yesterday from the Heaven's Gate case dir, but
# these four symbols it calls through `B.` were left behind, so the new "Fit panel sizes to the
# page layout" step raised AttributeError on its first real run. Copied verbatim from
# cases/heavens-gate/build_comic.py, which is the version that actually built an 80-page book.

# How wide a panel's lettering may demand. Past MAX_TEXT_W the caption is the page's problem,
# not the layout's.
MIN_TEXT_W = 2.00 * inch
MAX_TEXT_W = 3.60 * inch

# Characters of house caption per inch of caption box. Calibrated at four lines, not six: at
# five panels to the page the cells are small, and a caption that technically fits in eight
# narrow lines still swallows the picture underneath it.
CHARS_PER_INCH = 60.0

_ASPECT_CACHE = {}


def text_len(panel):
    n = len(panel.get("caption") or "") + len(panel.get("caption2") or "")
    for item in panel.get("dialogue", []):
        # Scripts differ: some author dialogue as {"speaker":.., "text":..}, others as a bare
        # string. Measuring the words should not care which.
        n += len(item if isinstance(item, str) else (item.get("text") or ""))
    return n


def text_width(panel):
    """Width this panel's lettering wants, clamped to something sane."""
    n = text_len(panel)
    if not n:
        return 0.0
    return max(MIN_TEXT_W, min(MAX_TEXT_W, n / CHARS_PER_INCH * inch))


def art_aspect(path, fallback=16 / 9):
    """Trimmed art aspect, cached.

    The matte trim happens before the aspect crop, so solving against the raw file size
    mis-sizes every panel that arrived matted.
    """
    if path in _ASPECT_CACHE:
        return _ASPECT_CACHE[path]
    a = fallback
    if os.path.exists(path):
        try:
            img = Image.open(path).convert("RGB")
            body, _, _ = LT.trim_border(img)
            a = body.width / float(body.height)
        except Exception:
            a = fallback
    _ASPECT_CACHE[path] = a
    return a


def register_fonts():
    # Two callers, two layouts. build_comic normally runs from a case dir that the workflow has
    # copied fonts/ into, so HERE/fonts is right. But spec_panels imports this module straight
    # out of pipeline_lib/ BEFORE that copy step happens, and pipeline_lib/fonts does not exist
    # -- which killed the first real end-to-end run of the daily pipeline at "Fit panel sizes to
    # the page layout". Search the repo root as well rather than requiring the copy first.
    candidates = [
        os.path.join(HERE, "fonts"),
        os.path.join(os.path.dirname(HERE), "fonts"),
        os.path.join(os.getcwd(), "fonts"),
    ]
    pairs = [
        (FONT_BODY, "Montserrat-Bold.ttf"),
        (FONT_HEAVY, "Montserrat-ExtraBold.ttf"),
        (FONT_SFX, "Impact.ttf"),
    ]
    for name, fn in pairs:
        path = next((os.path.join(d, fn) for d in candidates
                     if os.path.exists(os.path.join(d, fn))), None)
        if path is None:
            sys.exit("missing font: %s (looked in: %s)" % (fn, ", ".join(candidates)))
        pdfmetrics.registerFont(TTFont(name, path))

    # ReportLab opens every page with a preamble that selects its base font, and
    # the default base font is Helvetica — one of the 14 "standard" faces it
    # never embeds. Nothing in this book is SET in Helvetica, but the reference
    # alone put an unembedded font on all 24 pages, which most printers fail at
    # preflight. Repointing the base font at an embedded face removes it.
    from reportlab import rl_config
    rl_config.canvas_basefontname = FONT_BODY

    # The face *stressed words* set in. See lettering.split_emphasis.
    LT.EMPH_FONT = FONT_HEAVY


# --- text helpers ----------------------------------------------------------
# Typography lives in the lettering engine; these are thin aliases for the front
# and back matter, which set plain text rather than lettering.

def wrap_to_width(text, font, size, max_w):
    return LT.wrap(text, font, size, max_w)


# --- drawing primitives ----------------------------------------------------

def draw_panel_image(c, path, x, y, w, h):
    """
    Center-crop the art to the cell aspect so nothing is stretched.

    Returns (ok, cropped_image, crop_box, orig_size) so the lettering pass can map
    speaker anchors through the same crop and read the art's busyness.
    """
    if not os.path.exists(path):
        c.setFillColor(ink(0.18, 0.18, 0.20))
        c.rect(x, y, w, h, stroke=0, fill=1)
        c.setFillColor(ink(0.55, 0.55, 0.58))
        c.setFont(FONT_BODY, 7)
        c.drawCentredString(x + w / 2, y + h / 2 + 4, "ART PENDING")
        c.setFont(FONT_BODY, 5)
        c.drawCentredString(x + w / 2, y + h / 2 - 6, os.path.basename(path))
        return False, None, None, None

    img = Image.open(path).convert("RGB")
    orig_w, orig_h = img.size

    # Two crops happen here: the matte trim, then the aspect crop. `speaker_at` is
    # authored against the ORIGINAL file, so the two are composed into one box in
    # original coordinates — otherwise every trimmed panel's tails drift.
    body, (tl, tt, _, _), trimmed = LT.trim_border(img)
    if trimmed:
        MATTED.append(os.path.basename(path))

    iw, ih = body.size
    l, t, r, b = LT.crop_box_for(iw, ih, w / h)
    cropped = body.crop((l, t, r, b))

    # Placing art at source resolution put 113 MB into a 20-page book. Nothing
    # above the target DPI can print, so resample down to it. The lettering pass
    # keeps the full-size crop — its busyness map wants the detail.
    placed = cropped
    max_px = int(w / 72.0 * TARGET_DPI)
    if placed.width > max_px:
        placed = placed.resize(
            (max_px, max(int(placed.height * max_px / placed.width), 1)),
            Image.LANCZOS)

    # Hand ReportLab JPEG bytes rather than a PIL image: given a PIL object it
    # re-encodes the bitmap losslessly (Flate) and the 20-page book lands at
    # 113 MB. JPEG is passed straight through to the PDF instead.
    buf = io.BytesIO()
    placed.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True,
                progressive=False)
    buf.seek(0)
    c.drawImage(ImageReader(buf), x, y, w, h, mask=None)
    return True, cropped, (tl + l, tt + t, tl + r, tt + b), (orig_w, orig_h)


def draw_panel_border(c, x, y, w, h, style="rule"):
    """
    Panel borders carry meaning. Sixteen pages of one identical black rule is the
    visual equivalent of reading in a monotone.

        rule    the house border — the default, and most of the book
        none    borderless; the art sits straight on the black page. For the
                interior beats, where the frame would only get in the way.
        jagged  a torn, broken outline for the violence. Drawn as a perturbed
                rectangle so no two are identical.
        heavy   a thick keyline, for the panel a page turns on.
    """
    if style == "none":
        return

    if style == "jagged":
        import random
        rng = random.Random(int(x * 7 + y * 13 + w * 3 + h))
        j = min(w, h) * 0.018
        pts = []
        for x0, y0, x1, y1, n in ((x, y, x + w, y, 9), (x + w, y, x + w, y + h, 7),
                                  (x + w, y + h, x, y + h, 9), (x, y + h, x, y, 7)):
            for i in range(n):
                t = i / float(n)
                pts.append((x0 + (x1 - x0) * t + rng.uniform(-j, j),
                            y0 + (y1 - y0) * t + rng.uniform(-j, j)))
        p = c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        p.close()
        c.setStrokeColor(INK)
        c.setLineWidth(2.2)
        c.drawPath(p, stroke=1, fill=0)
        return

    c.setStrokeColor(INK)
    c.setLineWidth(3.4 if style == "heavy" else 1.6)
    c.rect(x, y, w, h, stroke=1, fill=0)


# --- page layout -----------------------------------------------------------

ACT_BAND_H = 0.34 * inch       # slim act banner above a grid page
SAFE = 0.22 * inch             # keep type this far off the trim on bleed pages


def page_bg(c):
    # Painted one bleed oversize in every direction so the page colour itself
    # reaches the cut, not just the art on top of it.
    b = BLEED if BLEED_ON else 0
    c.setFillColor(PAPER)
    c.rect(-b, -b, PAGE_W + 2 * b, PAGE_H + 2 * b, stroke=0, fill=1)


def draw_crop_marks(c):
    """
    Printer's marks, drawn in the SLUG — outside both the trim and the bleed.

    Three things have to be true or the marks are decoration:
      * they start beyond the bleed, so they survive on the waste after the cut;
      * they sit on unpainted stock, so they are black-on-white and visible;
      * the MediaBox is big enough to contain them.

    Only emitted with --bleed. A digital PDF with crop marks hanging off the
    corners looks like a mistake; a print PDF without them gets sent back.
    """
    if not BLEED_ON:
        return
    c.setStrokeColor(ink(0, 0, 0))
    c.setLineWidth(0.4)
    for x in (0, PAGE_W):
        for y in (0, PAGE_H):
            sx = -1 if x == 0 else 1
            sy = -1 if y == 0 else 1
            c.line(x + sx * MARK_GAP, y, x + sx * (MARK_GAP + MARK_LEN), y)
            c.line(x, y + sy * MARK_GAP, x, y + sy * (MARK_GAP + MARK_LEN))


def is_act(page):
    """Pages that open an act carry the act name in `title`."""
    return str(page.get("title", "")).strip().lower().startswith("act ")


def draw_act_band(c, title, y):
    """Slim act banner: crimson rule, act name, hairline rule to the trim edge."""
    c.setFillColor(ACCENT)
    c.rect(MARGIN, y + ACT_BAND_H * 0.30, 0.26 * inch, 2.4, stroke=0, fill=1)

    c.setFillColor(NEWSPRINT)
    c.setFont(FONT_HEAVY, 10.5)
    c.drawString(MARGIN + 0.36 * inch, y + ACT_BAND_H * 0.26, title.upper())

    c.setStrokeColor(ink(0.30, 0.29, 0.28))
    c.setLineWidth(0.6)
    c.line(MARGIN, y + 0.06 * inch, PAGE_W - MARGIN, y + 0.06 * inch)


def draw_splash_title(c, title):
    """Act lockup across the foot of a full-bleed splash, over its own scrim."""
    band = 0.92 * inch
    for i in range(48):
        t = i / 48.0
        c.setFillColor(ink(0, 0, 0, alpha=0.86 * (1 - t)))
        c.rect(0, i * (band / 48), PAGE_W, band / 48 + 0.6, stroke=0, fill=1)

    c.setFillColor(ACCENT)
    c.rect(SAFE, SAFE + 0.30 * inch, 0.42 * inch, 3.0, stroke=0, fill=1)

    c.setFillColor(NEWSPRINT)
    c.setFont(FONT_HEAVY, 17)
    c.drawString(SAFE, SAFE + 0.04 * inch, title.upper())


def draw_folio(c, n, force_right=False):
    """
    Page number, bottom outer corner. Legible over art on bleed pages.

    `force_right` keeps it clear of the act lockup, which is left-aligned at the
    foot of every splash.
    """
    x = PAGE_W - MARGIN if (force_right or n % 2 == 0) else MARGIN
    y = 0.155 * inch
    c.setFillColor(ink(0, 0, 0, alpha=0.55))
    c.circle(x, y + 2.4, 8.2, stroke=0, fill=1)
    c.setFillColor(ink(0.78, 0.76, 0.72))
    c.setFont(FONT_BODY, 7.2)
    c.drawCentredString(x, y, str(n))


def render_panel(c, panel, x, y, w, h, panels_dir, missing, bleed=False,
                 overlay=None, hard=None, inset=None, tilt=0):
    """
    Letter one panel.

    Draw order is the whole trick, and it is deliberate:

        art -> border -> SFX -> captions -> balloons

    SFX is a picture element and belongs UNDER the lettering; drawing it last is
    what let BRAKKA-KRAK eat a caption on p15. Each stage reserves its footprint
    in `occupied`, so every later stage routes around everything before it, and
    lettering — the part the reader must be able to read — always wins.

    `tilt` cants the ART AND BORDER only. The lettering that follows is placed
    in unrotated page coordinates, so balloons and captions stay upright inside
    a leaning frame. That is how a canted panel is drawn by hand: the camera is
    off balance, the voice is not, and tilted type reads as a mistake.
    """
    path = os.path.join(panels_dir, panel["file"])

    if tilt:
        c.saveState()
        c.translate(x + w / 2.0, y + h / 2.0)
        c.rotate(tilt)
        c.translate(-(x + w / 2.0), -(y + h / 2.0))

    ok, cropped, box, orig = draw_panel_image(c, path, x, y, w, h)
    if not ok:
        missing.append(panel["file"])
    if not bleed:
        draw_panel_border(c, x, y, w, h, panel.get("border", "rule"))

    if tilt:
        c.restoreState()

    # Furniture that belongs UNDER the lettering — the splash scrim, act lockup
    # and folio. Drawing these after the panel put a black scrim across p8's
    # caption and dropped the folio onto the word HAPPEN. Same rule as SFX:
    # anything that is not lettering goes down before the lettering does.
    if overlay is not None:
        overlay(c)

    # --art-only: the lettering is already painted into the art (see the LETTERED
    # prompt pack), so lay out pages and skip every mark the builder would add.
    if ART_ONLY:
        return

    # The cell stays the true art rect so `speaker_at` anchors map exactly. On a
    # bleed page type must still keep off the trim, so the safe band is reserved
    # as occupied instead — along with the foot, which carries the act lockup
    # and the folio.
    cell = (x, y, w, h)
    occupied = []
    hard = hard or []

    bmap = LT.busyness(cropped) if cropped is not None else None

    # resolve every speaker anchor up front — captions need them too, so they can
    # avoid covering a face that is about to be given a balloon
    dialogue = panel.get("dialogue", [])
    anchors = []
    for item in dialogue:
        if item.get("speaker_at") and orig:
            anchors.append(LT.map_point(item["speaker_at"], box, orig[0], orig[1]))
        else:
            anchors.append(None)

    for item in panel.get("sfx", []):
        LT.draw_sfx(c, SPEC, item, cell, occupied, bmap)

    if panel.get("caption"):
        LT.draw_caption(c, SPEC, panel["caption"], cell, bmap, occupied,
                        anchors, role="open", hard=hard, inset=inset)
    if panel.get("caption2"):
        LT.draw_caption(c, SPEC, panel["caption2"], cell, bmap, occupied,
                        anchors, role="close", hard=hard, inset=inset)

    for item, anchor in zip(dialogue, anchors):
        LT.draw_balloon(c, SPEC, item, cell, bmap, anchor, occupied, hard)


def render_grid_page(c, page, panels_dir, missing):
    page_bg(c)
    avail_w = PAGE_W - 2 * MARGIN
    avail_h = PAGE_H - 2 * MARGIN

    # An act opener gives up a band of page height to the banner, so the grid
    # re-solves against the reduced space rather than overlapping it.
    band = is_act(page)
    if band:
        avail_h -= ACT_BAND_H
        draw_act_band(c, page["title"], PAGE_H - MARGIN - ACT_BAND_H)

    rows = page["rows"]

    # natural height of each row if it spanned the full width undistorted
    natural = []
    for row in rows:
        aspects = [ASPECT[p["shape"]] for p in row]
        inner_w = avail_w - GUTTER * (len(row) - 1)
        natural.append(inner_w / sum(aspects))

    total_gutter = GUTTER * (len(rows) - 1)
    scale = (avail_h - total_gutter) / sum(natural)

    # Solve the grid first, THEN let individual panels break out of it. Keeping
    # the solve honest means a broken-out page still reads in the right order —
    # the panels are where the grid put them, they have just been allowed to
    # lean, grow or run off the edge.
    placed = []
    y = MARGIN + avail_h
    for row, nat in zip(rows, natural):
        row_h = nat * scale
        y -= row_h
        aspects = [ASPECT[p["shape"]] for p in row]
        inner_w = avail_w - GUTTER * (len(row) - 1)
        x = MARGIN
        for panel, a in zip(row, aspects):
            pw = inner_w * (a / sum(aspects))
            placed.append([panel, x, y, pw, row_h])
            x += pw + GUTTER
        y -= GUTTER

    # A panel may only grow INTO SPACE IT HAS. Growing the middle panel of a
    # tight three-panel row does not make the page dynamic, it buries the panels
    # either side of it — that is what half-swallowed KLIK on page 5 and the
    # RADIO SILENCE caption on page 12. Interior edges are clamped to the
    # gutter; only an edge that faces the margin is free to run.
    idx = 0
    for ri, row in enumerate(rows):
        for ci in range(len(row)):
            p = placed[idx]
            free = (ci == 0, ri == 0, ci == len(row) - 1, ri == len(rows) - 1)
            # Recorded so the draw loop below frames the panel according to the bleed that was
            # actually applied, not the one the script asked for.
            p[0]["_bleed_applied"] = effective_bleed(p[0], free)
            p[1:] = break_out(p[0], *p[1:], free=free)
            idx += 1

    # z sorts the draw order so a grown or canted panel can sit ON TOP of its
    # neighbour instead of under it. Python's sort is stable, so equal z keeps
    # reading order.
    for panel, px, py, pw, ph in sorted(placed, key=lambda p: p[0].get("z", 0)):
        # A panel running off the trim gets no border on any side, and its
        # lettering is held inside the safe band — same rule as a splash.
        render_panel(c, panel, px, py, pw, ph, panels_dir, missing,
                     bleed=bool(panel.get("_bleed_applied")),
                     tilt=panel.get("tilt", 0))


def break_out(panel, x, y, w, h, free=(True, True, True, True)):
    """
    Let one panel escape its grid cell.

        grow   [left, top, right, bottom] as fractions of the panel's own size.
               Positive values push the panel over its gutters, which is what
               makes an overlap.
        bleed  any of "left" "right" "top" "bottom" — run that edge off the
               trim and into the bleed, so the art has no border on that side.

    `free` says which of (left, top, right, bottom) face open page rather than
    another panel. An edge that faces a neighbour may only grow by half a
    gutter — enough to kill the white line between them and read as an overlap,
    not enough to bury the panel next door.

    Both are expressed relative to the solved cell rather than in absolute
    points, so a page still recomposes if the trim changes.
    """
    g = panel.get("grow")
    if g:
        cap_w = GUTTER * 0.5 / max(w, 1.0)
        cap_h = GUTTER * 0.5 / max(h, 1.0)
        l, t, r, b = (v if f else min(v, cap)
                      for v, f, cap in zip(g, free,
                                           (cap_w, cap_h, cap_w, cap_h)))
        x, y = x - w * l, y - h * b
        w, h = w * (1 + l + r), h * (1 + t + b)

    # ⚠️ A BLEED IS SUBJECT TO `free` EXACTLY AS A GROW IS.
    #
    # This block used to run off the trim on any edge the script named, whether or not that edge
    # faced the page. "bleed": ["bottom"] on a TOP-tier panel therefore grew it to y = -BLEED --
    # straight down over every tier beneath it. Measured on the delivered Princes Gate issue: 67
    # overlapping panel pairs, most of them one panel drawn wholly inside another, plus 73
    # caption blocks straddling two panels on 26 pages, because a caption is placed relative to
    # the cell and the cell now spanned half the sheet.
    #
    # The sizing side already had this guard -- spec_panels.apply_bleed tests `facing` before
    # growing anything -- so the art was being GENERATED for the correct cell and DRAWN into a
    # bloated one. The two sides now agree.
    #
    # It is the same rule the comment above this function's caller states for grow: a panel may
    # only run into space it has. An edge that faces a neighbour is not the page edge, and
    # bleeding it is meaningless as well as destructive -- there is no trim there to run off.
    edges = effective_bleed(panel, free)
    if edges:
        b = BLEED if BLEED_ON else 0
        if "left" in edges:
            w += x + b
            x = -b
        if "right" in edges:
            w = PAGE_W + b - x
        if "bottom" in edges:
            h += y + b
            y = -b
        if "top" in edges:
            h = PAGE_H + b - y
    return [x, y, w, h]


def effective_bleed(panel, free):
    """The bleed edges that actually apply, given which of this cell's edges face the page.

    A panel that asked to bleed on an interior edge is, after this, an ordinary framed cell --
    so it must be DRAWN as one. Passing the script's raw `bleed` through to render_panel would
    suppress its border and inset its lettering for a bleed that never happened, which is how
    the fix for the geometry would have quietly become a second, subtler defect.
    """
    edges = panel.get("bleed")
    if not edges:
        return []
    if isinstance(edges, str):
        edges = [edges]
    faces = dict(zip(("left", "top", "right", "bottom"), free))
    return [e for e in edges if faces.get(e)]


def render_splash_page(c, page, panels_dir, missing, folio=None):
    """
    A splash runs to trim. Framing it inside the same margin as a grid page was
    what made the book read as a PDF of a comic rather than a comic.
    """
    page_bg(c)

    def furniture(cv):
        if page.get("title"):
            draw_splash_title(cv, page["title"])
        draw_folio(cv, folio if folio is not None else page["page"],
                   force_right=True)

    # Reserve only what is actually there: the full-width lockup band on a titled
    # splash, otherwise just the folio's corner. Blocking the whole foot of an
    # untitled page needlessly pushes captions back up into the art.
    if page.get("title"):
        hard = [(0.0, 0.86, 1.0, 1.0)]
    else:
        hard = [(0.84, 0.92, 1.0, 1.0)]

    bx, by, bw, bh = bleed_rect()
    render_panel(c, page["panel"], bx, by, bw, bh, panels_dir, missing,
                 bleed=True, overlay=furniture, hard=hard,
                 inset=(SAFE / bw, SAFE / bh))


def _outlined(c, x, y, text, font, size, fill, stroke_w=2.2,
              stroke=(0, 0, 0), shadow=None, centred=True):
    """Comic-cover lettering: heavy stroke plus an offset colour shadow.

    Plain flat type is what makes a cover read as a film poster instead of a
    comic. Trade dress on a comic logo is always outlined and offset.
    """
    draw = c.drawCentredString if centred else c.drawString
    if shadow:
        c.setFillColor(ink(*shadow))
        c.setFont(font, size)
        draw(x + stroke_w * 1.9, y - stroke_w * 1.9, text)
    c.saveState()
    c.setLineWidth(stroke_w)
    c.setStrokeColor(ink(*stroke))
    c.setFillColor(fill)
    c.setFont(font, size)
    t = c.beginText()
    t.setTextRenderMode(2)          # fill + stroke
    c.setFont(font, size)
    if centred:
        w = pdfmetrics.stringWidth(text, font, size)
        t.setTextOrigin(x - w / 2, y)
    else:
        t.setTextOrigin(x, y)
    t.setFont(font, size)
    t.textOut(text)
    c.drawText(t)
    c.restoreState()


def render_cover(c, spec, panels_dir, missing):
    page_bg(c)
    path = os.path.join(panels_dir, spec["image"])
    if not draw_panel_image(c, path, *bleed_rect())[0]:
        missing.append(spec["image"])

    ACCENT_C = ink(0.78, 0.20, 0.16)

    # top scrim so the logo always reads
    for i in range(60):
        t = i / 60.0
        c.setFillColor(ink(0, 0, 0, alpha=0.80 * (1 - t)))
        c.rect(0, PAGE_H - (i + 1) * (2.05 * inch / 60), PAGE_W, 2.05 * inch / 60 + 0.6,
               stroke=0, fill=1)
    # bottom scrim for the title block
    for i in range(50):
        t = i / 50.0
        c.setFillColor(ink(0, 0, 0, alpha=0.88 * (1 - t)))
        c.rect(0, i * (2.0 * inch / 50), PAGE_W, 2.0 * inch / 50 + 0.6, stroke=0, fill=1)

    # ---- masthead logo, outlined with a red offset ----
    _outlined(c, PAGE_W / 2, PAGE_H - 1.00 * inch, spec["logo"], FONT_HEAVY, 40,
              NEWSPRINT, stroke_w=2.6, shadow=(0.78, 0.20, 0.16))

    # ---- genre strip under the logo ----
    strip = spec.get("genre_strip", "TRUE CRIME  ·  DOCUMENTARY COMIC")
    c.setFillColor(ACCENT_C)
    c.rect(0, PAGE_H - 1.52 * inch, PAGE_W, 0.20 * inch, stroke=0, fill=1)
    c.setFillColor(ink(1, 1, 1))
    c.setFont(FONT_HEAVY, 8.4)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.465 * inch, strip)

    # ---- title, big and outlined ----
    size = 46
    while size > 22 and pdfmetrics.stringWidth(spec["title"], FONT_HEAVY, size) > PAGE_W - 1.1 * inch:
        size -= 2
    _outlined(c, PAGE_W / 2, 1.12 * inch, spec["title"], FONT_HEAVY, size,
              ink(1, 1, 1), stroke_w=2.8, shadow=(0.78, 0.20, 0.16))

    # ---- tagline in a cover-blurb bar ----
    c.setFillColor(ink(0.07, 0.07, 0.08, alpha=0.9))
    c.rect(0, 0.62 * inch, PAGE_W, 0.30 * inch, stroke=0, fill=1)
    c.setFillColor(NEWSPRINT)
    c.setFont(FONT_HEAVY, 8.6)
    c.drawCentredString(PAGE_W / 2, 0.715 * inch, spec["tagline"].upper())


def render_title_page(c, spec, meta):
    page_bg(c)
    c.setFillColor(NEWSPRINT)
    c.setFont(FONT_HEAVY, 26)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 2.5 * inch, spec["heading"])

    c.setStrokeColor(ink(0.78, 0.20, 0.16))
    c.setLineWidth(2)
    c.line(PAGE_W / 2 - 1.1 * inch, PAGE_H - 2.8 * inch,
           PAGE_W / 2 + 1.1 * inch, PAGE_H - 2.8 * inch)

    c.setFillColor(ink(0.72, 0.70, 0.66))
    y = PAGE_H - 3.3 * inch
    for line in spec["credits"]:
        c.setFont(FONT_BODY, 8)
        c.drawCentredString(PAGE_W / 2, y, line)
        y -= 13

    y -= 26
    c.setFillColor(ink(0.55, 0.54, 0.52))
    for line in wrap_to_width(spec["disclaimer"], FONT_BODY, 6.6, PAGE_W - 2.2 * inch):
        c.setFont(FONT_BODY, 6.6)
        c.drawCentredString(PAGE_W / 2, y, line)
        y -= 10

    draw_masthead(c, spec.get("masthead"), y - 0.44 * inch)
    indicia = spec.get("indicia")
    if indicia and not BLEED_ON:
        # Digital build: "PRINTED IN [COUNTRY TK]" is a print-run line and
        # means nothing on a file nobody presses onto paper. Swap it for an
        # edition line so the foot of the title page doesn't ship a bracketed
        # placeholder to a paying reader.
        indicia = [
            "DIGITAL EDITION · kianukal@theverdictcourier.com"
            if ln.startswith("PRINTED IN") else ln
            for ln in indicia
        ]
    draw_indicia(c, indicia)


def draw_masthead(c, rows, y):
    """
    Who made it — roles right-aligned into the spine, names left-aligned out of
    it, so the block reads as one column rather than two lists.

    Issue 02 credited nobody. A comic with no credits reads as either stolen or
    unfinished, and a retailer or reviewer has no name to attach to it.
    """
    if not rows:
        return

    # Names are set from a fixed gutter, so the longest one governs the size.
    # Better a point smaller than a credit running off the trim.
    size = 7.6
    room = PAGE_W / 2 - MARGIN - 0.10 * inch
    while size > 5.4 and any(
            pdfmetrics.stringWidth(n.upper(), FONT_HEAVY, size) > room
            for _, n in rows):
        size -= 0.2

    for role, name in rows:
        c.setFillColor(ACCENT)
        c.setFont(FONT_BODY, size * 0.84)
        c.drawRightString(PAGE_W / 2 - 0.10 * inch, y, role.upper())
        c.setFillColor(NEWSPRINT)
        c.setFont(FONT_HEAVY, size)
        c.drawString(PAGE_W / 2 + 0.10 * inch, y, name.upper())
        y -= size * 1.85


def draw_indicia(c, lines):
    """
    The legal furniture, set small at the foot of the title page.

    Copyright holder, year, publisher, edition, rights reservation and contact.
    It is the least glamorous block in a comic and the one whose absence stops a
    book being distributable: it is what a shop, a library and a copyright
    registry all read first.
    """
    if not lines:
        return

    # Set the block from the bottom up: wrap first, measure, then place, so a
    # longer indicia grows upward into the page instead of off the foot of it.
    wrapped = [wrap_to_width(p, FONT_BODY, 5.6, PAGE_W - 1.7 * inch)
               for p in lines]
    height = sum(len(w) * 8.0 + 3.0 for w in wrapped)
    y = MARGIN + height

    c.setStrokeColor(ink(0.26, 0.25, 0.24))
    c.setLineWidth(0.5)
    c.line(PAGE_W / 2 - 1.5 * inch, y + 0.20 * inch,
           PAGE_W / 2 + 1.5 * inch, y + 0.20 * inch)

    c.setFillColor(ink(0.46, 0.45, 0.44))
    for para in wrapped:
        for ln in para:
            c.setFont(FONT_BODY, 5.6)
            c.drawCentredString(PAGE_W / 2, y, ln)
            y -= 8.0
        y -= 3.0


# --- EAN-13 ----------------------------------------------------------------
# Encoding tables. L/G/R are the three alphabets; PARITY picks which of L or G
# each digit of the left half uses, and that choice is what encodes digit 1.

_EAN_L = ("0001101", "0011001", "0010011", "0111101", "0100011",
          "0110001", "0101111", "0111011", "0110111", "0001011")
_EAN_G = ("0100111", "0110011", "0011011", "0100001", "0011101",
          "0111001", "0000101", "0010001", "0001001", "0010111")
_EAN_R = tuple("".join("01"[ch == "0"] for ch in code) for code in _EAN_L)
_EAN_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
               "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")


def ean13_checksum(d12):
    s = sum(int(n) * (3 if i % 2 else 1) for i, n in enumerate(d12))
    return (10 - s % 10) % 10


def ean13_modules(code):
    """Return the 95-module bit string for a 12- or 13-digit EAN-13."""
    code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(code) == 12:
        code += str(ean13_checksum(code))
    if len(code) != 13:
        raise ValueError("EAN-13 needs 12 or 13 digits, got %d" % len(code))
    if int(code[12]) != ean13_checksum(code[:12]):
        raise ValueError("EAN-13 check digit is wrong for %s" % code)

    bits = "101"
    for i, ch in enumerate(code[1:7]):
        bits += (_EAN_L if _EAN_PARITY[int(code[0])][i] == "L" else _EAN_G)[int(ch)]
    bits += "01010"
    for ch in code[7:]:
        bits += _EAN_R[int(ch)]
    return bits + "101", code


def draw_barcode_block(c, spec, x, y, w, h):
    """
    Retail furniture: the barcode field, price and rating.

    Given `isbn` (or `upc`) in the back-cover spec this draws a real, scannable
    EAN-13 with a correct check digit and the standard quiet zones. Without one
    it draws an empty reserved field marked ISBN TK.

    It deliberately does NOT draw decorative bars when the number is missing.
    Issue 02 shipped with a random bar field captioned "EAN-13 · placeholder";
    that is worse than an empty box, because a bar field that cannot scan still
    looks finished enough to get signed off and sent to print.
    """
    c.setFillColor(ink(1, 1, 1))
    c.rect(x, y, w, h, stroke=0, fill=1)

    code = spec.get("isbn") or spec.get("upc")
    bars_y = y + h * 0.26
    bars_h = h * 0.60

    if code:
        try:
            bits, full = ean13_modules(code)
        except ValueError as exc:
            sys.exit("back_cover barcode: %s" % exc)

        # Quiet zones are part of the symbol, not padding: 11 modules leading,
        # 7 trailing. A barcode printed edge to edge in its box will not scan.
        mod = w / (95 + 11 + 7.0)
        bx = x + 11 * mod
        c.setFillColor(ink(0, 0, 0))
        for i, bit in enumerate(bits):
            if bit == "1":
                # guard bars run longer, under the digit line
                guard = i < 3 or i >= 92 or 45 <= i < 50
                c.rect(bx + i * mod, bars_y - (h * 0.10 if guard else 0),
                       mod, bars_h + (h * 0.10 if guard else 0),
                       stroke=0, fill=1)

        c.setFont(FONT_BODY, 5.2)
        c.drawString(x + 1.5 * mod, y + h * 0.06, full[0])
        c.drawCentredString(x + (11 + 25) * mod, y + h * 0.06, full[1:7])
        c.drawCentredString(x + (11 + 70) * mod, y + h * 0.06, full[7:])
    else:
        c.setStrokeColor(ink(0.62, 0.62, 0.62))
        c.setLineWidth(0.6)
        c.setDash(2, 2)
        c.rect(x + w * 0.06, bars_y, w * 0.88, bars_h, stroke=1, fill=0)
        c.setDash()
        c.setFillColor(ink(0.35, 0.35, 0.35))
        c.setFont(FONT_HEAVY, 6.0)
        c.drawCentredString(x + w / 2, bars_y + bars_h / 2 - 2, "ISBN TK")
        c.setFont(FONT_BODY, 4.4)
        c.drawCentredString(x + w / 2, y + h * 0.09,
                            "set back_cover.isbn to print")

    c.setFillColor(ink(0.55, 0.54, 0.52))
    c.setFont(FONT_HEAVY, 8.4)
    c.drawRightString(x - 0.14 * inch, y + h - 9, spec.get("price", ""))
    c.setFont(FONT_BODY, 6.0)
    c.drawRightString(x - 0.14 * inch, y + h - 20, spec.get("rating", ""))


def render_back_cover(c, spec):
    page_bg(c)
    c.setFillColor(NEWSPRINT)
    c.setFont(FONT_HEAVY, 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 2.2 * inch, spec["logo"])

    # ⚠️ WRAP IT. This split on "\n" and drew each piece as one centred line, which is only a
    # wrap if something upstream inserted the newlines -- and nothing can. gen_case_script's
    # JSON-validity rules explicitly forbid literal newlines inside string values (a stray one
    # breaks the whole generation), so spec["quote"] is ALWAYS a single line by construction and
    # this loop could never once have wrapped anything. The Princes Gate back cover drew its
    # hook 487pt wide on a 477pt page, clipped off both edges mid-word.
    #
    # The blurb twelve lines below already wraps through LT.wrap against real glyph widths. The
    # display line just never used it.
    c.setFillColor(ink(1, 1, 1))
    y = PAGE_H / 2 + 0.4 * inch
    quote = " ".join(spec["quote"].split())
    measure = PAGE_W - 2.4 * inch          # same centred column as the blurb
    # Step the display size down rather than let a long hook march into the blurb beneath it.
    for size in (15, 13.5, 12, 10.5):
        lines = LT.wrap(quote, FONT_HEAVY, size, measure)
        if len(lines) <= 4:
            break
    for line in lines:
        c.setFont(FONT_HEAVY, size)
        c.drawCentredString(PAGE_W / 2, y, line)
        y -= size * 1.6

    # crimson rule, so the lower third is composed rather than simply empty
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.6)
    c.line(PAGE_W / 2 - 0.9 * inch, y - 0.16 * inch,
           PAGE_W / 2 + 0.9 * inch, y - 0.16 * inch)

    if spec.get("blurb"):
        y -= 0.46 * inch
        c.setFillColor(ink(0.72, 0.70, 0.66))
        for ln in LT.wrap(spec["blurb"], FONT_BODY, 7.6, PAGE_W - 2.4 * inch):
            c.setFont(FONT_BODY, 7.6)
            c.drawCentredString(PAGE_W / 2, y, ln)
            y -= 11.6

    bw, bh = 1.30 * inch, 0.72 * inch
    bx, by = PAGE_W - MARGIN - bw, MARGIN + 0.10 * inch
    if BLEED_ON:
        # Print run: a shop needs the scan field, real or reserved.
        draw_barcode_block(c, spec, bx, by, bw, bh)
    else:
        # Digital-only release: there is nothing to scan and no ISBN to
        # reserve space for, so there is no barcode furniture at all — just
        # the price and age rating, set as plain text.
        c.setFillColor(ink(0.55, 0.54, 0.52))
        c.setFont(FONT_HEAVY, 8.4)
        c.drawRightString(bx + bw, by + bh - 9, spec.get("price", ""))
        c.setFont(FONT_BODY, 6.0)
        c.drawRightString(bx + bw, by + bh - 20, spec.get("rating", ""))

    c.setFillColor(ink(0.55, 0.54, 0.52))
    c.setFont(FONT_BODY, 7)
    c.drawString(MARGIN, MARGIN + 0.52 * inch, spec["footer"])
    if spec.get("publisher"):
        c.setFillColor(NEWSPRINT)
        c.setFont(FONT_HEAVY, 8.4)
        c.drawString(MARGIN, MARGIN + 0.72 * inch, spec["publisher"].upper())


def set_page_boxes(path, off):
    """
    Stamp TrimBox / BleedBox / ArtBox onto every page.

    A press PDF that carries only a MediaBox is telling the printer the page is
    the whole painted sheet — it has no way to know where the finished page is,
    so imposition is a guess and every preflight profile flags it. The geometry
    is already known here exactly, so declare it:

        MediaBox  trim + bleed + slug   (everything, including the marks)
        BleedBox  trim + bleed          (paint to here)
        TrimBox   the finished page     (cut to here)
        ArtBox    == TrimBox

    Written after c.save() with pypdf so it does not depend on which ReportLab
    version is installed.
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject

    r = PdfReader(path)
    w = PdfWriter()
    trim = RectangleObject([off, off, off + PAGE_W, off + PAGE_H])
    bleed = RectangleObject([off - BLEED, off - BLEED,
                             off + PAGE_W + BLEED, off + PAGE_H + BLEED])
    for pg in r.pages:
        pg.trimbox = trim
        pg.artbox = trim
        pg.bleedbox = bleed
        w.add_page(pg)
    w.add_metadata(r.metadata or {})
    with open(path, "wb") as fh:
        w.write(fh)


def archive_existing(out):
    """
    Never overwrite a build. Any existing PDF at `out` is moved into versions/
    with the next free version number before the new one is written, so the
    previous book is always still on disk.
    """
    if not os.path.exists(out):
        return None

    vdir = os.path.join(os.path.dirname(out) or ".", "versions")
    os.makedirs(vdir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(out))

    n = 1
    while os.path.exists(os.path.join(vdir, "%s_v%02d%s" % (stem, n, ext))):
        n += 1
    dest = os.path.join(vdir, "%s_v%02d%s" % (stem, n, ext))

    shutil.move(out, dest)
    print("archived previous build -> versions/%s" % os.path.basename(dest))
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=os.path.join(HERE, "script_issue02.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--art-only", action="store_true",
                    help="skip all builder lettering — for art that already has "
                         "balloons and captions painted in")
    ap.add_argument("--bleed", action="store_true",
                    help="press build: 0.125in bleed on all four sides plus crop "
                         "marks. Omit for the digital/screen PDF.")
    ap.add_argument("--cmyk", action="store_true",
                    help="press build: rich-black and named-ink palette for the "
                         "vector layer. Panel art stays RGB for the printer's RIP.")
    args = ap.parse_args()

    register_fonts()

    global SPEC, ART_ONLY, BLEED_ON
    ART_ONLY = args.art_only
    BLEED_ON = args.bleed
    if args.cmyk:
        to_cmyk()
    SPEC = LT.Spec(PAGE_W, PAGE_H, FONT_BODY, FONT_SFX)

    with open(args.script, encoding="utf-8") as fh:
        doc = json.load(fh)

    # Resolve against the SCRIPT, not this module.
    #
    # HERE is pipeline_lib/, and this builder historically ran as a copy sitting inside the case
    # directory, so HERE and the case dir were the same place. Running it from pipeline_lib made
    # every data path point into the library folder instead: panels were looked for in
    # pipeline_lib/panels and the finished PDF was written to pipeline_lib/, which is why
    # Gumroad then failed with "could not stat file: cases/<slug>/<TITLE>_issue01.pdf".
    # The script's own directory is the case directory by definition, so anchor there.
    base = os.path.dirname(os.path.abspath(args.script))
    panels_dir = os.path.normpath(os.path.join(base, doc.get("panels_dir", "../panels")))
    out = args.out or os.path.join(base, doc.get("output", "comic.pdf"))

    archive_existing(out)

    b = BLEED if BLEED_ON else 0
    s = SLUG if BLEED_ON else 0
    off = b + s
    c = canvas.Canvas(out, pagesize=(PAGE_W + 2 * off, PAGE_H + 2 * off))
    c.setTitle("%s — Issue %s: %s" % (doc["series"], doc["issue_no"], doc["title"]))
    c.setAuthor(doc["series"])
    c.setCreator("%s comic builder" % doc["series"])
    c.setSubject(doc.get("subject",
                         "The 1980 Iranian Embassy siege and Operation Nimrod."))
    c.setKeywords(doc.get("keywords",
                          "Shadow Gasp, Operation Nimrod, Iranian Embassy siege, "
                          "SAS, 1980, London, true crime, comic"))

    missing = []
    g = sys.modules[__name__]

    # Folios are PHYSICAL position, not the editorial page number in the script.
    # Adding the cast page shifted every story page by one; the script keeps its
    # own 3-18 numbering so it still lines up with SHOT_LIST_AND_ARRANGEMENT.txt,
    # and the build report prints the mapping between the two.
    folio = [1]
    editorial = []

    def page(draw, folio_after=True):
        """
        Render one page inside the bleed transform.

        The origin is shifted per page rather than once after each showPage:
        translating after the FINAL showPage leaves marks on the canvas and
        ReportLab flushes an extra blank page for them, which is how the 24-page
        book came out of the press build as 25.
        """
        c.saveState()
        if off:
            c.translate(off, off)
        draw()
        draw_crop_marks(c)          # marks last, so nothing paints over them
        c.restoreState()
        c.showPage()
        if folio_after:
            folio[0] += 1

    def foliated(fn):
        n = folio[0]

        def draw():
            fn()
            draw_folio(c, n)
        return draw

    page(lambda: render_cover(c, doc["cover"], panels_dir, missing))
    page(lambda: render_title_page(c, doc["title_page"], doc))

    if doc.get("cast_page"):
        page(foliated(lambda: FB.render_cast_page(
            c, g, doc["cast_page"], panels_dir)))

    for sp in doc["pages"]:
        editorial.append((folio[0], sp["page"]))
        if sp["type"] == "splash":
            # splashes draw their own folio under the lettering, via `furniture`
            page(lambda sp=sp, n=folio[0]: render_splash_page(
                c, sp, panels_dir, missing, folio=n))
        else:
            page(foliated(lambda sp=sp: render_grid_page(
                c, sp, panels_dir, missing)))

    bm_pages = int(doc["back_matter"].get("pages", 2))
    for i in range(bm_pages):
        page(foliated(lambda i=i: FB.render_back_matter(
            c, g, doc["back_matter"], i, bm_pages)))

    if doc.get("floorplan"):
        page(foliated(lambda: FB.render_floorplan(c, g, doc["floorplan"])))

    if doc.get("timeline"):
        page(foliated(lambda: FB.render_timeline(c, g, doc["timeline"])))

    page(lambda: render_back_cover(c, doc["back_cover"]))

    c.save()
    if BLEED_ON:
        set_page_boxes(out, off)
    total = folio[0] - 1

    n_panels = 1 + sum(
        1 if p["type"] == "splash" else sum(len(r) for r in p["rows"])
        for p in doc["pages"]
    )
    print("built: %s" % out)
    print("pages: %d   panels referenced: %d" % (total, n_panels))
    if total % 4:
        print("NOTE - %d pages is not a multiple of 4; printers impose in "
              "signatures of four. Nearest clean count: %d."
              % (total, total + (4 - total % 4)))
    if editorial:
        drift = [(f, e) for f, e in editorial if f != e]
        if drift:
            print("folio -> script page: %s"
                  % ", ".join("%d=p%02d" % (f, e) for f, e in drift[:4]) +
                  (" ..." if len(drift) > 4 else ""))
    if missing:
        print("MISSING ART (%d) -> rendered as placeholders:" % len(missing))
        for m in missing:
            print("   " + m)
    else:
        print("all panel art present")

    # `title` prints on act openers and on splashes. On an interior grid page it is
    # an editorial label only — say so, so nobody assumes it reaches the page.
    silent = [p["page"] for p in doc["pages"]
              if p.get("title") and p["type"] != "splash" and not is_act(p)]
    if silent:
        print("page titles held as editorial labels (not printed): %s"
              % ", ".join("p%02d" % n for n in silent))

    if MATTED:
        print("auto-trimmed a baked-in matte from %d panel(s):" % len(MATTED))
        for m in sorted(set(MATTED)):
            print("   " + m)


if __name__ == "__main__":
    main()
