"""Compose a dedicated promotional graphic for social posting.

This is NOT a comic page. Comic interiors are the product; posting them into
general-interest groups sells the format ("here's some artwork") to people who
have no reason to care about comics yet. A promo graphic instead leads with the
hook — the unanswered question about the real case — the way a designed
template post does, with the comic as the payoff underneath.

Layout (1080x1080, the safest single size for feed + group posts):

    ┌──────────────────────────────┐
    │  SHADOW GASP · TRUE CRIME    │  small label, top
    │                              │
    │   BIG HOOK LINE THAT         │  the actual scroll-stopper
    │   RAISES A QUESTION          │
    │   ─────                      │  accent rule
    │                              │
    │  Title · 32-page comic       │  what it is
    │  $2.99 · link in comments    │  CTA
    └──────────────────────────────┘

Background is a dedicated atmospheric FLUX image (promo_bg.jpg), heavily
darkened so text stays legible — not a story panel.
"""
import argparse
import os
import textwrap

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "fonts")

SIZE = 1080
CREAM = (232, 226, 214)
ACCENT = (199, 51, 41)
MUTED = (150, 146, 140)


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _fit_hook(draw, text, font_name, max_width, start_size, min_size=44):
    """Shrink + wrap the hook until it fits the safe area."""
    size = start_size
    while size >= min_size:
        font = _font(font_name, size)
        # rough chars-per-line from average glyph width
        avg = draw.textlength("M", font=font)
        wrap_at = max(12, int(max_width / avg))
        lines = textwrap.wrap(text, width=wrap_at)
        if len(lines) <= 5 and all(draw.textlength(l, font=font) <= max_width for l in lines):
            return font, lines
        size -= 4
    font = _font(font_name, min_size)
    return font, textwrap.wrap(text, width=26)[:5]


def build(bg_path, hook, title, subtitle, cta, out_path):
    if bg_path and os.path.exists(bg_path):
        bg = Image.open(bg_path).convert("RGB")
        # cover-crop to square
        w, h = bg.size
        side = min(w, h)
        bg = bg.crop(((w - side) // 2, (h - side) // 2,
                      (w - side) // 2 + side, (h - side) // 2 + side))
        bg = bg.resize((SIZE, SIZE), Image.LANCZOS)
        bg = ImageEnhance.Brightness(bg).enhance(0.42)
        bg = bg.filter(ImageFilter.GaussianBlur(1.2))
    else:
        bg = Image.new("RGB", (SIZE, SIZE), (18, 18, 20))

    # Vertical scrim: darkest at top and bottom where text sits, so the
    # artwork still reads through the middle.
    scrim = Image.new("L", (1, SIZE))
    for y in range(SIZE):
        t = y / SIZE
        edge = max(0.0, 1 - abs(t - 0.5) * 2)      # 1 at centre, 0 at edges
        scrim.putpixel((0, y), int(215 - 120 * edge))
    scrim = scrim.resize((SIZE, SIZE))
    bg = Image.composite(Image.new("RGB", (SIZE, SIZE), (10, 10, 12)), bg, scrim)

    d = ImageDraw.Draw(bg)
    margin = 84
    safe = SIZE - margin * 2

    # top label
    label_font = _font("Montserrat-Bold.ttf", 26)
    d.text((margin, margin), "SHADOW GASP  ·  TRUE CRIME, TOLD IN INK",
           font=label_font, fill=MUTED)

    # hook
    hook_font, lines = _fit_hook(d, hook.upper(), "Montserrat-ExtraBold.ttf", safe, 82)
    line_h = hook_font.size * 1.16
    block_h = line_h * len(lines)
    y = (SIZE - block_h) / 2 - 40
    for line in lines:
        d.text((margin, y), line, font=hook_font, fill=CREAM)
        y += line_h

    # accent rule
    y += 18
    d.rectangle([margin, y, margin + 150, y + 7], fill=ACCENT)

    # bottom block
    title_font = _font("Montserrat-Bold.ttf", 40)
    sub_font = _font("Montserrat-Bold.ttf", 27)
    cta_font = _font("Montserrat-ExtraBold.ttf", 30)

    by = SIZE - margin - 150
    d.text((margin, by), title.upper(), font=title_font, fill=CREAM)
    d.text((margin, by + 54), subtitle, font=sub_font, fill=MUTED)
    d.text((margin, by + 100), cta, font=cta_font, fill=ACCENT)

    bg.save(out_path, quality=94)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", help="atmospheric background image (promo_bg.jpg)")
    ap.add_argument("--hook", required=True, help="the scroll-stopping question/line")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="A documentary comic · Real case, researched")
    ap.add_argument("--cta", default="LINK IN COMMENTS")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    print(build(args.bg, args.hook, args.title, args.subtitle, args.cta, args.out))


if __name__ == "__main__":
    main()
