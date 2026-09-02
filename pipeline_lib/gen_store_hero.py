"""16:9 product-page hero: the finished comic stood beside a panel of facts.

History, because this layout has flipped once already. An early version pasted a small cover
next to a big repeated title, and was replaced by a centred letterboxed cover on the grounds
that "the cover already carries its own logo and title, so that read as the same headline twice
at very different sizes". That reasoning is sound about REPETITION and wrong about the panel: on
the NORJAK hero, which was assembled by hand and is the best of the three storefronts, the panel
earns its space by carrying what the cover cannot -- the issue number, the format, and the hook
sentence -- as text that stays legible when the whole image is 300px wide in a gallery.

So: keep the panel, and give it facts. The series and title repeat by necessity (a cover shrunk
to fit 16:9 renders its own lettering too small to read), but everything under them is new
information rather than a second headline.
"""
import os

import fitz
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [os.path.join(os.path.dirname(HERE), "fonts"), os.path.join(HERE, "fonts")]


def _font(name, size):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build(pdf_path, out, meta=None, W=1280, H=720):
    """meta: {series, title, issue_no, hook, pages, price}. Missing keys just omit their line."""
    meta = meta or {}
    doc = fitz.open(pdf_path)
    tmp = out + ".cover.png"
    doc[0].get_pixmap(dpi=260).save(tmp)
    cov = Image.open(tmp).convert("RGB")
    w, h = cov.size

    # Blurred, darkened wash of the cover as the ground -- keeps the palette of the book itself
    # rather than dropping it on flat black.
    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side))
    bg = bg.resize((W, W), Image.LANCZOS).crop((0, (W - H) // 2, W, (W - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(30))).enhance(0.28)

    # Cover on the left, upright and uncropped.
    target_h = int(H * 0.86)
    scale = target_h / h
    fg = cov.resize((max(1, int(w * scale)), target_h), Image.LANCZOS)
    pad = int(W * 0.055)
    fg_x, fg_y = pad, (H - fg.height) // 2
    shadow = Image.new("RGB", (fg.width + 16, fg.height + 16), (0, 0, 0))
    bg.paste(shadow, (fg_x - 8, fg_y - 8))
    bg.paste(fg, (fg_x, fg_y))

    d = ImageDraw.Draw(bg)
    tx = fg_x + fg.width + int(W * 0.06)
    tw = W - tx - pad
    y = int(H * 0.20)

    series = (meta.get("series") or "SHADOW GASP").upper()
    d.text((tx, y), series, font=_font("Montserrat-Bold.ttf", 40), fill=(238, 238, 238))
    y += 60

    strap = "TRUE CRIME  ·  DOCUMENTARY COMIC"
    f_strap = _font("Montserrat-Bold.ttf", 20)
    bar_h = 40
    d.rectangle([tx, y, tx + min(tw, int(d.textlength(strap, font=f_strap)) + 36), y + bar_h],
                fill=(196, 40, 40))
    d.text((tx + 18, y + 9), strap, font=f_strap, fill=(255, 255, 255))
    y += bar_h + 34

    title = (meta.get("title") or "").upper()
    if title:
        f_title = _font("Montserrat-ExtraBold.ttf", 68)
        for line in _wrap(d, title, f_title, tw)[:2]:
            d.text((tx, y), line, font=f_title, fill=(255, 255, 255))
            y += 78
        y += 12

    # The part the cover cannot carry.
    bits = []
    if meta.get("issue_no"):
        bits.append(f"Issue {meta['issue_no']}")
    # The PDF's own page count, not the script's story-page count: the buyer downloads 80 pages
    # and the script says 75, and pricing already settled on what the buyer actually receives.
    bits.append(f"{doc.page_count} pages")
    bits.append("Instant PDF download")
    d.text((tx, y), "  ·  ".join(bits), font=_font("Montserrat-Bold.ttf", 26),
           fill=(200, 200, 200))
    y += 48

    hook = (meta.get("hook") or "").strip()
    if hook:
        f_hook = _font("Montserrat-Bold.ttf", 24)
        for line in _wrap(d, hook, f_hook, tw)[:3]:
            d.text((tx, y), line, font=f_hook, fill=(228, 228, 228))
            y += 34

    bg.save(out, quality=95)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out
