"""
SHADOW GASP lettering engine  —  "noir prestige caps" house style.

One module owns every mark that is not art: caption boxes, balloons, SFX, and the
placement logic that keeps them off each other and off the art.

Three ideas hold it together:

1. SPEC — every size, weight and inset is derived from the page trim width via
   `Spec`, so the same book lays out correctly at any trim (comic, magazine,
   digest, webtoon strip) and every issue in the line looks identical.

2. MEASURE, NOT PERCENT — text blocks are sized to a target character count the
   way a letterer works, not to a fraction of the panel. That is what stops a
   two-word balloon from becoming a lozenge next to a wide one.

3. ONE OCCUPANCY MODEL — SFX, captions and balloons all reserve normalized rects
   in a single `occupied` list and all avoid it, in that order. Nothing can be
   drawn over anything else, including tails.

Coordinates: panel-normalized (0-1) with origin TOP-LEFT, converted to ReportLab
points (origin bottom-left) only at the moment of drawing.
"""

import math
import re

import numpy as np
from PIL import Image
from reportlab.lib.colors import Color, black
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics

# ------------------------------------------------------------------ palette --

INK = Color(0.06, 0.06, 0.07)          # borders and lettering
BALLOON = Color(0.97, 0.96, 0.93)      # balloon stock
CREAM = Color(0.937, 0.902, 0.824)     # caption stock
ACCENT = Color(0.78, 0.20, 0.16)       # series crimson
NEWSPRINT = Color(0.85, 0.80, 0.70)    # SFX fill

# The trim the house style was drawn at. Everything scales off this.
REF_TRIM_W = 6.625 * inch


class Spec:
    """
    The house lettering style, resolved for one page size.

    Point sizes, rules and insets are all `REF * scale`, so changing the trim
    changes nothing about how the page reads.
    """

    def __init__(self, page_w, page_h, font_body, font_sfx):
        self.page_w = page_w
        self.page_h = page_h
        self.scale = page_w / REF_TRIM_W
        self.font = font_body
        self.font_sfx = font_sfx

        s = self.scale

        # -- captions ------------------------------------------------------
        self.cap_size_max = 8.0 * s
        self.cap_size_min = 5.6 * s
        self.cap_measure = 34             # target characters per line
        self.cap_leading = 1.26
        self.cap_track = 0.4 * s          # letter-spacing, points
        self.cap_pad_x = 5.2 * s
        self.cap_pad_y = 4.4 * s
        self.cap_rule = 0.9 * s           # border weight
        self.cap_shadow = 2.0 * s         # hard offset shadow
        self.cap_accent = 2.4 * s         # crimson spine on the leading edge
        self.cap_inset = 9.0 * s          # gap from the panel border
        self.cap_w_max = 0.60             # never wider than this share of panel
        self.cap_w_min = 0.34
        self.cap_h_max = 0.34             # never taller than this share of panel

        # -- balloons ------------------------------------------------------
        self.bal_size_max = 8.6 * s
        self.bal_size_min = 5.8 * s
        self.bal_measure = 19             # target characters per line
        self.bal_leading = 1.20
        self.bal_track = 0.3 * s
        self.bal_ratio = 2.05             # ideal text-block width:height
        # Slack around the text block, on top of the sqrt(2) an ellipse needs to
        # circumscribe a rectangle. 1.20 on top of 1.414 inflated every balloon to
        # 1.7x its own text, which is most of why they swallowed the small panels.
        self.bal_pad = 1.06
        self.bal_rule = 2.30 * s
        # NOTE these are SEMI-axes, so the drawn balloon is twice each figure.
        # 0.42/0.30 therefore allowed a balloon 84% of the panel wide and 60% of
        # it tall — which is how the three short panels on p11 ended up almost
        # entirely covered, with the hostages invisible behind the whisper.
        self.bal_a_min = 0.085            # min semi-axis, share of panel width
        self.bal_a_max = 0.36             # -> 72% of panel width
        self.bal_b_max = 0.24             # -> 48% of panel height

        # The real guard. Width and height caps are independent, so a balloon can
        # satisfy both and still swallow a short, wide panel. An ellipse may not
        # cover more than this share of the panel's area, whatever its proportion;
        # the text is re-set smaller until it complies.
        self.bal_area_max = 0.24
        self.bal_area_min_panel = 0.30    # tiny panels get a little more slack
        self.bal_tail_hw = 2.6 * s        # tail base HALF-width — absolute, see below
        self.bal_tail_hw_max = 4.4 * s

        # How far a tail actually travels toward the mouth. A tail drawn the whole
        # distance lands ON the speaker: across p07's foreheads, into the mouth of
        # the officer on p13 like a skewer. A real comic tail covers a third to a
        # half of the gap and stops in open air — it indicates a direction, it does
        # not connect two objects. Reach is a fraction of the gap, then clamped so
        # a balloon far from its speaker cannot grow a spear.
        self.bal_tail_reach = {"speech": 0.42, "whisper": 0.42,
                               "thought": 0.55, "broadcast": 0.50}
        self.bal_tail_max = 30.0 * s      # absolute ceiling on tail length
        self.bal_tail_min = 7.0 * s       # below this it reads as a nub, not a tail

        # -- sfx -----------------------------------------------------------
        self.sfx_outline = 0.05           # outline weight as a share of size
        self.sfx_h_max = 0.42             # cap height as a share of panel height
        self.sfx_drift = 0.22             # how far off its authored pos it may move

    # -- typography ------------------------------------------------------

    def avg_char(self, size):
        """Average advance width of the body face at `size`, in points."""
        sample = "THE QUICK BROWN FOX JUMPS OVER A LAZY DOG"
        return pdfmetrics.stringWidth(sample, self.font, size) / len(sample)


