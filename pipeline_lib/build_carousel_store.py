"""Carousel for an EXISTING, published comic, built from its Gumroad storefront pictures.

The comic's pages are not kept anywhere (cases/ is deleted after every build), but the storefront is
durable and public: every comic carries a 1280x720 banner, a 1080 square card, and 3 preview art
images from the opening third of the book. HEAVEN'S GATE also has its full-size book cover.

  slide 1   = the first art image, with the hook line
  slides 2+ = the art images (up to 3)
  last      = the book cover (the full cover when there is one, else cut out of the square card)

Dispatched by the comics bot (/carousel <n> for a comic without a carousel) through
build_carousel.yml, which commits the result and hands the entry back to the bot for the draft.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_carousel  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (shadow-gasp-comic-pipeline)"}


def gumroad(args):
    from stage_and_deliver import gumroad as _g
    return _g(args)


def classify(covers):
    """(banner, card, book_cover, art[]) from a product's covers, by SHAPE, never by position alone."""
    banner = card = book = None
    art = []
    for c in covers:
        w, h = c.get("native_width") or 0, c.get("native_height") or 0
        if not w or not h:
            continue
        r = w / h
        if banner is None and (w, h) == (1280, 720):
            banner = c
        elif card is None and w == h:
            card = c
        elif book is None and w >= 1500 and 0.55 <= r <= 0.72:
            book = c                        # a full-size book cover (HEAVEN'S GATE)
        else:
            art.append(c)
    return banner, card, book, art


def fetch(c, dest):
    url = c.get("original_url") or c.get("url")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        open(dest, "wb").write(r.read())
    return dest


def cover_from_card(card_path, dest):
    """The square card shows the book cover inset in the middle (x ~19%..81%, y ~3%..97%)."""
    im = Image.open(card_path).convert("RGB")
    w, h = im.size
    im.crop((round(w * 0.194), round(h * 0.028), round(w * 0.806), round(h * 0.972))).save(dest, quality=95)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True)
    ap.add_argument("--permalink", required=True)
    ap.add_argument("--hook", default="")
    ap.add_argument("--result", default=os.environ.get("CAR_BUILT_PATH", "/tmp/car_built.json"))
    ap.add_argument("--repo", default=gen_carousel.REPO)
    a = ap.parse_args()

    # --all: the CLI pages 10 products at a time, and a plain `products list` only ever saw the newest
    # ten -- #34 was "not found" on the first real run (2026-09-15).
    products = gumroad(["products", "list", "--all"]).get("products", [])
    p = next((x for x in products if x.get("custom_permalink") == a.permalink), None)
    if not p:
        raise SystemExit(f"no Gumroad product with permalink {a.permalink!r}")
    if not p.get("published"):
        raise SystemExit(f"{p['name']!r} is not published -- a carousel for it would send people to a dead link")
    title = p["name"].split(":", 1)[-1].strip() or p["name"]
    pages = "".join(re.findall(r"\d+", (p.get("file_info") or {}).get("Length", "")))
    hook = a.hook.strip()
    if not hook:
        desc = " ".join(re.sub(r"<[^>]+>", " ", p.get("description") or "").split())
        hook = re.split(r"(?<=[.!?])\s+", desc)[0][:160] if desc else title

    banner, card, book, art = classify(p.get("covers") or [])
    print(f"#{a.issue} {title}: banner={bool(banner)} card={bool(card)} book_cover={bool(book)} art={len(art)}", flush=True)
    if not art:
        raise SystemExit("this product has no preview art on Gumroad -- nothing to build slides from")
    if not (book or card):
        raise SystemExit("no book cover and no square card to take the cover from")

    tmp = tempfile.mkdtemp(prefix="carousel_")
    art_paths = [fetch(c, os.path.join(tmp, f"art{i}.jpg")) for i, c in enumerate(art[:3], 1)]
    if book:
        cover = fetch(book, os.path.join(tmp, "cover.jpg"))
    else:
        cover = cover_from_card(fetch(card, os.path.join(tmp, "card.jpg")), os.path.join(tmp, "cover.jpg"))

    free = int(a.issue) == 1
    slides = gen_carousel.build(art_paths[0], art_paths, cover, hook, title, int(a.issue), pages, free,
                                os.path.join(tmp, "slides"))
    caption = gen_carousel.default_caption(hook, int(a.issue), title, pages)
    entry = gen_carousel.publish_entry(slides, a.permalink, int(a.issue), title, a.permalink, caption, repo=a.repo)
    print(f"carousel: {len(slides)} slides -> carousel/{entry['dir']}", flush=True)
    json.dump(entry, open(a.result, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
