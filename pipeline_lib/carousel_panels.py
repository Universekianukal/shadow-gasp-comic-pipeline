"""Panel-story carousel (v3): the comic told panel by panel, the way a comic seller cuts a carousel.

    python pipeline_lib/carousel_panels.py <comic.pdf> <out_dir> --issue 51 --title "..." --hook "..."

Why: v2 pasted whole pages onto the slides, and a full page of six to eight panels on a phone is
unreadable -- nobody follows the story, nobody swipes on (owner, 2026-09-17).

Slides (1080x1350), only real art from the first ~62% of the book (never the ending):
  1     hook         the splash art full-bleed, headline in Bebas Neue (the storefront's display face)
  2..6  story        ONE panel per slide, in reading order, its narration re-lettered large;
                     a tall splash fills the whole slide (boxed, it looked empty -- owner)
  7     cliffhanger  a later panel, darkened, stamped CASE FILE CONTINUES...
  8     CTA          the cover + "Comment COMIC" (unchanged from v2)
Panels come from the PDF itself: every panel is a placed image, so its box is exact.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import carousel_from_pdf as v2  # noqa: E402  (picker, hook art, text/art scoring, CTA slide)
import gen_carousel as g  # noqa: E402

W, H = g.W, g.H
RED, CREAM, INK = g.RED, g.CREAM, (11, 11, 13)
STORY_PANELS = 5
FONT_DIRS = [os.path.join(os.path.dirname(HERE), "fonts"), os.path.join(HERE, "fonts")]


def bebas(size):
    for d in FONT_DIRS:
        p = os.path.join(d, "BebasNeue-Regular.ttf")
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return g.font(size)


# ---------------------------------------------------------------- picking
def panels(doc, first, last, skip_pages):
    """Every sizeable panel in pages first..last (1-based) as {page, box, score}."""
    import fitz
    out = []
    for pno in range(first, last + 1):
        page = doc[pno - 1]
        if pno in skip_pages or v2.text_share(page) > 0.22:
            continue
        pw, ph = page.rect.width, page.rect.height
        for info in page.get_image_info():
            x0, y0, x1, y1 = info["bbox"]
            w, h = x1 - x0, y1 - y0
            share = (w * h) / (pw * ph)
            if share < 0.12 or not 0.5 <= w / h <= 2.6:
                continue
            pix = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), dpi=40)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            out.append({"page": pno, "box": (x0, y0, x1, y1), "score": v2.art_score(img) * share ** 0.5})
    return out


def pick_panels(doc):
    base = v2.pick(doc)
    first, last = base["window"]
    cands = panels(doc, first, last, {base["hook"]})
    story = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if all(c["page"] != s["page"] for s in story):
            story.append(c)
        if len(story) == STORY_PANELS:
            break
    story.sort(key=lambda c: (c["page"], c["box"][1], c["box"][0]))
    rest = [c for c in cands if c not in story and all(c["page"] != s["page"] for s in story)]
    later = [c for c in rest if story and c["page"] > story[-1]["page"]]
    cliff = max(later or rest, key=lambda c: c["score"]) if (later or rest) else None
    return base["hook"], story, cliff


def render_panel(doc, c, width=1000):
    """(image, narration) -- the panel as printed, and the lettering inside it as plain text."""
    import fitz
    x0, y0, x1, y1 = c["box"]
    rect = fitz.Rect(x0, y0, x1, y1)
    dpi = int(72 * width / (x1 - x0)) + 1
    pix = doc[c["page"] - 1].get_pixmap(clip=rect, dpi=min(dpi, 600))
    # Narration boxes only: page numbers and short act labels ("ACCIDENT") are text too.
    blocks = [" ".join(bl[4].split()) for bl in doc[c["page"] - 1].get_text("blocks", clip=rect)]
    text = " ".join(t for t in blocks if len(t) > 25 and not t.isdigit())
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), text


def raw_art(doc, c):
    """The panel's own embedded picture -- clean art, no lettering or page margin -- or None."""
    import io
    page = doc[c["page"] - 1]
    try:
        for info in page.get_image_info(xrefs=True):
            if info.get("xref") and all(abs(a - b) < 2 for a, b in zip(info["bbox"], c["box"])):
                im = Image.open(io.BytesIO(doc.extract_image(info["xref"])["image"])).convert("RGB")
                if im.width >= 600:
                    return im
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- slides
def chrome(img, idx, total, swipe=True):
    d = ImageDraw.Draw(img)
    f = g.font(24, "Bold")
    tw = d.textlength("SHADOW GASP", font=f)
    d.rectangle((48, 48, 48 + tw + 32, 92), fill=RED)
    d.text((64, 57), "SHADOW GASP", font=f, fill=(255, 255, 255))
    # progress bar: one segment per slide, this one red
    gap, x0, x1, y = 8, 48, W - 48, H - 40
    seg = (x1 - x0 - gap * (total - 1)) / total
    for i in range(total):
        sx = x0 + i * (seg + gap)
        d.rectangle((sx, y, sx + seg, y + 6), fill=RED if i == idx - 1 else (70, 68, 66))
    if swipe:
        # Bebas Neue has no arrow glyph, so the arrow is drawn.
        sf = bebas(40)
        ax = W - 48 - 34
        d.polygon([(ax, H - 92), (ax + 34, H - 76), (ax, H - 60)], fill=RED)
        d.text((ax - 16 - d.textlength("SWIPE", font=sf), H - 97), "SWIPE", font=sf, fill=CREAM)


