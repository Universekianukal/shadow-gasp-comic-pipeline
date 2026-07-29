#!/usr/bin/env python
"""
Front and back matter for the SHADOW GASP line.

Everything here is comprehension scaffolding rather than story: the cast page a
new reader needs before page one, the building the siege happens inside, and the
six days laid end to end. All three are drawn from data in the script file, and
all three are the reason a reader who knows nothing about 1980 can follow this.

The cast page takes its portraits from panel art you already have — a focus point
per entry, cropped square at build time. No new generation.
"""

import io
import os

from PIL import Image
from reportlab.lib.colors import Color
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

import lettering as LT

INK = LT.INK
CREAM = LT.CREAM
ACCENT = LT.ACCENT
NEWSPRINT = LT.NEWSPRINT

BODY = Color(0.80, 0.78, 0.74)
DIM = Color(0.55, 0.54, 0.52)
RULE = Color(0.30, 0.29, 0.28)


# ----------------------------------------------------------------- helpers --

def _heading(c, g, text, standfirst=None):
    """House page head: crimson tick, title, hairline, optional standfirst."""
    y = g.PAGE_H - 1.00 * inch
    c.setFillColor(ACCENT)
    c.rect(g.MARGIN, y + 0.30 * inch, 0.42 * inch, 3.0, stroke=0, fill=1)

    c.setFillColor(NEWSPRINT)
    c.setFont(g.FONT_HEAVY, 20)
    c.drawString(g.MARGIN, y, text.upper())

    y -= 0.16 * inch
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.6)
    c.line(g.MARGIN, y, g.PAGE_W - g.MARGIN, y)

    if standfirst:
        y -= 0.20 * inch
        c.setFillColor(DIM)
        for ln in LT.wrap(standfirst, g.FONT_BODY, 7.2, g.PAGE_W - 2 * g.MARGIN):
            c.setFont(g.FONT_BODY, 7.2)
            c.drawString(g.MARGIN, y, ln)
            y -= 10
    return y - 0.18 * inch


def _portrait(c, g, path, focus, x, y, side):
    """
    Square crop of an existing panel, centred on a focus point.

    The focus is in the ORIGINAL image's coordinates (0-1, origin top-left), the
    same space `speaker_at` uses, so a point picked off one document works in the
    other. Falls back to a marked placeholder when the art is not there yet.
    """
    if not os.path.exists(path):
        c.setFillColor(g.ink(0.18, 0.18, 0.20))
        c.rect(x, y, side, side, stroke=0, fill=1)
        c.setFillColor(g.ink(0.45, 0.45, 0.48))
        c.setFont("Montserrat-Bold", 5)
        c.drawCentredString(x + side / 2, y + side / 2, os.path.basename(path))
    else:
        img = Image.open(path).convert("RGB")
        body, _, _ = LT.trim_border(img)
        iw, ih = body.size
        s = min(iw, ih)
        fx, fy = focus
        l = min(max(int(iw * fx - s / 2), 0), iw - s)
        t = min(max(int(ih * fy - s / 2), 0), ih - s)
        crop = body.crop((l, t, l + s, t + s))

        px = int(side / 72.0 * 300)
        if crop.width > px:
            crop = crop.resize((px, px), Image.LANCZOS)
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=85, optimize=True)
        buf.seek(0)
        c.drawImage(ImageReader(buf), x, y, side, side, mask=None)

    c.setStrokeColor(INK)
    c.setLineWidth(1.6)
    c.rect(x, y, side, side, stroke=1, fill=0)
    c.setFillColor(ACCENT)
    c.rect(x, y - 3.0, side, 3.0, stroke=0, fill=1)


# ------------------------------------------------------------- cast page --

