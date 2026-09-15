"""THE carousel builder: pick the best pages inside a finished comic PDF and turn them into a carousel.

One picker and one look for every comic, wherever the PDF comes from:
  - the comic build (stage_and_deliver -> carousel_from_book), right after the PDF is made
  - /carousel <n> in Telegram (build_carousel.yml -> build_carousel_store), from the product's own PDF on
    Gumroad -- the file buyers download -- so any published comic, old or new, can be fetched and built

Picking (never the ending):
  - story window = page 3 (after cover + title page) up to ~62% of the book: the last third of the story
    and the back matter (sources, "what was real", credits) are never shown
  - text pages are skipped (text blocks cover >22% of the page)
  - every page in the window is scored for striking art: tonal range + edge detail
  - hook = the best page that is mostly ONE picture (a splash); story = the next 3 best, in reading order,
    never two neighbouring pages and never the hook's neighbours

Slides (1080x1350):
  1  hook   the splash page full-bleed, dark gradient, the headline + one line under it, swipe arrow
  2-4 story  the whole comic page (its own panels and lettering) over a blurred copy of itself
  5  CTA    the cover, "Comment COMIC" (+ "Your first case is on us." only for #1)
"""
import os
import re
import sys
import tempfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_carousel as g  # noqa: E402  (fonts, wrap, cover_crop, contain, default_caption, publish_entry)

W, H = g.W, g.H
RED, CREAM = g.RED, g.CREAM


def _open(path):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    return pymupdf.open(path)


def render(doc, i, dpi):
    pix = doc[i].get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def text_share(page):
    r = page.rect
    area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in page.get_text("blocks") if b[4].strip())
    return area / (r.width * r.height)


def art_score(img):
    gray = img.convert("L")
    return ImageStat.Stat(gray).stddev[0] * 0.6 + ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0] * 1.4


def splashiness(page):
    imgs = page.get_image_info()
    if not imgs:
        return 0.0
    r = page.rect
    biggest = max((b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1]) for b in imgs) / (r.width * r.height)
    return min(1.0, biggest / 0.7)


def pick(doc):
    """{'hook': page_no, 'story': [page_no x3], 'window': [first, last]} -- 1-based page numbers."""
    n = doc.page_count
    last = max(4, int(n * 0.62))
    cands = []
    for i in range(2, last):
        if text_share(doc[i]) > 0.22:
            continue
        cands.append({"page": i + 1, "score": art_score(render(doc, i, 40)), "splash": splashiness(doc[i])})
    if not cands:
        raise RuntimeError("no art pages in the story window")
    hook = max(cands, key=lambda c: c["score"] * (0.6 + 0.8 * c["splash"]))
    story = []
    for c in sorted((c for c in cands if c["page"] != hook["page"]), key=lambda c: -c["score"]):
        if abs(c["page"] - hook["page"]) > 1 and all(abs(c["page"] - s["page"]) > 1 for s in story):
            story.append(c)
        if len(story) == 3:
            break
    return {"hook": hook["page"], "story": sorted(c["page"] for c in story), "window": [3, last]}


# ---------------------------------------------------------------- slides
def chrome(img, idx, total):
    d = ImageDraw.Draw(img)
    f = g.font(24, "Bold")
    tw = d.textlength("SHADOW GASP", font=f)
    d.rectangle((48, 48, 48 + tw + 32, 92), fill=RED)
    d.text((64, 57), "SHADOW GASP", font=f, fill=(255, 255, 255))
    c = f"{idx}/{total}"
    cf = g.font(26, "Bold")
    cw = d.textlength(c, font=cf)
    d.rounded_rectangle((W - 48 - cw - 36, 48, W - 48, 92), radius=22, fill=(0, 0, 0))
    d.text((W - 48 - cw - 18, 55), c, font=cf, fill=CREAM)


def fit(d, text, max_w, max_lines, start, floor, weight="ExtraBold"):
    size = start
    while size > floor:
        f = g.font(size, weight)
        lines = g.wrap(d, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
        size -= 2
    f = g.font(floor, weight)
    return f, g.wrap(d, text, f, max_w), floor


def slide_hook(page_img, headline, subline, issue, total):
    base = g.cover_crop(page_img.convert("RGB"), W, H, 0.30)
    fade = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.40) / (H * 0.60))
        fade.putpixel((0, y), int(255 * min(1.0, t * 1.25)))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), base, fade.resize((W, H)))
    d = ImageDraw.Draw(img)
    f, lines, size = fit(d, headline, W - 120, 4, 88, 54)
    sf, slines, ssize = fit(d, subline, W - 120, 3, 38, 30, "Bold") if subline else (None, [], 0)
    block = len(lines) * size * 1.12 + (24 + len(slines) * ssize * 1.3 if slines else 0)
    y = H - 175 - block
    for ln in lines:
        d.text((60, y), ln, font=f, fill=(255, 255, 255))
        y += size * 1.12
    if slines:
        y += 24
        for ln in slines:
            d.text((60, y), ln, font=sf, fill=CREAM)
            y += ssize * 1.3
    d.text((60, H - 112), f"ISSUE #{issue}  ·  SWIPE", font=g.font(28, "Bold"), fill=CREAM)
    d.ellipse((W - 150, H - 150, W - 60, H - 60), fill=RED)
    d.text((W - 124, H - 136), "→", font=g.font(52), fill=(255, 255, 255))
    chrome(img, 1, total)
    return img


