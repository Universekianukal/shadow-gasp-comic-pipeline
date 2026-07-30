"""16:9 product-page hero: the finished comic cover, letterboxed over a
blurred copy of itself.

Earlier version pasted the cover small in a corner next to a big repeated
title/tagline text block -- but the cover already carries its own logo and
title, so that read as the same headline twice at very different sizes,
cramped rather than bold. Letterboxing avoids cropping a 9:16 cover into a
16:9 frame while never duplicating text the cover already has.
"""
import os

import fitz
from PIL import Image, ImageEnhance, ImageFilter


def build(pdf_path, out, W=1280, H=720):
    doc = fitz.open(pdf_path)
    tmp = out + ".cover.png"
    doc[0].get_pixmap(dpi=260).save(tmp)
    cov = Image.open(tmp).convert("RGB")
    w, h = cov.size

    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side))
    bg = bg.resize((W, W), Image.LANCZOS).crop((0, (W - H) // 2, W, (W - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(30))).enhance(0.30)

    target_h = int(H * 0.92)
    scale = target_h / h
    fg = cov.resize((int(w * scale), target_h), Image.LANCZOS)
    x, y = (W - fg.width) // 2, (H - fg.height) // 2
    bg.paste(fg, (x, y))

    bg.save(out, quality=95)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out