def backdrop(img, dim=0.22):
    return ImageEnhance.Brightness(g.cover_crop(img, W, H, 0.5).filter(ImageFilter.GaussianBlur(36))).enhance(dim)


def slide_hook(art, headline, subline, issue, total):
    base = g.cover_crop(art.convert("RGB"), W, H, 0.30)
    fade = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.36) / (H * 0.64))
        fade.putpixel((0, y), int(255 * min(1.0, t * 1.3)))
    img = Image.composite(Image.new("RGB", (W, H), INK), base, fade.resize((W, H)))
    d = ImageDraw.Draw(img)
    text = headline.upper()
    size = 150
    while size > 80:
        f = bebas(size)
        lines = g.wrap(d, text, f, W - 110)
        if len(lines) <= 3:
            break
        size -= 6
    sf = g.font(38, "Bold")
    slines = g.wrap(d, subline, sf, W - 120)[:3] if subline else []
    block = len(lines) * size * 0.95 + (26 + len(slines) * 50 if slines else 0)
    y = H - 190 - block
    d.rectangle((60, y - 34, 180, y - 24), fill=RED)
    for ln in lines:
        d.text((58, y), ln, font=f, fill=(255, 255, 255))
        y += size * 0.95
    if slines:
        y += 26
        for ln in slines:
            d.text((60, y), ln, font=sf, fill=CREAM)
            y += 50
    d.text((60, H - 104), f"TRUE CRIME COMIC  ·  ISSUE #{issue}", font=bebas(40), fill=CREAM)
    chrome(img, 1, total)
    return img


def narration_block(d, text, max_w, max_h, start=50):
    """The panel's own lettering, re-set large enough to read on a phone."""
    if not text:
        return None, [], 0
    text = text.upper()
    size = start
    while size >= 30:
        f = g.font(size, "ExtraBold")
        lines = g.wrap(d, text, f, max_w)
        if len(lines) * size * 1.25 <= max_h:
            return f, lines, size
        size -= 2
    return None, [], 0


def slide_panel(panel, narration, idx, total):
    img = backdrop(panel)
    d = ImageDraw.Draw(img)
    top, bottom = 118, H - 130
    f, lines, size = narration_block(d, narration, W - 140, 330)
    text_h = int(len(lines) * size * 1.25) + (40 if lines else 0)
    fg = g.contain(panel, W - 80, bottom - top - text_h)
    x = (W - fg.width) // 2
    y = top + (bottom - top - text_h - fg.height) // 2
    d.rectangle((x - 5, y - 5, x + fg.width + 4, y + fg.height + 4), fill=CREAM)
    img.paste(fg, (x, y))
    ty = y + fg.height + 40
    if lines:
        d.rectangle((70, ty + 6, 80, ty + len(lines) * size * 1.25 - 10), fill=RED)
        for ln in lines:
            d.text((100, ty), ln, font=f, fill=(255, 255, 255))
            ty += size * 1.25
    chrome(img, idx, total)
    return img


def trim_white(img, thresh=232):
    """Cut near-white margins (some splash art carries a white bleed strip on one side)."""
    import numpy as np
    a = np.asarray(img.convert("L"), dtype=float)
    cols, rows = a.mean(axis=0), a.mean(axis=1)
    x0, x1, y0, y1 = 0, len(cols), 0, len(rows)
    while x0 < x1 - 10 and cols[x0] > thresh:
        x0 += 1
    while x1 > x0 + 10 and cols[x1 - 1] > thresh:
        x1 -= 1
    while y0 < y1 - 10 and rows[y0] > thresh:
        y0 += 1
    while y1 > y0 + 10 and rows[y1 - 1] > thresh:
        y1 -= 1
    return img.crop((x0, y0, x1, y1))