# ------------------------------------------------------------------- text --

# --------------------------------------------------------------- emphasis --
#
# Comics bold the stressed word. It is not decoration — it is where the actor's
# stress goes, and a page of balloons set in one flat weight reads as a page of
# people talking in a monotone. Issue 02 had no emphasis anywhere in it.
#
# Markup is *asterisks*, set in the heavy face. EMPH_FONT is filled in by the
# builder once the fonts are registered; until then emphasis degrades silently
# to plain text rather than crashing a build.

EMPH_FONT = None

_EMPH_RE = re.compile(r"\*([^*]+)\*")


def _with_alpha(col, alpha):
    """The same colour, same colour space, at a new alpha."""
    try:
        return col.clone(alpha=alpha)
    except AttributeError:
        return Color(col.red, col.green, col.blue, alpha=alpha)


def _normalise_emphasis(text):
    """`*NO DEAL*` -> `*NO* *DEAL*`, so a stressed phrase survives word wrap."""
    return _EMPH_RE.sub(
        lambda m: " ".join("*%s*" % w for w in m.group(1).split()), text)


def split_emphasis(s):
    """Split a string into [(run, is_emphasised), ...]."""
    out, i = [], 0
    for m in _EMPH_RE.finditer(s):
        if m.start() > i:
            out.append((s[i:m.start()], False))
        out.append((m.group(1), True))
        i = m.end()
    if i < len(s):
        out.append((s[i:], False))
    return out or [(s, False)]


def strip_emphasis(s):
    """The text as the reader sees it, markers removed."""
    return _EMPH_RE.sub(r"\1", s)


def emph_width(s, font, size, track=0.0):
    """Width of a marked-up string, each run measured in the face it is set in."""
    total, n = 0.0, 0
    for run, em in split_emphasis(s):
        f = EMPH_FONT if (em and EMPH_FONT) else font
        total += pdfmetrics.stringWidth(run, f, size)
        n += len(run)
    return total + track * max(n - 1, 0)


def wrap(text, font, size, max_w, track=0.0):
    """Greedy word wrap against real glyph widths, tracking included."""
    def width(s):
        return emph_width(s, font, size, track)

    text = _normalise_emphasis(text)
    words = text.split()
    if not words:
        return []
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if width(trial) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def block_width(lines, font, size, track=0.0):
    if not lines:
        return 0.0
    return max(emph_width(l, font, size, track) for l in lines)


def fit_block(text, spec, size_max, size_min, measure, leading, track,
              max_w, max_h):
    """
    Set `text` at the largest size that keeps it inside (max_w, max_h) while
    staying near the target `measure` in characters.

    Returns (size, lines, width, height).
    """
    size = size_max
    while size >= size_min:
        # the letterer's measure, clamped to what the box actually allows
        w = min(measure * spec.avg_char(size), max_w)
        lines = wrap(text, spec.font, size, w, track)
        h = len(lines) * size * leading
        if h <= max_h and block_width(lines, spec.font, size, track) <= max_w:
            return size, lines, block_width(lines, spec.font, size, track), h
        size -= 0.25

    size = size_min
    lines = wrap(text, spec.font, size, max_w, track)
    return (size, lines, block_width(lines, spec.font, size, track),
            len(lines) * size * leading)


def fit_balloon_block(text, spec, max_w, max_h):
    """
    Set balloon text, choosing the wrap measure that lands the block closest to
    `spec.bal_ratio`. Uniform block proportion is what makes a page of balloons
    look like one letterer set them.
    """
    size = spec.bal_size_max
    while size >= spec.bal_size_min:
        best = None
        # try measures around the target, widest first
        for chars in range(spec.bal_measure + 8, 5, -1):
            w = min(chars * spec.avg_char(size), max_w)
            lines = wrap(text, spec.font, size, w, spec.bal_track)
            bw = block_width(lines, spec.font, size, spec.bal_track)
            bh = len(lines) * size * spec.bal_leading
            if bw > max_w or bh > max_h:
                continue
            cost = abs((bw / bh) - spec.bal_ratio)
            if best is None or cost < best[0]:
                best = (cost, lines, bw, bh)
        if best:
            return size, best[1], best[2], best[3]
        size -= 0.25

    size = spec.bal_size_min
    lines = wrap(text, spec.font, size, max_w, spec.bal_track)
    return (size, lines, block_width(lines, spec.font, size, spec.bal_track),
            len(lines) * size * spec.bal_leading)


