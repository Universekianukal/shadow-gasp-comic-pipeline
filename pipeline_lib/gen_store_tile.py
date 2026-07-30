"""Square storefront tile styled as a comic cover.

A comic's shop tile IS its cover -- title, series banner, issue number. A bare
atmospheric image reads as a documentary still, not something you can buy.
"""
import os
from PIL import Image, ImageDraw, ImageFont

import os as _os
FONTS = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "fonts")
CREAM = (235, 229, 214)
ACCENT = (198, 48, 36)
INK = (16, 16, 18)


def f(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def build(art_path, series, issue, title, tagline, out, S=1080):
    art = Image.open(art_path).convert("RGB")
    w, h = art.size
    # crop to square around the upper-middle, where the figure sits
    side = min(w, h)
    top = int((h - side) * 0.28) if h > side else 0
    left = (w - side) // 2 if w > side else 0
    art = art.crop((left, top, left + side, top + side)).resize((S, S), Image.LANCZOS)

    d = ImageDraw.Draw(art, "RGBA")
    m = int(S * 0.055)

    # top series banner
    bar_h = int(S * 0.108)
    d.rectangle([0, 0, S, bar_h], fill=INK)
    lf = f("Montserrat-ExtraBold.ttf", int(S * 0.052))
    d.text((m, bar_h / 2), series, font=lf, fill=CREAM, anchor="lm")
    isf = f("Montserrat-Bold.ttf", int(S * 0.034))
    d.text((S - m, bar_h / 2), issue, font=isf, fill=ACCENT, anchor="rm")

    # bottom block: scrim + title + tagline
    blk = int(S * 0.30)
    d.rectangle([0, S - blk, S, S], fill=(16, 16, 18, 224))

    tf_size = int(S * 0.155)
    while tf_size > 40:
        tf = f("Montserrat-ExtraBold.ttf", tf_size)
        if d.textlength(title.upper(), font=tf) <= S - 2 * m:
            break
        tf_size -= 4
    ty = S - blk + int(S * 0.055)
    d.text((m, ty), title.upper(), font=tf, fill=CREAM)

    d.rectangle([m, ty + tf_size * 1.12, m + int(S * 0.13), ty + tf_size * 1.12 + int(S * 0.009)],
                fill=ACCENT)

    gf = f("Montserrat-Bold.ttf", int(S * 0.031))
    d.text((m, ty + tf_size * 1.12 + int(S * 0.035)), tagline.upper(), font=gf, fill=(176, 172, 165))

    art.save(out, quality=95)
    return out