def render_cast_page(c, g, spec, panels_dir):
    """
    Six faces, one line each. The single highest-leverage page in the book — and
    the first comics page the reader sees, so it cannot look like a contents
    list.

    The first version stacked six identical squares down the left margin with
    text to the right of each: six rows of the same shape, read once and
    skipped. This one alternates the portrait side, cants each frame a couple of
    degrees, and gives the first entry a larger plate, so the page reads as a
    pinned-up dossier rather than a table. Same data, same file, no new art.
    """
    g.page_bg(c)
    y = _heading(c, g, spec["heading"], spec.get("standfirst"))

    entries = spec["entries"]
    avail = y - g.MARGIN - 0.30 * inch
    # Fill the page. Solve the repeat size from the space actually left
    # rather than capping it at a guess — the first pass left an inch of
    # dead paper at the foot, which is what makes a page look unfinished.
    gap_y = 0.15 * inch
    lead = 1.62 * inch
    n = max(len(entries) - 1, 1)
    side = min(1.30 * inch,
               (avail - lead - gap_y * len(entries)) / n)

    for i, e in enumerate(entries):
        s = lead if i == 0 else side
        left = (i % 2 == 0)                  # alternate the portrait side
        px = g.MARGIN if left else g.PAGE_W - g.MARGIN - s
        top = y

        # A couple of degrees, alternating, deterministic per row. Enough to
        # read as pinned to a board; not enough to look like a mistake.
        tilt = (-2.4, 1.8, -1.5, 2.2, -2.0, 1.4)[i % 6]
        c.saveState()
        c.translate(px + s / 2.0, top - s / 2.0)
        c.rotate(tilt)
        c.translate(-(px + s / 2.0), -(top - s / 2.0))
        _portrait(c, g, os.path.join(panels_dir, e["file"]), e["focus"],
                  px, top - s, s)
        c.restoreState()

        tx = (g.MARGIN + s + 0.22 * inch) if left else g.MARGIN
        tw = g.PAGE_W - g.MARGIN - s - 0.22 * inch - g.MARGIN
        ty = top - 0.15 * inch

        c.setFillColor(ACCENT)
        c.rect(tx, ty + 0.21 * inch, 0.20 * inch, 2.2, stroke=0, fill=1)

        c.setFillColor(NEWSPRINT)
        c.setFont(g.FONT_HEAVY, 12 if i == 0 else 10)
        c.drawString(tx, ty, e["name"].upper())

        ty -= 0.115 * inch
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(tx, ty, tx + tw, ty)

        ty -= 0.155 * inch
        c.setFillColor(BODY)
        size = 8.0 if i == 0 else 7.2
        for ln in LT.wrap(e["line"], g.FONT_BODY, size, tw):
            c.setFont(g.FONT_BODY, size)
            c.drawString(tx, ty, ln)
            ty -= size * 1.42

        y = top - s - gap_y


# ------------------------------------------------------------- floor plan --

