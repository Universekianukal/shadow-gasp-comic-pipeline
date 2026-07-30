"""Square promo card for social posting: the finished comic cover, large,
with three spec badges underneath.

Earlier version put the cover in a small corner next to a big repeated
title/tagline block -- but the cover already has its own logo and title
baked in, so that read as the same headline twice at two different sizes,
cramped and cluttered. This version lets the cover carry the whole image;
the badges add just the facts a cover can't (unsolved/status/format).
"""
import os

import fitz
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
CREAM = (238, 232, 218)
ACCENT = (198, 48, 36)
GOLD = (226, 168, 48)
INK = (14, 14, 16)
S = 1080


def _f(n, s):
    return ImageFont.truetype(os.path.join(FONTS, n), s)


def build(pdf_path, out, badge, cta="OUT NOW", format_label="INSTANT PDF", size=S):
    doc = fitz.open(pdf_path)
    tmp = out + ".cover.png"
    doc[0].get_pixmap(dpi=260).save(tmp)
    cov = Image.open(tmp).convert("RGB")
    w, h = cov.size

    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side)).resize((size, size), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(30))).enhance(0.22)
    d = ImageDraw.Draw(bg, "RGBA")

    target_h = int(size * 0.855)
    scale = target_h / h
    fg = cov.resize((int(w * scale), target_h), Image.LANCZOS)
    fx, fy = (size - fg.width) // 2, 18
    d.rectangle([fx - 8, fy - 8, fx + fg.width + 8, fy + fg.height + 8], fill=(0, 0, 0))
    bg.paste(fg, (fx, fy))

    by = fy + fg.height + 20

    def bdg(bx, byy, bw, bh, t, fill, fgc, sz=19):
        d.rounded_rectangle([bx, byy, bx + bw, byy + bh], radius=7, fill=fill)
        d.text((bx + bw / 2, byy + bh / 2), t, font=_f("Montserrat-ExtraBold.ttf", sz),
               fill=fgc, anchor="mm")

    gap = 10
    bw3 = (size - 2 * 44 - 2 * gap) // 3
    bdg(44, by, bw3, 50, badge, GOLD, INK)
    bdg(44 + bw3 + gap, by, bw3, 50, cta, ACCENT, (255, 255, 255))
    bdg(44 + 2 * (bw3 + gap), by, bw3, 50, format_label, CREAM, INK, 17)

    bg.save(out, quality=95)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out
