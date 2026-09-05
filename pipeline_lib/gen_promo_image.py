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


def _paste_cover(base, cover_path, margin, scale):
    """Drop the REAL cover into the frame, with a shadow and a hairline edge.

    ⭐ WITHOUT THIS THE POSTER NEVER SHOWS THE PRODUCT. promo_bg.jpg is generated for this case
    in the house style -- same model, same mandatory style prefix, same era palette -- but it
    is a bespoke establishing shot, deliberately emptied of close-up subjects so type can sit
    on it. A poster built on it alone advertises the mood and never shows the thing being sold,
    so a reader cannot tell what they would receive. The cover is the one image that IS the
    product, so it belongs in the frame.

    Right-hand side, because every type block here is left-aligned: putting it left would
    collide with the hook at long hook lengths rather than never.
    """
    if not cover_path or not os.path.exists(cover_path):
        return
    cov = Image.open(cover_path).convert("RGB")
    W, H = base.size
    target_h = int(H * 0.42)
    ratio = cov.width / max(1, cov.height)
    target_w = int(target_h * ratio)
    if target_w > W * 0.34:                      # never crowd the hook column
        target_w = int(W * 0.34)
        target_h = int(target_w / ratio)
    cov = cov.resize((max(1, target_w), max(1, target_h)), Image.LANCZOS)

    x = W - margin - target_w
    y = int(H * 0.5 - target_h * 0.5)

    shadow = Image.new("RGBA", (target_w + 40, target_h + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([20, 20, 20 + target_w, 20 + target_h], fill=(0, 0, 0, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    base.paste(shadow, (x - 20, y - 20 + int(8 * scale)), shadow)
    base.paste(cov, (x, y))
    ImageDraw.Draw(base).rectangle([x, y, x + target_w, y + target_h],
                                   outline=(90, 88, 84), width=max(1, int(2 * scale)))
    return (x, y, target_w, target_h)


def build(bg_path, hook, title, subtitle, cta, out_path, size=(SIZE, SIZE), cover_path=None):
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
    scale = min(W, H) / SIZE

    # The cover goes down BEFORE the type, and the text column is narrowed to what is left.
    # Drawing it afterwards would let the hook run underneath it -- text that reads fine in the
    # generated file and is unreadable in the post, which is the failure that only shows up
    # once it is public.
    placed = _paste_cover(bg, cover_path, margin, scale) if cover_path else None
    safe = (placed[0] - margin - int(30 * scale)) - margin if placed else W - margin * 2

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
    ap.add_argument("--cover", default=None,
                    help="the finished cover, inset so the poster shows the actual product")
    ap.add_argument("--hook", required=True, help="the scroll-stopping question/line")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="A documentary comic · Real case, researched")
    ap.add_argument("--cta", default="LINK IN COMMENTS")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1080x1080", help="WxH, e.g. 1280x720")
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))
    print(build(args.bg, args.hook, args.title, args.subtitle, args.cta, args.out, (w, h),
                cover_path=args.cover))


if __name__ == "__main__":
    main()