def render_floorplan(c, g, spec):
    """
    A cutaway section, not a plan.

    This story moves vertically — the team comes down from the roof and in from
    the balcony while the hostages are driven upward — so a section reads the
    beats in the order they happen. A flat plan cannot show that.
    """
    g.page_bg(c)
    y = _heading(c, g, spec["heading"], spec.get("standfirst"))

    floors = spec["floors"]
    beats = spec["beats"]

    # The section and its key have to share the page, so size the storeys from
    # what is actually left rather than from a fixed number that leaves half the
    # page empty.
    key_h = 0.30 * inch + 0.24 * inch * len(beats)
    bw = 2.60 * inch                       # building width
    bx = (g.PAGE_W - bw) / 2
    top = y - 0.16 * inch
    fh = max(min((top - key_h - 0.90 * inch) / len(floors), 1.02 * inch),
             0.62 * inch)
    bottom = top - fh * len(floors)

    # ground line
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(g.MARGIN, bottom - 0.14 * inch, g.PAGE_W - g.MARGIN, bottom - 0.14 * inch)

    for i, f in enumerate(floors):
        fy = top - fh * (i + 1)
        c.setFillColor(g.ink(0.15, 0.15, 0.17))
        c.rect(bx, fy, bw, fh, stroke=0, fill=1)
        c.setStrokeColor(g.ink(0.42, 0.41, 0.39))
        c.setLineWidth(1.0)
        c.rect(bx, fy, bw, fh, stroke=1, fill=0)

        # sash windows, so the section reads as the same building as the art
        if f["name"] != "ROOF":
            for k in range(4):
                wx = bx + bw * (0.12 + 0.24 * k)
                c.setFillColor(g.ink(0.24, 0.25, 0.28))
                c.rect(wx, fy + fh * 0.28, bw * 0.13, fh * 0.44, stroke=0, fill=1)
        else:
            for k in range(3):
                cx = bx + bw * (0.20 + 0.30 * k)
                c.setFillColor(g.ink(0.26, 0.24, 0.22))
                c.rect(cx, fy + fh * 0.52, bw * 0.09, fh * 0.40, stroke=0, fill=1)

        c.setFillColor(NEWSPRINT)
        c.setFont(g.FONT_HEAVY, 6.4)
        c.drawString(bx + 4, fy + fh - 9, f["name"])
        c.setFillColor(DIM)
        c.setFont(g.FONT_BODY, 5.6)
        c.drawString(bx + 4, fy + 5, f["note"])

    # the black front door, so the section reads as the building on page 4
    door_i = next((i for i, f in enumerate(floors)
                   if f["name"] == "GROUND FLOOR"), len(floors) - 2)
    dy = top - fh * (door_i + 1) + fh * 0.22   # clear of the floor's note line
    c.setFillColor(g.ink(0.06, 0.06, 0.07))
    c.rect(bx + bw * 0.45, dy, bw * 0.10, fh * 0.46, stroke=0, fill=1)

    # Numbered beat markers. Several beats share a floor — the execution and the
    # body on the steps are both GROUND on the right — so markers on the same
    # floor and side fan outward instead of stacking on top of each other.
    lanes = {}
    for b in beats:
        lanes.setdefault((b["floor"], b["side"]), []).append(b)
    for (fl, side), group in lanes.items():
        fy0 = top - fh * (fl + 0.5)
        for k, b in enumerate(group):
            off = (k - (len(group) - 1) / 2.0) * 0.19 * inch
            mx = (bx - 0.20 * inch - abs(off)) if side == "L" \
                else (bx + bw + 0.20 * inch + abs(off))
            fy = fy0 + off
            c.setFillColor(ACCENT)
            c.circle(mx, fy, 6.4, stroke=0, fill=1)
            c.setFillColor(g.ink(1, 1, 1))
            c.setFont(g.FONT_HEAVY, 6.4)
            c.drawCentredString(mx, fy - 2.2, str(b["n"]))
            # leader line back to the wall it refers to
            c.setStrokeColor(ACCENT)
            c.setLineWidth(0.7)
            if side == "L":
                c.line(mx + 6.4, fy, bx, fy0)
            else:
                c.line(mx - 6.4, fy, bx + bw, fy0)

    # the key runs below the section, where there is room to set it properly
    ky = bottom - 0.40 * inch
    for b in sorted(beats, key=lambda z: z["n"]):
        c.setFillColor(ACCENT)
        c.circle(g.MARGIN + 6.2, ky + 2.2, 6.2, stroke=0, fill=1)
        c.setFillColor(g.ink(1, 1, 1))
        c.setFont(g.FONT_HEAVY, 6.4)
        c.drawCentredString(g.MARGIN + 6.2, ky, str(b["n"]))

        c.setFillColor(BODY)
        tx = g.MARGIN + 0.26 * inch
        for ln in LT.wrap(b["text"], g.FONT_BODY, 7.0, g.PAGE_W - g.MARGIN - tx):
            c.setFont(g.FONT_BODY, 7.0)
            c.drawString(tx, ky, ln)
            ky -= 9.8
        ky -= 5.0


# --------------------------------------------------------------- timeline --

