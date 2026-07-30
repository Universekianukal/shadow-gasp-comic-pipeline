"""Square promo card for social posting: the comic shown as an object beside a
compact spec/hook block.

The earlier promo was a mood image with a hook line over it, which looked like
a documentary poster and gave no signal it was a comic for sale. Sales graphics
in digital-product groups work because they answer everything at a glance:
what it is, what's in it, what it costs, how you get it.
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


def build(pdf_path, out, title, subtitle_lines, issue, price, badge, inside, footer,
          strip="TRUE CRIME  ·  DOCUMENTARY COMIC", size=S):
    doc = fitz.open(pdf_path)
    tmp = out + ".cover.png"
    doc[0].get_pixmap(dpi=220).save(tmp)
    cov = Image.open(tmp).convert("RGB")
    w, h = cov.size

    side = min(w, h)
    bg = cov.crop(((w - side) // 2, (h - side) // 2,
                   (w - side) // 2 + side, (h - side) // 2 + side)).resize((size, size), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(26))).enhance(0.26)
    d = ImageDraw.Draw(bg, "RGBA")

    d.rectangle([0, 0, size, 58], fill=INK)
    d.text((28, 29), strip, font=_f("Montserrat-ExtraBold.ttf", 22), fill=CREAM, anchor="lm")
    d.text((size - 28, 29), issue, font=_f("Montserrat-ExtraBold.ttf", 22), fill=ACCENT, anchor="rm")

    s = (size * 0.735) / h
    fg = cov.resize((int(w * s), int(h * s)), Image.LANCZOS)
    x, y = 52, (size - fg.height) // 2 + 18
    bg.paste(Image.new("RGB", (fg.width + 16, fg.height + 16), (0, 0, 0)), (x - 8, y - 4))
    bg.paste(fg, (x, y))

    tx, right = x + fg.width + 44, size - 44
    ts = 76
    while ts > 30 and d.textlength(title.upper(), font=_f("Montserrat-ExtraBold.ttf", ts)) > right - tx:
        ts -= 4
    d.text((tx, 168), title.upper(), font=_f("Montserrat-ExtraBold.ttf", ts), fill=(255, 255, 255))
    d.rectangle([tx, 258, tx + 130, 266], fill=ACCENT)
    sy = 292
    for ln in subtitle_lines[:3]:
        d.text((tx, sy), ln, font=_f("Montserrat-Bold.ttf", 26), fill=CREAM)
        sy += 32

    def bdg(bx, by, bw, bh, t, fill, fgc, sz=22):
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=7, fill=fill)
        d.text((bx + bw / 2, by + bh / 2), t, font=_f("Montserrat-ExtraBold.ttf", sz), fill=fgc, anchor="mm")

    bw = (right - tx - 16) // 2
    bdg(tx, 420, bw, 54, badge, GOLD, INK)
    bdg(tx + bw + 16, 420, bw, 54, price, ACCENT, (255, 255, 255))
    bdg(tx, 488, right - tx, 54, "INSTANT PDF DOWNLOAD", CREAM, INK, 20)

    d.text((tx, 572), "INSIDE:", font=_f("Montserrat-ExtraBold.ttf", 21), fill=GOLD)
    py = 604
    for p in inside[:4]:
        d.rounded_rectangle([tx, py, right, py + 44], radius=7, outline=(122, 118, 112), width=2)
        d.text((tx + 16, py + 22), "·  " + p.upper(), font=_f("Montserrat-Bold.ttf", 19),
               fill=CREAM, anchor="lm")
        py += 52

    d.rectangle([0, size - 52, size, size], fill=INK)
    d.text((size / 2, size - 26), footer, font=_f("Montserrat-Bold.ttf", 19),
           fill=(178, 174, 167), anchor="mm")

    bg.save(out, quality=95)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out
