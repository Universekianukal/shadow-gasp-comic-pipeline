"""16:9 product-page hero: the comic standing on a blurred backdrop, with the
title block beside it.

The earlier version was a wide atmospheric image with a hook line over it,
which looked like a documentary poster and gave a buyer no signal they were
looking at a comic. Showing the actual cover as an object does that instantly.
"""
import os

import fitz
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
CREAM = (235, 229, 214)
ACCENT = (198, 48, 36)
MUTED = (176, 172, 165)


def _f(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def build(pdf_path, out, series, title, strip, meta_line, tagline, W=1280, H=720):
    doc = fitz.open(pdf_path)
    tmp = out + ".cover.png"
    doc[0].get_pixmap(dpi=200).save(tmp)
    cov = Image.open(tmp).convert("RGB")
    w, h = cov.size

    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side))
    bg = bg.resize((W, W), Image.LANCZOS).crop((0, (W - H) // 2, W, (W - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(30))).enhance(0.32)

    s = (H * 0.90) / h
    fg = cov.resize((int(w * s), int(h * s)), Image.LANCZOS)
    x, y = int(W * 0.09), (H - fg.height) // 2
    bg.paste(Image.new("RGB", (fg.width + 16, fg.height + 16), (0, 0, 0)), (x - 8, y - 4))
    bg.paste(fg, (x, y))

    d = ImageDraw.Draw(bg)
    tx = x + fg.width + int(W * 0.06)
    d.text((tx, int(H * 0.28)), series, font=_f("Montserrat-ExtraBold.ttf", 34), fill=CREAM)
    d.rectangle([tx, int(H * 0.375), tx + int(W * 0.30), int(H * 0.375) + 30], fill=ACCENT)
    d.text((tx + 10, int(H * 0.375) + 7), strip, font=_f("Montserrat-Bold.ttf", 13), fill=(255, 255, 255))

    ts = 76
    while ts > 30 and d.textlength(title.upper(), font=_f("Montserrat-ExtraBold.ttf", ts)) > W - tx - 40:
        ts -= 4
    d.text((tx, int(H * 0.47)), title.upper(), font=_f("Montserrat-ExtraBold.ttf", ts), fill=(255, 255, 255))
    d.text((tx, int(H * 0.66)), meta_line, font=_f("Montserrat-Bold.ttf", 20), fill=MUTED)
    d.text((tx, int(H * 0.73)), tagline, font=_f("Montserrat-Bold.ttf", 18), fill=MUTED)

    bg.save(out, quality=95)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out
