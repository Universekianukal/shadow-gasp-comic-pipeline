"""Carousel for any PUBLISHED comic, on demand (/carousel <n> in Telegram), from the comic itself.

The comic's own PDF lives on Gumroad -- the file buyers download -- and the seller can fetch it:
`products view` lists the product's files with a signed download URL, and `products content get` says
which of them is the buyer's download (its fileEmbed). So every comic, old or upcoming, is fetchable,
and its carousel is picked from its real pages by carousel_from_pdf -- the same picker and look the
comic build uses, so a carousel looks the same however it was made.

Dispatched through build_carousel.yml, which commits the result and hands the entry back to the bot
for the draft. Nothing is posted here.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import carousel_from_pdf  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (shadow-gasp-comic-pipeline)"}


def gumroad(args):
    from stage_and_deliver import gumroad as _g
    return _g(args)


def buyer_pdf(product_id):
    """(url, name) of the PDF a buyer downloads: the file whose id is embedded in the product content."""
    view = gumroad(["products", "view", product_id])
    files = [f for f in ((view.get("product", view) or {}).get("files") or []) if f.get("filetype") == "pdf" and f.get("url")]
    if not files:
        raise SystemExit("this product has no PDF file on Gumroad")
    embedded = set(re.findall(r'"id":\s*"([^"]+)"', json.dumps(gumroad(["products", "content", "get", product_id]))))
    pick = [f for f in files if f["id"] in embedded] or files[-1:]
    return pick[0]["url"], pick[0].get("name", "comic.pdf")


def download(url, dest):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(dest, "wb") as out:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            out.write(b)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True)
    ap.add_argument("--permalink", required=True)
    ap.add_argument("--hook", default="")
    ap.add_argument("--result", default=os.environ.get("CAR_BUILT_PATH", "/tmp/car_built.json"))
    ap.add_argument("--repo", default=carousel_from_pdf.g.REPO)
    a = ap.parse_args()

    # --all: the CLI pages 10 products at a time; a plain list only ever saw the newest ten.
    products = gumroad(["products", "list", "--all"]).get("products", [])
    p = next((x for x in products if x.get("custom_permalink") == a.permalink), None)
    if not p:
        raise SystemExit(f"no Gumroad product with permalink {a.permalink!r}")
    if not p.get("published"):
        raise SystemExit(f"{p['name']!r} is not published -- a carousel for it would send people to a dead link")
    title = p["name"].split(":", 1)[-1].strip() or p["name"]
    hook = a.hook.strip()
    if not hook:
        desc = " ".join(re.sub(r"<[^>]+>", " ", p.get("description") or "").split())
        hook = re.split(r"(?<=[.!?])\s+", desc)[0][:160] if desc else title

    url, name = buyer_pdf(p["id"])
    pdf = download(url, os.path.join(tempfile.mkdtemp(prefix="carousel_src_"), "comic.pdf"))
    print(f"#{a.issue} {title}: fetched the buyer's PDF ({name}, {os.path.getsize(pdf) / 1e6:.1f} MB)", flush=True)

    entry = carousel_from_pdf.build(pdf, int(a.issue), title, hook, a.permalink, repo=a.repo)
    print(f"carousel: {entry['slides']} slides -> carousel/{entry['dir']}  (hook p{entry['picks']['hook']}, "
          f"story {entry['picks']['story']})", flush=True)
    json.dump(entry, open(a.result, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