def draw_lines(c, spec, lines, size, leading, track, x, y_top, align="left",
               color=INK):
    """
    Draw a set line block. `y_top` is the top of the block, in points.

    Tracking is a text-object property in ReportLab, not a canvas one, so each
    block is drawn through its own text object. Centred lines are positioned by
    hand because the tracked width is wider than `stringWidth` reports.
    """
    ty = y_top - size * 0.92
    for ln in lines:
        w = emph_width(ln, spec.font, size, track)
        lx = x - w / 2 if align == "center" else x

        # One text object per line, but the font is switched mid-run so a
        # stressed word sets in the heavy face without breaking the tracking or
        # the baseline.
        t = c.beginText(lx, ty)
        t.setCharSpace(track)
        t.setFillColor(color)
        for run, em in split_emphasis(ln):
            t.setFont(EMPH_FONT if (em and EMPH_FONT) else spec.font, size)
            t.textOut(run)
        c.drawText(t)
        ty -= size * leading


# --------------------------------------------------------------- geometry --

def trim_border(img, max_frac=0.12, flat=9.0, tol=14.0):
    """
    Strip a flat, baked-in border from generated art.

    Image generators intermittently return a panel matted inside a frame
    (`p14_4.jpg` shipped with one). Left alone it reads as a printing error in
    the middle of the page, so every panel is checked on the way in.

    The matte tone is READ FROM THE CORNERS rather than assumed. The first
    version of this only recognised near-white (>244) or near-black (<11)
    borders, so it walked straight past the cream ~219 letterbox bars on
    p05_1 / p04_2 / p05_5 and the cream pillarbox on p09_3 — which is why issue
    02 printed with a pale bar across the top of the Thatcher panel. A line is
    trimmed only when it is genuinely uniform AND matches a corner tone, and
    never more than `max_frac` of a side, so real art is still never touched.
    """
    a = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = a.shape

    # Candidate matte tones: the four corners. A real panel's corners disagree
    # with each other, so a matte only survives as a candidate if a whole edge
    # line is flat at that value too.
    corners = (a[0, 0], a[0, -1], a[-1, 0], a[-1, -1])

    def flat_line(line):
        if line.std() >= flat:
            return False
        m = line.mean()
        return any(abs(m - t) <= tol for t in corners)

    def run(get, limit):
        n = 0
        while n < limit and flat_line(get(n)):
            n += 1
        return n

    t = run(lambda i: a[i], int(h * max_frac))
    b = run(lambda i: a[h - 1 - i], int(h * max_frac))
    l = run(lambda i: a[:, i], int(w * max_frac))
    r = run(lambda i: a[:, w - 1 - i], int(w * max_frac))

    def paired(n, m):
        """
        A matte is a LETTERBOX: it appears on both opposing sides at roughly the
        same thickness. A flat run on one side only is almost always real art —
        a night sky, a wall, a pool of shadow. Requiring the pair is what stops
        this from taking 331px of ceiling off the top of p01_splash and 56px of
        wall off the side of p09_1, which a one-sided test happily did.
        """
        if n == 0 or m == 0:
            return 0, 0
        if abs(n - m) > max(3, 0.5 * max(n, m)):
            return 0, 0
        return n, m

    t, b = paired(t, b)
    l, r = paired(l, r)
    top, bottom, left, right = t, h - b, l, w - r

    if (left, top, right, bottom) == (0, 0, w, h):
        return img, (0, 0, w, h), False
    return img.crop((left, top, right, bottom)), (left, top, right, bottom), True


def crop_box_for(iw, ih, target_aspect, vbias=0.40):
    """Center-crop box (l, t, r, b) that makes iw:ih match target_aspect."""
    cur = iw / ih
    if cur > target_aspect:
        new_w = int(ih * target_aspect)
        off = (iw - new_w) // 2
        return (off, 0, off + new_w, ih)
    if cur < target_aspect:
        new_h = int(iw / target_aspect)
        off = int((ih - new_h) * vbias)
        return (0, off, iw, off + new_h)
    return (0, 0, iw, ih)


def map_point(pt, box, iw, ih):
    """Point in ORIGINAL image space (0-1, top-left) -> cropped panel space."""
    l, t, r, b = box
    x = (pt[0] * iw - l) / max(r - l, 1)
    y = (pt[1] * ih - t) / max(b - t, 1)
    return (min(max(x, 0.02), 0.98), min(max(y, 0.02), 0.98))


