"""Square promo card for social posting: just the finished comic cover,
letterboxed over a blurred copy of itself.

Two earlier versions both drew button-shaped badges (UNSOLVED / OUT NOW /
INSTANT PDF) as pixels baked into the image. Whatever page later embeds this
image (a Gumroad landing page, a social post) can't tell a visitor those
aren't real buttons -- they look exactly like the actual buy button, get
tapped, and do nothing. That's a trust problem, not a style one. Any status
text belongs in real HTML/live UI elsewhere on the page, never burned into
the image itself.
"""
import os

import fitz
from PIL import Image, ImageEnhance, ImageFilter

S = 1080


def build(pdf_path, out, size=S):
    doc = fitz.open(pdf_path)
    tmp = out + ".cover.png"
    doc[0].get_pixmap(dpi=260).save(tmp)
    cov = Image.open(tmp).convert("RGB")
    w, h = cov.size

    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side)).resize((size, size), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(30))).enhance(0.22)

    target_h = int(size * 0.94)
    scale = target_h / h
    fg = cov.resize((int(w * scale), target_h), Image.LANCZOS)
    x, y = (size - fg.width) // 2, (size - target_h) // 2
    bg.paste(fg, (x, y))

    bg.save(out, quality=95)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out
