"""Square storefront tile built from the FINISHED comic cover page.

Not from raw art: a shop tile for a comic is its cover, trade dress and all
(logo, issue/price box, title). Bare atmospheric art reads as a documentary
still rather than something purchasable.

The cover is 9:16, so it's letterboxed over a blurred, darkened copy of itself
rather than cropped — cropping a portrait cover to square cuts off the title.
"""
import os

import fitz
from PIL import Image, ImageEnhance, ImageFilter

S = 1080


def build(pdf_path, out, size=S):
    doc = fitz.open(pdf_path)
    doc[0].get_pixmap(dpi=200).save(out + ".cover.png")
    cov = Image.open(out + ".cover.png").convert("RGB")
    w, h = cov.size

    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side))
    bg = bg.resize((size, size), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(28))).enhance(0.38)

    scale = min(size / w, size / h) * 0.94
    fg = cov.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    bg.paste(fg, ((size - fg.width) // 2, (size - fg.height) // 2))
    bg.save(out, quality=95)

    try:
        os.remove(out + ".cover.png")
    except OSError:
        pass
    return out
