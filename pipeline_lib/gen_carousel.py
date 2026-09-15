"""Build an Instagram carousel (1080x1350, 4:5) for one comic, and file it under carousel/.

  1       hook   -- art full-bleed, the hook line set large over a dark fade
  2..n-1  art    -- 1 to 3 inside pages / art images, whole, on dark
  n       CTA    -- cover + "Comment COMIC" (the DM funnel sends the link); only issue #1 is free

Only preview material: the storefront's own preview art, or a few pages from the opening third of a
book -- never the ending. Fonts: Montserrat (OFL), the same face the covers use. Never Impact.

Filing (publish_entry): slides go to carousel/<slug>-<hash8>/1..N.jpg -- a content-hash folder, because
Instagram binds a fetch refusal to a URL for good -- and the listing to carousel/entries/<iii>-<slug>.json,
one small file per comic so two builds never edit the same file. carousel/index.json (issue #1) is the
older single list and is still read.
"""
import argparse
import hashlib
import json
import os
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
BG = (13, 13, 13)
RED = (200, 40, 36)
CREAM = (240, 232, 214)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HASHTAGS = "#truecrime #unsolved #coldcase #documentarycomic #shadowgasp"


def font(size, weight="ExtraBold"):
    for d in (os.path.join(HERE, "fonts"), os.path.join(REPO, "fonts")):
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
    # Wording picked by the user (2026-09-15): "Your first case is on us." -- a gift, not a sale.
    # Only issue #1 is free; every other issue gets the plain line.
    sub = "Your first case is on us." if free else "and we'll DM you the link."
    center(sub, font(36, "Bold"), RED if free else CREAM, y); y += 70
    meta = " · ".join(x for x in (f"Issue #{issue}", title, f"{pages} pages" if pages else "") if x)
    center(meta, font(28, "Bold"), (150, 150, 150), y)
    return s


def build(hook_art, art, cover, hook, title, issue, pages, free, out_dir, hook_focus=0.35):
    """Write 1.jpg..N.jpg into out_dir (N = 2 + len(art), art = 1..3 images). Returns the paths."""
    art = list(art)[:3]
    if not art:
        raise ValueError("a carousel needs at least one art image")
    os.makedirs(out_dir, exist_ok=True)
    foot = f"SHADOW GASP #{issue} · {title}"
    slides = [slide_hook(Image.open(hook_art), hook, f"SHADOW GASP · ISSUE #{issue}", hook_focus)]
    slides += [slide_page(Image.open(a), foot) for a in art]
    slides.append(slide_cta(Image.open(cover), title, issue, pages, free))
    paths = []
    for i, sl in enumerate(slides, 1):
        p = os.path.join(out_dir, f"{i}.jpg")
        sl.save(p, quality=92)
        paths.append(p)
    return paths


def default_caption(hook, issue, title, pages):
    """Hook, what it is, the call to action. The CTA is the one the user approved for #1; it must not
    repeat slide 5's line word for word (user rule)."""
    what = f"SHADOW GASP #{issue}: {title}, a {pages}-page documentary comic." if pages else \
        f"SHADOW GASP #{issue}: {title}, a documentary comic."
    return f"{hook.strip()} 🕯️\n\n{what}\n\nCurious how it ends? Comment COMIC and check your DMs 📩\n\n{HASHTAGS}"


def publish_entry(slide_paths, slug, issue, title, permalink, caption, repo=REPO):
    """Copy the slides to carousel/<slug>-<hash8>/ and write carousel/entries/<iii>-<slug>.json."""
    h = hashlib.sha256(b"".join(open(p, "rb").read() for p in slide_paths)).hexdigest()[:8]
    d = f"{slug}-{h}"
    dest = os.path.join(repo, "carousel", d)
    os.makedirs(dest, exist_ok=True)
    for i, p in enumerate(slide_paths, 1):
        shutil.copyfile(p, os.path.join(dest, f"{i}.jpg"))
    entry = {"issue": int(issue), "slug": slug, "permalink": permalink, "title": title, "dir": d,
             "slides": len(slide_paths), "caption": caption}
    edir = os.path.join(repo, "carousel", "entries")
    os.makedirs(edir, exist_ok=True)
    # One listing per comic: a rebuild replaces it (the older slide folder is simply no longer referenced).
    for old in os.listdir(edir):
        if old[:1].isdigit() and old.split("-", 1)[-1] == f"{slug}.json":
            os.remove(os.path.join(edir, old))
    with open(os.path.join(edir, f"{int(issue):03d}-{slug}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(entry, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook-art", required=True)
    ap.add_argument("--art", nargs="+", required=True, help="1 to 3 art images")
    ap.add_argument("--hook-focus", type=float, default=0.35)
    ap.add_argument("--cover", required=True)
    ap.add_argument("--hook", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--issue", required=True)
    ap.add_argument("--pages", default="")
    ap.add_argument("--free", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    for p in build(a.hook_art, a.art, a.cover, a.hook, a.title, a.issue, a.pages, a.free, a.out, a.hook_focus):
        print("wrote", p)


if __name__ == "__main__":
    main()