def render_timeline(c, g, spec):
    """Six days end to end, so the shape of the siege is visible at a glance."""
    g.page_bg(c)
    y = _heading(c, g, spec["heading"], spec.get("standfirst"))

    days = spec["days"]
    x0 = g.MARGIN + 0.90 * inch
    avail = y - 1.00 * inch

    # Give each day height in proportion to what happened in it. An even split
    # left five near-empty bands and crushed 5 May, which is the day the book is
    # actually about — the shape of the siege should be visible in the spacing.
    weights = [1.0 + 0.62 * len(d["events"]) for d in days]
    unit = avail / sum(weights)
    steps = [w * unit for w in weights]

    # the spine
    c.setStrokeColor(RULE)
    c.setLineWidth(1.2)
    c.line(x0, y - 0.10 * inch, x0, y - avail - 0.05 * inch)

    ty = y - 0.24 * inch
    for i, d in enumerate(days):
        last = i == len(days) - 1

        c.setFillColor(ACCENT if last else g.ink(0.42, 0.41, 0.39))
        c.circle(x0, ty + 2.4, 5.0 if last else 3.4, stroke=0, fill=1)

        c.setFillColor(NEWSPRINT if last else BODY)
        c.setFont(g.FONT_HEAVY, 8.0)
        c.drawRightString(x0 - 0.16 * inch, ty, d["label"])

        ey = ty
        for ev in d["events"]:
            c.setFillColor(BODY if last else DIM)
            for ln in LT.wrap(ev, g.FONT_BODY, 7.0,
                              g.PAGE_W - g.MARGIN - (x0 + 0.20 * inch)):
                c.setFont(g.FONT_BODY, 7.0)
                c.drawString(x0 + 0.20 * inch, ey, ln)
                ey -= 9.8
            ey -= 2.0

        ty -= steps[i]


# ------------------------------------------------------------ back matter --

def render_back_matter(c, g, spec, page_index, total_pages):
    """
    WHAT WAS REAL, paginated.

    One page of 7.6pt grey at legal-notice density was the densest thing in the
    book, aimed at exactly the readers least likely to squint through it. The same
    words now run across two pages with a subhead per beat.
    """
    g.page_bg(c)

    paras = [p for p in spec["lines"] if p.strip()]
    per = (len(paras) + total_pages - 1) // total_pages
    mine = paras[page_index * per:(page_index + 1) * per]

    head = spec["heading"] if page_index == 0 else spec["heading"] + " (CONT.)"
    y = _heading(c, g, head,
                 spec.get("standfirst") if page_index == 0 else None)

    max_w = g.PAGE_W - 2 * g.MARGIN
    for j, para in enumerate(mine):
        if j:
            c.setStrokeColor(RULE)
            c.setLineWidth(0.5)
            c.line(g.MARGIN, y + 0.13 * inch, g.PAGE_W - g.MARGIN, y + 0.13 * inch)

        # "THE SIEGE. Six gunmen seized..." — the lead clause is a subhead.
        head_txt, _, rest = para.partition(". ")
        if rest and len(head_txt) < 34 and head_txt.upper() == head_txt:
            c.setFillColor(ACCENT)
            c.setFont(g.FONT_HEAVY, 9.0)
            c.drawString(g.MARGIN, y, head_txt.upper())
            y -= 16
        else:
            rest = para

        c.setFillColor(BODY)
        for ln in LT.wrap(rest, g.FONT_BODY, 9.0, max_w):
            c.setFont(g.FONT_BODY, 9.0)
            c.drawString(g.MARGIN, y, ln)
            y -= 14.4
        y -= 18

    if page_index == total_pages - 1:
        y -= 4
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(g.MARGIN, y, g.PAGE_W - g.MARGIN, y)
        y -= 0.34 * inch
        y = _sources(c, g, spec.get("sources"), y)


def _sources(c, g, sources, y):
    """
    The reading list.

    A true-crime book that asserts "this is what really happened" and then cites
    nothing is asking to be taken on trust. This is also the cheapest way to earn
    the cover price: the back of the book is where a reader decides whether the
    front of it was serious. It doubles as the answer to "where did you get
    this?" when a reviewer asks.
    """
    if not sources:
        return y

    c.setFillColor(ACCENT)
    c.setFont(g.FONT_HEAVY, 9.0)
    c.drawString(g.MARGIN, y, "PRINCIPAL SOURCES")
    y -= 0.14 * inch

    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(g.MARGIN, y, g.PAGE_W - g.MARGIN, y)
    y -= 0.20 * inch

    max_w = g.PAGE_W - 2 * g.MARGIN - 0.16 * inch
    for src in sources:
        c.setFillColor(ACCENT)
        c.rect(g.MARGIN, y + 2.4, 0.07 * inch, 2.0, stroke=0, fill=1)
        c.setFillColor(DIM)
        for k, ln in enumerate(LT.wrap(src, g.FONT_BODY, 7.4, max_w)):
            c.setFont(g.FONT_BODY, 7.4)
            c.drawString(g.MARGIN + 0.16 * inch, y, ln)
            y -= 10.6
        y -= 4.6
    return y