def _overlap(r1, r2):
    """Area of intersection of two normalized rects, 0 if disjoint."""
    x0 = max(r1[0], r2[0])
    y0 = max(r1[1], r2[1])
    x1 = min(r1[2], r2[2])
    y1 = min(r1[3], r2[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _pt_seg_dist(p, a, b):
    """Shortest distance from point `p` to segment a-b."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 1e-12:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _seg_hits_rect(p, q, rect, samples=14):
    """Cheap segment/rect test — used to stop a tail crossing a caption box."""
    x0, y0, x1, y1 = rect
    for i in range(samples + 1):
        t = i / samples
        sx = p[0] + (q[0] - p[0]) * t
        sy = p[1] + (q[1] - p[1]) * t
        if x0 <= sx <= x1 and y0 <= sy <= y1:
            return True
    return False


# ----------------------------------------------------------- busyness map --

def busyness(img, grid=56):
    """Downsampled edge-energy map. High = detailed art (faces, debris, crowds)."""
    g = img.convert("L").resize((grid, grid), Image.BILINEAR)
    a = np.asarray(g, dtype=np.float32) / 255.0
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    e = np.sqrt(gx * gx + gy * gy)
    k = np.ones((3, 3), dtype=np.float32) / 9.0
    pad = np.pad(e, 1, mode="edge")
    out = np.zeros_like(e)
    for dy in range(3):
        for dx in range(3):
            out += pad[dy:dy + grid, dx:dx + grid] * k[dy, dx]
    m = out.max()
    return out / m if m > 0 else out


def box_cost(bmap, rect):
    """Mean art detail under a normalized rect. 0 = flat sky, 1 = maximum noise."""
    if bmap is None:
        return 0.0
    g = bmap.shape[0]
    xa, xb = int(rect[0] * g), max(int(rect[2] * g), int(rect[0] * g) + 1)
    ya, yb = int(rect[1] * g), max(int(rect[3] * g), int(rect[1] * g) + 1)
    xa, ya = max(xa, 0), max(ya, 0)
    xb, yb = min(xb, g), min(yb, g)
    if xb <= xa or yb <= ya:
        return 1.0
    return float(bmap[ya:yb, xa:xb].mean())


# ------------------------------------------------------------- caption box --

# Candidate anchors, with a reading-order bias. Comics read top-left first, so a
# narration box costs nothing there and progressively more as it moves away.
#
# The mid-height slots are not decoration. With the top row taken by `caption`
# and the foot reserved for an act lockup, a splash carrying `caption2` has
# nowhere legal to go and lands back on top of `caption` — which is exactly what
# p8 did. Six slots is not enough; eight is.
_CAP_SLOTS = [
    #  key            ax    ay    open-bias  close-bias
    ("tl",           0.0,  0.0,   0.0,       30.0),
    ("tc",           0.5,  0.0,   7.0,       26.0),
    ("tr",           1.0,  0.0,  11.0,       22.0),
    ("ml",           0.0,  0.5,  17.0,       17.0),
    ("mr",           1.0,  0.5,  20.0,       14.0),
    ("bl",           0.0,  1.0,  26.0,        6.0),
    ("bc",           0.5,  1.0,  30.0,        3.0),
    ("br",           1.0,  1.0,  34.0,        0.0),
]


def place_caption(spec, cw, ch, bmap, occupied, anchors, role="open", hard=(),
                  inset=None):
    """
    Pick the caption slot: quiet art, out of the way of speakers, and as close to
    reading order as the panel allows. Returns (rect, key).
    """
    best, best_key, best_score = None, None, 1e9

    # How far every slot sits in from the panel edge. On a full-bleed page the
    # caller passes the trim safe area here — as an INSET, not as a `hard` rect.
    # Modelling the safe area as an obstacle made every one of the six slots
    # violate it, so they all tied and the bottom bias won: that is how p8's
    # caption2 ended up under the act lockup.
    if inset is None:
        ix = spec.cap_inset / max(spec.page_w, 1)
        iy = ix * (spec.page_w / spec.page_h)
    else:
        ix, iy = inset

    for key, ax, ay, bias_open, bias_close in _CAP_SLOTS:
        x0 = ix + (1 - 2 * ix - cw) * ax
        y0 = iy + (1 - 2 * iy - ch) * ay
        rect = (x0, y0, x0 + cw, y0 + ch)

        score = box_cost(bmap, rect) * 110.0
        score += bias_close if role == "close" else bias_open

        # A caption box overlapping anything already placed — another caption, an
        # SFX footprint — is always wrong, so any overlap takes a flat penalty on
        # top of the proportional one. Proportional alone let p8's caption2 sit on
        # caption1 because a marginally quieter patch of art outscored it.
        for occ in occupied:
            ov = _overlap(rect, occ)
            if ov > 1e-6:
                score += 2000.0 + ov * 900.0

        # Hard reservations — trim safe area, act lockup, folio. A proportional
        # penalty is not enough: on p8 a quiet patch of art at the foot outbid it
        # and caption2 landed under the lockup. Any overlap at all is disqualifying.
        for hz in hard:
            if _overlap(rect, hz) > 1e-6:
                score += 10000.0

        # never sit on a speaking face
        for a in anchors:
            if a and rect[0] - 0.05 < a[0] < rect[2] + 0.05 and \
                    rect[1] - 0.07 < a[1] < rect[3] + 0.07:
                score += 150.0

        if score < best_score:
            best_score, best, best_key = score, rect, key

    return best, best_key


def draw_caption(c, spec, text, cell, bmap, occupied, anchors, role="open",
                 hard=(), inset=None):
    """
    Narration box: cream stock, ink rule, hard offset shadow, crimson spine.

    Returns the normalized rect it occupied (also appended to `occupied`).
    """
    x, y, w, h = cell
    text = text.upper()

    max_w = w * spec.cap_w_max - 2 * spec.cap_pad_x - spec.cap_accent
    max_h = h * spec.cap_h_max - 2 * spec.cap_pad_y
    size, lines, tw, th = fit_block(
        text, spec, spec.cap_size_max, spec.cap_size_min, spec.cap_measure,
        spec.cap_leading, spec.cap_track, max_w, max_h)

    box_w = max(tw + 2 * spec.cap_pad_x + spec.cap_accent, w * spec.cap_w_min)
    box_w = min(box_w, w * spec.cap_w_max)
    box_h = th + 2 * spec.cap_pad_y

    rect, key = place_caption(spec, box_w / w, box_h / h, bmap, occupied,
                              anchors, role, hard, inset)

    bx = x + rect[0] * w
    by = y + h - rect[3] * h            # rect is top-left origin; canvas is not

    sh = spec.cap_shadow
    c.setFillColor(INK)          # not `black`: under --cmyk that is a bare 100K
    c.rect(bx + sh, by - sh, box_w, box_h, stroke=0, fill=1)

    c.setFillColor(CREAM)
    c.setStrokeColor(INK)
    c.setLineWidth(spec.cap_rule)
    c.rect(bx, by, box_w, box_h, stroke=1, fill=1)

    # crimson spine on the leading edge — the line's signature mark
    c.setFillColor(ACCENT)
    c.rect(bx, by, spec.cap_accent, box_h, stroke=0, fill=1)

    c.setFillColor(INK)
    draw_lines(c, spec, lines, size, spec.cap_leading, spec.cap_track,
               bx + spec.cap_accent + spec.cap_pad_x, by + box_h - spec.cap_pad_y)

    occupied.append(rect)
    return rect


# ---------------------------------------------------------------- balloons --

def _ellipse_pt(cx, cy, a, b, ang):
    return (cx + a * math.cos(ang), cy + b * math.sin(ang))


def place_balloon(spec, bw, bh, bmap, speaker, occupied, hard=()):
    """
    Choose a balloon centre (normalized, TOP-LEFT origin).

    Balloons want: quiet art, near their speaker, above them, high in the panel,
    clear of everything already placed, and a tail that does not cross a box.
    """
    hw, hh = bw / 2, bh / 2
    ys = np.arange(0.04 + hh, 0.90 - hh + 1e-6, 0.02)
    xs = np.arange(0.04 + hw, 0.96 - hw + 1e-6, 0.02)
    if len(ys) == 0 or len(xs) == 0:
        return (0.5, min(0.18 + hh, 0.9))

    best, best_score = None, 1e9
    for cy in ys:
        for cx in xs:
            rect = (cx - hw, cy - hh, cx + hw, cy + hh)

            score = box_cost(bmap, rect) * 100.0
            score += cy * 14.0                       # balloons belong high

            if speaker:
                score += math.hypot(cx - speaker[0], cy - speaker[1]) * 26.0
                face_r = 0.13
                if (abs(cx - speaker[0]) < hw + face_r * 0.8 and
                        abs(cy - speaker[1]) < hh + face_r):
                    score += 120.0
                if cy > speaker[1]:                  # reads better above
                    score += 26.0

                # The tail must not travel ACROSS the face to reach the mouth.
                # Guarding only the balloon body let p12's tail run down the
                # officer's cheek and terminate through his eye. The eyes sit
                # above the mouth anchor, so penalise any tail passing close to
                # that point — it pushes the balloon round to approach from the
                # side, where there is no face to cross.
                eyes = (speaker[0], speaker[1] - 0.075)
                score += 150.0 * max(0.0, 1.0 - _pt_seg_dist(eyes, (cx, cy),
                                                             speaker) / 0.085)

            for hz in hard:
                if _overlap(rect, hz) > 1e-6:
                    score += 10000.0

            for occ in occupied:
                if _overlap(rect, occ) > 0:
                    score += 200.0 + _overlap(rect, occ) * 1200.0
                # and the tail must not cut through it either
                if speaker and _seg_hits_rect((cx, cy), speaker, occ):
                    score += 260.0

            if score < best_score:
                best_score, best = score, (float(cx), float(cy))

    return best or (0.5, 0.18)


def _tail_tip(spec, cx, cy, a, b, tip, style):
    """
    Where the tail actually stops.

    Not at the mouth. A tail is a pointer, not a leader line: it leaves the
    balloon, travels part of the way, and ends in clear air with the speaker
    beyond it. Drawing to the anchor is what put a line through Thatcher's
    forehead and a spike into the officer's mouth on p13.

    Returns (end_point, ellipse_point, reach).
    """
    ang = math.atan2(tip[1] - cy, tip[0] - cx)
    ex, ey = _ellipse_pt(cx, cy, a, b, ang)
    dx, dy = tip[0] - ex, tip[1] - ey
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return (ex, ey), (ex, ey), 0.0

    frac = spec.bal_tail_reach.get(style, 0.42)
    reach = min(dist * frac, spec.bal_tail_max)
    reach = max(min(reach, dist), min(dist, spec.bal_tail_min))
    return (ex + dx / dist * reach, ey + dy / dist * reach), (ex, ey), reach


def _draw_tail(c, spec, cx, cy, a, b, tip, style):
    """Short, tapered tail pointing from the balloon toward the speaker."""
    ang = math.atan2(tip[1] - cy, tip[0] - cx)
    end, (ex, ey), reach = _tail_tip(spec, cx, cy, a, b, tip, style)
    if reach <= 0:
        return
    tip = end

    if style == "thought":
        c.setFillColor(BALLOON)
        c.setStrokeColor(INK)
        c.setLineWidth(spec.bal_rule * 0.55)
        for f, r in ((0.34, 3.6), (0.68, 2.4), (1.0, 1.5)):
            c.circle(ex + (tip[0] - ex) * f, ey + (tip[1] - ey) * f,
                     r * spec.scale, stroke=1, fill=1)
        return

    if style == "broadcast":
        c.setStrokeColor(INK)
        c.setLineWidth(1.5 * spec.scale)
        mx = (ex + tip[0]) / 2 + (tip[1] - ey) * 0.12
        my = (ey + tip[1]) / 2 - (tip[0] - ex) * 0.12
        p = c.beginPath()
        p.moveTo(ex, ey)
        p.curveTo(mx, my, mx, my, tip[0], tip[1])
        c.drawPath(p, stroke=1, fill=0)
        return

    # speech / whisper: a narrow, gently curved spike.
    #
    # The base width is DELIBERATELY absolute, not derived from the ellipse. Tying
    # it to `a` turns a big balloon's tail into a wedge that wipes out the face it
    # is pointing at — that bug ate Thatcher on p05_1.
    px, py = -math.sin(ang), math.cos(ang)
    hw = min(max(min(a, b) * 0.13, spec.bal_tail_hw), spec.bal_tail_hw_max)
    # A short tail with the old base width is a stubby triangle, so taper the base
    # for tails that had to be clamped hard.
    hw = min(hw, reach * 0.34)

    sx, sy = ex - math.cos(ang) * hw * 0.6, ey - math.sin(ang) * hw * 0.6
    b1 = (sx + px * hw, sy + py * hw)
    b2 = (sx - px * hw, sy - py * hw)
    # Bow scales with the tail, not the balloon — otherwise a clamped tail curls.
    bow = reach * 0.10

    p = c.beginPath()
    p.moveTo(*b1)
    p.curveTo(b1[0] + (tip[0] - b1[0]) * 0.40 + px * bow,
              b1[1] + (tip[1] - b1[1]) * 0.40 + py * bow,
              b1[0] + (tip[0] - b1[0]) * 0.82 + px * bow * 0.30,
              b1[1] + (tip[1] - b1[1]) * 0.82 + py * bow * 0.30,
              tip[0], tip[1])
    p.curveTo(b2[0] + (tip[0] - b2[0]) * 0.82 + px * bow * 0.30,
              b2[1] + (tip[1] - b2[1]) * 0.82 + py * bow * 0.30,
              b2[0] + (tip[0] - b2[0]) * 0.40 + px * bow,
              b2[1] + (tip[1] - b2[1]) * 0.40 + py * bow,
              b2[0], b2[1])
    p.close()
    c.setFillColor(BALLOON)
    c.setStrokeColor(INK)
    c.setLineWidth(spec.bal_rule * 0.85)
    c.drawPath(p, stroke=1, fill=1)


def _draw_body(c, spec, cx, cy, a, b, style):
    if style == "thought":
        n = max(int((a + b) / (7.0 * spec.scale)), 9)
        r = max(min(a, b) * 0.30, 3.2 * spec.scale)
        c.setFillColor(BALLOON)
        c.setStrokeColor(INK)
        # Derived from the house rule, not a literal. A thought balloon outlined
        # at half the weight of the speech balloon beside it reads as a different
        # book; the cloud only needs a touch less because it has many more edges.
        c.setLineWidth(spec.bal_rule * 0.80)
        for i in range(n):
            t = 2 * math.pi * i / n
            c.circle(cx + (a - r * 0.55) * math.cos(t),
                     cy + (b - r * 0.55) * math.sin(t), r, stroke=1, fill=1)
        c.setFillColor(BALLOON)
        c.ellipse(cx - (a - r * 0.75), cy - (b - r * 0.75),
                  cx + (a - r * 0.75), cy + (b - r * 0.75), stroke=0, fill=1)
        return

    if style == "broadcast":
        n = 22
        p = c.beginPath()
        for i in range(n):
            t = 2 * math.pi * i / n
            k = 1.0 if i % 2 == 0 else 0.80
            px, py = cx + a * k * math.cos(t), cy + b * k * math.sin(t)
            p.moveTo(px, py) if i == 0 else p.lineTo(px, py)
        p.close()
        c.setFillColor(BALLOON)
        c.setStrokeColor(INK)
        c.setLineWidth(spec.bal_rule * 0.85)
        c.drawPath(p, stroke=1, fill=1)
        return

    c.setFillColor(BALLOON)
    c.setStrokeColor(INK)
    if style == "whisper":
        c.setLineWidth(spec.bal_rule * 0.7)
        c.setDash(2.2 * spec.scale, 2.0 * spec.scale)
    else:
        c.setLineWidth(spec.bal_rule)
    c.ellipse(cx - a, cy - b, cx + a, cy + b, stroke=1, fill=1)
    c.setDash()


def draw_balloon(c, spec, item, cell, bmap, anchor, occupied, hard=()):
    """
    Draw one balloon. Placement is automatic unless the spec pins it with `pos`.

    anchor  speaker's mouth in panel space (0-1, top-left), or None for a
            floating, tail-less balloon (radio, TV, off-panel voice)
    """
    x, y, w, h = cell
    style = item.get("style", "speech")
    text = item["text"].upper()

    # A balloon must leave its panel readable. Set the text, measure the ellipse
    # it needs, and if that ellipse would cover too much of the panel, set the
    # text smaller and try again. Capping the ellipse alone just clips the words.
    area_cap = spec.bal_area_max * w * h
    if w * h < (spec.bal_area_min_panel * spec.page_w) ** 2:
        area_cap *= 1.15                  # a very small panel needs a little more

    # Derive the text box FROM the largest permitted ellipse rather than from an
    # independent fudge factor. The two used to disagree — the text was fitted to
    # 1.6x the axis cap, then the ellipse it needed was clamped back down, so the
    # balloon sat pinned at its maximum in every small panel. Inverting the same
    # relationship means the text simply sets smaller until it fits.
    infl = math.sqrt(2) * spec.bal_pad
    box_w = (2 * w * spec.bal_a_max) / infl
    box_h = (2 * h * spec.bal_b_max) / infl
    for _ in range(6):
        size, lines, tw, th = fit_balloon_block(text, spec, box_w, box_h)

        a = (tw / 2) * math.sqrt(2) * spec.bal_pad
        b = (th / 2) * math.sqrt(2) * spec.bal_pad
        b = max(b, size * 1.15)
        # floors keep a two-word balloon from shrinking to a lozenge
        a = max(a, w * spec.bal_a_min, b * 1.15)
        a = min(a, w * spec.bal_a_max)
        b = min(b, h * spec.bal_b_max)

        if math.pi * a * b <= area_cap or size <= spec.bal_size_min + 1e-6:
            break
        shrink = math.sqrt(area_cap / (math.pi * a * b))
        box_w *= max(shrink, 0.80)
        box_h *= max(shrink, 0.80)

    bw, bh = (2 * a) / w, (2 * b) / h

    if item.get("pos"):
        cxn, cyn = item["pos"]
    else:
        cxn, cyn = place_balloon(spec, bw, bh, bmap, anchor, occupied, hard)

    cx = min(max(x + w * cxn, x + a + 2), x + w - a - 2)
    cy = min(max(y + h * (1 - cyn), y + b + 2), y + h - b - 2)

    tip = (x + w * anchor[0], y + h * (1 - anchor[1])) if anchor else None

    if tip is not None:
        _draw_tail(c, spec, cx, cy, a, b, tip, style)
    _draw_body(c, spec, cx, cy, a, b, style)

    c.setFillColor(INK)
    draw_lines(c, spec, lines, size, spec.bal_leading, spec.bal_track,
               cx, cy + th / 2 + size * 0.06, align="center")

    occupied.append((cxn - bw / 2, cyn - bh / 2, cxn + bw / 2, cyn + bh / 2))


# -------------------------------------------------------------------- SFX --

# All ten effects in issue 02 shipped as the same cream slab with the same drop
# shadow — gunfire, breaking glass, an explosion and a grenade pin all identical.
# A kind carries its own fill, outline, weight, slant and relative size, so the
# reader can tell what they are hearing before they read the word.
#
#   fill / outline  the two colours
#   weight          outline weight as a multiple of the house value
#   slant           degrees of italic shear — speed and violence lean, quiet does not
#   size_mul        relative scale, so a pin-pull is not sized like a detonation
#   halo            soft outer glow, for things that emit light

SFX_KINDS = {
    "gun": {
        "fill": Color(0.98, 0.97, 0.94), "outline": Color(0.04, 0.04, 0.05),
        "weight": 1.5, "slant": 10, "size_mul": 1.00, "halo": None,
    },
    "fire": {
        "fill": Color(1.00, 0.72, 0.22), "outline": Color(0.42, 0.10, 0.03),
        "weight": 1.3, "slant": 6, "size_mul": 1.05,
        "halo": Color(0.85, 0.28, 0.05),
    },
    "glass": {
        "fill": Color(0.86, 0.94, 0.98), "outline": Color(0.08, 0.16, 0.24),
        "weight": 1.2, "slant": 14, "size_mul": 1.00, "halo": None,
    },
    "impact": {
        "fill": NEWSPRINT, "outline": Color(0.04, 0.04, 0.05),
        "weight": 1.9, "slant": 8, "size_mul": 1.05, "halo": None,
    },
    "quiet": {
        "fill": Color(0.80, 0.78, 0.72), "outline": Color(0.05, 0.05, 0.06),
        "weight": 0.7, "slant": 0, "size_mul": 0.62, "halo": None,
    },
}

# Fallback when a effect carries no explicit "kind".
_SFX_GUESS = [
    (("KRAK", "BRAKKA", "BLAM", "CRACK"), "gun"),
    (("FWOOM", "WHOOMP", "BOOM", "ROAR"), "fire"),
    (("KRASH", "KRAAM", "SMASH", "TINK"), "glass"),
    (("WHAM", "THUD", "KRUNCH", "SLAM"), "impact"),
    (("KLIK", "TCHK", "CLICK", "SNAP"), "quiet"),
]


def sfx_kind(item):
    if item.get("kind") in SFX_KINDS:
        return SFX_KINDS[item["kind"]]
    up = item["text"].upper()
    for words, key in _SFX_GUESS:
        if any(word in up for word in words):
            return SFX_KINDS[key]
    return SFX_KINDS["impact"]


def place_sfx(spec, fw, fh, bmap, pref, occupied):
    """
    Nudge an effect onto quiet art.

    SFX is drawn before the lettering, so it cannot route around captions — but it
    can route around FACES, which is the collision that actually reached the page
    (KRASH! across the breaching team, TCHK over the hand pulling the pin,
    BRAKKA-KRAK through three hostages). The authored `pos` stays the preferred
    spot; this searches a small neighbourhood around it for less detailed art.

    Set "pin": true on an effect to keep the authored position exactly.
    """
    if bmap is None:
        return pref
    px, py = pref
    d = spec.sfx_drift
    best, best_cost = (px, py), None
    for dx in (-d, -d / 2, 0.0, d / 2, d):
        for dy in (-d, -d / 2, 0.0, d / 2, d):
            cx = min(max(px + dx, fw / 2 + 0.02), 1 - fw / 2 - 0.02)
            cy = min(max(py + dy, fh / 2 + 0.02), 1 - fh / 2 - 0.02)
            rect = (cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2)
            cost = box_cost(bmap, rect)
            cost += 0.55 * ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5 / max(d, 1e-6)
            for r in occupied:
                if _overlap(rect, r):
                    cost += 2.0
            if best_cost is None or cost < best_cost:
                best, best_cost = (cx, cy), cost
    return best


def draw_sfx(c, spec, item, cell, occupied, bmap=None):
    """
    Sound effect: outlined display lettering, styled by kind. Reserves its own
    footprint so captions and balloons route around it instead of colliding.
    """
    x, y, w, h = cell
    text = item["text"]
    kind = sfx_kind(item)
    target_w = w * float(item.get("size", 0.5)) * kind["size_mul"]

    # The italic shear widens the glyph run by tan(slant) * cap height. Sizing on
    # the upright width alone pushed a sheared BRAKKA-KRAK out through the right
    # edge of its panel and into the next one, so measure what will be drawn.
    shear = math.tan(math.radians(kind["slant"]))

    size = 40.0 * spec.scale
    while size > 6 and (pdfmetrics.stringWidth(text, spec.font_sfx, size)
                        + shear * size * 0.72) > target_w:
        size -= 0.5

    # Sizing on width alone makes a long effect enormous in a short, wide panel —
    # BRAKKA-KRAK grew tall enough to reach the caption and lose its first word.
    # Cap it against the panel height as well.
    size = min(size, h * spec.sfx_h_max * kind["size_mul"] / 0.72)  # 0.72 ~ cap height

    pref = tuple(item.get("pos", [0.5, 0.5]))
    rot = float(item.get("rot", 0))

    tw = pdfmetrics.stringWidth(text, spec.font_sfx, size) + shear * size * 0.72
    rad = abs(math.radians(rot))
    fw = (tw * math.cos(rad) + size * math.sin(rad)) / w
    fh = (tw * math.sin(rad) + size * math.cos(rad)) / h

    if item.get("pin"):
        px, py = pref
    else:
        px, py = place_sfx(spec, fw, fh, bmap, pref, occupied)
    cx, cy = x + w * px, y + h * (1 - py)

    c.saveState()
    c.translate(cx, cy)
    c.rotate(rot)
    # Italic shear. Impact has no oblique cut, so slant it with the matrix rather
    # than faking it with a second face.
    if kind["slant"]:
        c.transform(1, 0, math.tan(math.radians(kind["slant"])), 1, 0, 0)
    c.setFont(spec.font_sfx, size)
    o = max(size * spec.sfx_outline * kind["weight"], 0.8)

    # `drawCentredString` centres horizontally but sets the BASELINE at the anchor,
    # so the glyphs grow upward out of `pos` — which is how BRAKKA-KRAK climbed into
    # a caption box. Drop the baseline by half the cap height so `pos` means the
    # optical centre of the effect, matching the footprint reserved below.
    base = -0.36 * size

    if kind["halo"]:
        # Re-wrapping as Color(hc.red, ...) here silently dragged the halo back
        # into RGB on an otherwise CMYK page — the last DeviceRGB object in the
        # whole press file, on the one SFX where colour accuracy matters.
        # Clone instead, so only the alpha changes and the space does not.
        c.setFillColor(_with_alpha(kind["halo"], 0.30))
        for ring in (2.6, 1.8):
            r = o * ring
            for i in range(8):
                t = 2 * math.pi * i / 8
                c.drawCentredString(r * math.cos(t), base + r * math.sin(t), text)

    c.setFillColor(kind["outline"])
    for ox, oy in ((-o, 0), (o, 0), (0, -o), (0, o),
                   (-o, -o), (o, o), (-o, o), (o, -o)):
        c.drawCentredString(ox, base + oy, text)
    c.setFillColor(kind["fill"])
    c.drawCentredString(0, base, text)
    c.restoreState()

    occupied.append((px - fw / 2, py - fh / 2 - 0.02, px + fw / 2, py + fh / 2 + 0.06))