def slide_splash(panel, narration, idx, total):
    """A tall panel (a splash) fills the whole slide, like the hook: boxed, it left empty strips.
    `panel` should be the clean embedded art -- the printed lettering is re-set on the slide.
    The text goes over the QUIETER end of the picture, so the subject is never covered."""
    base = g.cover_crop(trim_white(panel.convert("RGB")), W, H, 0.35)
    d0 = ImageDraw.Draw(base)
    f, lines, size = narration_block(d0, narration, W - 160, 300, start=44)
    text_h = int(len(lines) * size * 1.25)
    band = int(H * 0.4)
    # Edge density, not tonal range: a bright empty shape (an envelope on black) is not "busy".
    def detail(im):
        return ImageStat.Stat(im.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]
    at_top = detail(base.crop((0, H - band, W, H))) > detail(base.crop((0, 0, W, band))) * 1.5
    fade = Image.new("L", (1, H))
    reach = text_h + 260
    for y in range(H):
        dist = y if at_top else H - y           # distance from the text's edge of the slide
        t = max(0.0, 1 - (dist - 110) / reach) if dist > 110 else 1.0
        fade.putpixel((0, y), int(235 * min(1.0, t * 1.4)))
    img = Image.composite(Image.new("RGB", (W, H), INK), base, fade.resize((W, H)))
    d = ImageDraw.Draw(img)
    ty = 130 if at_top else H - 150 - text_h
    if lines:
        d.rectangle((70, ty + 6, 80, ty + text_h - 10), fill=RED)
        for ln in lines:
            d.text((100, ty), ln, font=f, fill=(255, 255, 255))
            ty += size * 1.25
    chrome(img, idx, total)
    return img


def slide_story(doc, c, idx, total):
    panel, narration = render_panel(doc, c)
    if panel.width / panel.height < 0.9:
        return slide_splash(raw_art(doc, c) or panel, narration, idx, total)
    return slide_panel(panel, narration, idx, total)


def slide_cliff(panel, idx, total):
    img = backdrop(panel, 0.18)
    fg = ImageEnhance.Brightness(g.contain(panel, W - 80, H - 250)).enhance(0.45)
    # the lower half melts into black: the story is cut off, not shown
    mask = Image.new("L", fg.size, 255)
    md = ImageDraw.Draw(mask)
    for yy in range(fg.height):
        t = max(0.0, (yy - fg.height * 0.35) / (fg.height * 0.65))
        md.line((0, yy, fg.width, yy), fill=int(255 * (1 - min(1.0, t))))
    x, y = (W - fg.width) // 2, 118 + (H - 250 - fg.height) // 2
    img.paste(fg, (x, y), mask)
    stamp = Image.new("RGBA", (900, 260), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rectangle((8, 8, 891, 251), outline=RED, width=10)
    sf = bebas(118)
    label = "CASE FILE CONTINUES…"
    sd.text(((900 - sd.textlength(label, font=sf)) / 2, 58), label, font=sf, fill=RED)
    stamp = stamp.rotate(-6, expand=True, resample=Image.BICUBIC)
    img.paste(stamp, ((W - stamp.width) // 2, H // 2 - stamp.height // 2 + 40), stamp)
    d = ImageDraw.Draw(img)
    q = "What happened next is in the full comic."
    qf = g.font(40, "Bold")
    d.text(((W - d.textlength(q, font=qf)) / 2, H - 190), q, font=qf, fill=CREAM)
    chrome(img, idx, total)
    return img


def build_slides(pdf_path, issue, title, hook, out_dir):
    doc = v2._open(pdf_path)
    hook_page, story, cliff = pick_panels(doc)
    total = 1 + len(story) + (1 if cliff else 0) + 1
    head, sub = v2.headline_and_sub(hook or title)
    slides = [slide_hook(v2.hook_art(doc, hook_page), head, sub, issue, total)]
    slides += [slide_story(doc, c, k + 2, total) for k, c in enumerate(story)]
    if cliff:
        slides.append(slide_cliff(render_panel(doc, cliff)[0], len(slides) + 1, total))
    # No page count on the last slide (owner, 2026-09-17): just issue and title.
    cta = v2.slide_cta(v2.render(doc, 0, 150), title, issue, "", total, int(issue) == 1)
    chrome(cta, total, total, swipe=False)
    slides.append(cta)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for k, s in enumerate(slides, 1):
        p = os.path.join(out_dir, f"{k}.jpg")
        s.save(p, quality=90)
        paths.append(p)
    picks = {"hook": hook_page, "story": [(c["page"], [round(v) for v in c["box"]]) for c in story],
             "cliff": (cliff["page"], [round(v) for v in cliff["box"]]) if cliff else None}
    return paths, picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--hook", default="")
    a = ap.parse_args()
    paths, picks = build_slides(a.pdf, a.issue, a.title, a.hook, a.out_dir)
    print(len(paths), "slides", picks)


if __name__ == "__main__":
    main()