def slide_page(page_img, idx, total):
    """The whole comic page, as large as the slide allows, over a blurred copy of itself."""
    page_img = page_img.convert("RGB")
    bg = ImageEnhance.Brightness(g.cover_crop(page_img, W, H, 0.5).filter(ImageFilter.GaussianBlur(30))).enhance(0.40)
    fg = g.contain(page_img, W - 70, H - 150)
    x, y = (W - fg.width) // 2, 118 + (H - 150 - fg.height) // 2
    shadow = Image.new("RGBA", (fg.width + 60, fg.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((30, 30, fg.width + 30, fg.height + 30), fill=(0, 0, 0, 180))
    bg.paste(shadow.filter(ImageFilter.GaussianBlur(14)), (x - 30, y - 20), shadow.filter(ImageFilter.GaussianBlur(14)))
    bg.paste(fg, (x, y))
    chrome(bg, idx, total)
    return bg


def slide_cta(cover_img, title, issue, pages, total, free):
    bg = ImageEnhance.Brightness(g.cover_crop(cover_img.convert("RGB"), W, H, 0.5).filter(ImageFilter.GaussianBlur(30))).enhance(0.28)
    d = ImageDraw.Draw(bg)
    c = g.contain(cover_img.convert("RGB"), 540, 790)
    x, y = (W - c.width) // 2, 120
    d.rectangle((x - 6, y - 6, x + c.width + 5, y + c.height + 5), fill=CREAM)
    bg.paste(c, (x, y))
    y += c.height + 46

    def center(text, fnt, fill, yy):
        d.text(((W - d.textlength(text, font=fnt)) / 2, yy), text, font=fnt, fill=fill)
    center("WANT THE FULL STORY?", g.font(38, "Bold"), CREAM, y); y += 60
    center("Comment COMIC", g.font(92), (255, 255, 255), y); y += 116
    center("Your first case is on us." if free else "and we'll DM you the link.", g.font(36, "Bold"), RED if free else CREAM, y); y += 62
    meta = " · ".join(x for x in (f"Issue #{issue}", title, f"{pages} pages" if pages else "") if x)
    center(meta, g.font(26, "Bold"), (170, 165, 155), y)
    chrome(bg, total, total)
    return bg


def hook_art(doc, page_no, dpi=170):
    """The biggest raw picture on the hook page -- the panel art itself, without caption boxes or
    lettering -- so slide 1 is clean art behind the headline. Falls back to the rendered page."""
    try:
        import io
        best, best_area = None, 0
        for info in doc[page_no - 1].get_images(full=True):
            xref = info[0]
            w, h = info[2], info[3]
            if w * h > best_area and min(w, h) >= 500:
                best, best_area = xref, w * h
        if best:
            im = Image.open(io.BytesIO(doc.extract_image(best)["image"])).convert("RGB")
            if im.width * im.height >= 600 * 600:
                return im
    except Exception:
        pass
    return render(doc, page_no - 1, dpi)


def headline_and_sub(hook):
    t = " ".join((hook or "").split())
    parts = [s for s in re.split(r"(?<=[.!?])\s+", t) if s]
    return (parts[0], " ".join(parts[1:])) if parts else (t, "")


def build(pdf_path, issue, title, hook, permalink, repo=g.REPO, picks=None, out_dir=None):
    """Pick pages (or use `picks`), render the carousel, file it under carousel/. Returns the entry."""
    # Carousel-only hook line for comics whose saved hook gives away the ending (user, 2026-09-15).
    try:
        import json as _json
        ov = _json.load(open(os.path.join(repo, "carousel", "hook_overrides.json"), encoding="utf-8"))
        hook = ov.get(permalink) or hook
    except (OSError, ValueError):
        pass
    doc = _open(pdf_path)
    picks = picks or pick(doc)
    total = 2 + len(picks["story"])
    head, sub = headline_and_sub(hook or title)
    out_dir = out_dir or tempfile.mkdtemp(prefix="carousel_pdf_")
    os.makedirs(out_dir, exist_ok=True)
    slides = [slide_hook(hook_art(doc, picks["hook"]), head, sub, issue, total)]
    slides += [slide_page(render(doc, p - 1, 170), k + 2, total) for k, p in enumerate(picks["story"])]
    slides.append(slide_cta(render(doc, 0, 150), title, issue, str(doc.page_count), total, int(issue) == 1))
    paths = []
    for k, s in enumerate(slides, 1):
        p = os.path.join(out_dir, f"{k}.jpg")
        s.save(p, quality=90)
        paths.append(p)
    entry = g.publish_entry(paths, permalink, int(issue), title, permalink,
                            g.default_caption(hook or title, int(issue), title, str(doc.page_count)), repo=repo)
    entry["picks"] = picks
    return entry
