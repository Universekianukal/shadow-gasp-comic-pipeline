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
    │  $29 · link in comments      │  CTA
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


def build(bg_path, hook, title, subtitle, cta, out_path, size=(SIZE, SIZE)):
    W, H = size
    if bg_path and os.path.exists(bg_path):
        bg = Image.open(bg_path).convert("RGB")
        # cover-crop to square
        w, h = bg.size
        # cover-crop to the target aspect, then scale
        target = W / H
        if w / h > target:
            nw = int(h * target)
            bg = bg.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / target)
            bg = bg.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        bg = bg.resize((W, H), Image.LANCZOS)
        bg = ImageEnhance.Brightness(bg).enhance(0.42)
        bg = bg.filter(ImageFilter.GaussianBlur(1.2))
    else:
        bg = Image.new("RGB", (W, H), (18, 18, 20))

    # Vertical scrim: darkest at top and bottom where text sits, so the
    # artwork still reads through the middle.
    scrim = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        edge = max(0.0, 1 - abs(t - 0.5) * 2)      # 1 at centre, 0 at edges
        scrim.putpixel((0, y), int(215 - 120 * edge))
    scrim = scrim.resize((W, H))
    bg = Image.composite(Image.new("RGB", (W, H), (10, 10, 12)), bg, scrim)

    d = ImageDraw.Draw(bg)
    margin = int(min(W, H) * 0.078)
    safe = W - margin * 2
    scale = min(W, H) / SIZE

    # top label
    label_font = _font("Montserrat-Bold.ttf", max(16, int(26 * scale)))
    d.text((margin, margin), "SHADOW GASP  ·  TRUE CRIME, TOLD IN INK",
           font=label_font, fill=MUTED)

    # hook
    hook_font, lines = _fit_hook(d, hook.upper(), "Montserrat-ExtraBold.ttf", safe, max(40, int(82 * scale)))
    line_h = hook_font.size * 1.16
    block_h = line_h * len(lines)
    y = (H - block_h) / 2 - 40 * scale
    for line in lines:
        d.text((margin, y), line, font=hook_font, fill=CREAM)
        y += line_h

    # accent rule
    y += 18
    d.rectangle([margin, y, margin + 150 * scale, y + 7 * scale], fill=ACCENT)

    # bottom block
    title_font = _font("Montserrat-Bold.ttf", max(24, int(40 * scale)))
    sub_font = _font("Montserrat-Bold.ttf", max(16, int(27 * scale)))
    cta_font = _font("Montserrat-ExtraBold.ttf", max(18, int(30 * scale)))

    by = H - margin - 150 * scale
    d.text((margin, by), title.upper(), font=title_font, fill=CREAM)
    d.text((margin, by + 54 * scale), subtitle, font=sub_font, fill=MUTED)
    d.text((margin, by + 100 * scale), cta, font=cta_font, fill=ACCENT)

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
    ap.add_argument("--size", default="1080x1080", help="WxH, e.g. 1280x720")
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))
    print(build(args.bg, args.hook, args.title, args.subtitle, args.cta, args.out, (w, h)))


if __name__ == "__main__":
    main()
