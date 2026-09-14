"""Build a 5-slide Instagram carousel (1080x1350, 4:5) for one comic.

  1  hook   -- splash art full-bleed, the hook line set large over a dark fade
  2  art    -- an inside page / art image, whole, on dark
  3  art    -- a second one
  4  art    -- a third one
  5  CTA    -- "Comment COMIC" (the DM funnel sends the link); issue #1 says FREE

Only preview material: a few pages / the storefront's own preview art, never the story in order.
Fonts: Montserrat (OFL), the same face the covers use. Never Impact (Monotype licence).
"""
import argparse
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
BG = (13, 13, 13)
RED = (200, 40, 36)
CREAM = (240, 232, 214)
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def font(size, weight="ExtraBold"):
    for d in (FONTS, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")):
        p = os.path.join(d, f"Montserrat-{weight}.ttf")
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise SystemExit(f"Montserrat-{weight}.ttf not found in fonts/")


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def cover_crop(im, w, h, focus_y=0.5):
    """Scale to fill w x h, crop the overflow (vertical focus 0..1)."""
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = (im.width - w) // 2
    y = round((im.height - h) * focus_y)
    return im.crop((x, y, x + w, y + h))


def contain(im, box_w, box_h):
    s = min(box_w / im.width, box_h / im.height)
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def tag(draw, x, y, text, size=26):
    f = font(size, "Bold")
    tw = draw.textlength(text, font=f)
    draw.rectangle((x, y, x + tw + 36, y + size + 22), fill=RED)
    draw.text((x + 18, y + 9), text, font=f, fill=(255, 255, 255))


def footer(draw, text):
    f = font(26, "Bold")
    tw = draw.textlength(text, font=f)
    draw.text(((W - tw) / 2, H - 58), text, font=f, fill=(150, 150, 150))


def slide_hook(art, hook, label, focus_y=0.35):
    base = cover_crop(art.convert("RGB"), W, H, focus_y=focus_y)
    fade = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.38) / (H * 0.62))
        fade.putpixel((0, y), int(255 * min(1.0, t * 1.15)))
    shade = Image.new("RGB", (W, H), (0, 0, 0))
    base = Image.composite(shade, base, fade.resize((W, H)))
    d = ImageDraw.Draw(base)
    tag(d, 60, 60, label)
    size = 76
    while size > 44:
        f = font(size)
        lines = wrap(d, hook, f, W - 120)
        if len(lines) * size * 1.18 <= H * 0.36:
            break
        size -= 4
    y = H - 150 - len(lines) * size * 1.18
    for ln in lines:
        d.text((60, y), ln, font=f, fill=(255, 255, 255))
        y += size * 1.18
    fs = font(30, "Bold")
    d.text((60, H - 105), "SWIPE  →", font=fs, fill=CREAM)
    return base


def slide_page(page, foot):
    s = Image.new("RGB", (W, H), BG)
    p = contain(page.convert("RGB"), W - 120, H - 150)
    x, y = (W - p.width) // 2, (H - 90 - p.height) // 2 + 10
    glow = Image.new("RGB", (p.width + 40, p.height + 40), (0, 0, 0)).filter(ImageFilter.GaussianBlur(12))
    s.paste(glow, (x - 20, y - 20))
    s.paste(p, (x, y))
    footer(ImageDraw.Draw(s), foot)
    return s


def slide_cta(cover, title, issue, pages, free):
    s = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(s)
    c = contain(cover.convert("RGB"), 420, 640)
    block = c.height + 60 + 70 + 112 + 70 + 34          # cover + the four text lines
    top = (H - block) // 2
    s.paste(c, ((W - c.width) // 2, top))
    y = top + c.height + 60
    def center(text, fnt, fill, yy):
        tw = d.textlength(text, font=fnt)
        d.text(((W - tw) / 2, yy), text, font=fnt, fill=fill)
    center("WANT THE FULL STORY?", font(40, "Bold"), CREAM, y); y += 70
    center("Comment COMIC", font(84), (255, 255, 255), y); y += 112
    # Only the free issue says "free", and it names the issue: "FREE" alone read as if every comic
    # were free (user, 2026-09-15).
    sub = f"Issue #{issue} is free. We'll DM it to you." if free else "and we'll DM you the link."
    center(sub, font(36, "Bold"), RED if free else CREAM, y); y += 70
    meta = " · ".join(x for x in (("Your first comic is on us" if free else f"Issue #{issue}"), ("" if free else title),
                                   f"{pages} pages" if pages else "") if x)
    center(meta, font(28, "Bold"), (150, 150, 150), y)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook-art", required=True)
    ap.add_argument("--art", nargs=3, required=True)
    ap.add_argument("--hook-focus", type=float, default=0.35)
    ap.add_argument("--cover", required=True)
    ap.add_argument("--hook", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--issue", required=True)
    ap.add_argument("--pages", default="")
    ap.add_argument("--free", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    foot = f"SHADOW GASP #{a.issue} · {a.title}"
    slides = [
        slide_hook(Image.open(a.hook_art), a.hook, f"SHADOW GASP · ISSUE #{a.issue}", a.hook_focus),
        slide_page(Image.open(a.art[0]), foot),
        slide_page(Image.open(a.art[1]), foot),
        slide_page(Image.open(a.art[2]), foot),
        slide_cta(Image.open(a.cover), a.title, a.issue, a.pages, a.free),
    ]
    for i, sl in enumerate(slides, 1):
        p = os.path.join(a.out, f"{i}.jpg")
        sl.save(p, quality=92)
        print("wrote", p)


if __name__ == "__main__":
    main()
