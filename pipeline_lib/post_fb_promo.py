"""Post one comic to the Facebook page, with the Gumroad link in the post.

Why this exists: the comics have never had a funnel of their own. A book goes live on
Gumroad and nothing points at it -- the shorts drive YouTube, and the store is reached only
by someone who already went looking. The page has ~1,344 followers against Instagram's 46,
so it is the one social asset worth pointing at the store.

⭐⭐ THE LINK GOES IN THE POST, NOT IN THE COMMENTS.
"Link in comments" is folk wisdom about Facebook demoting external links. The 2026-08-12
investigation into this page's reach collapse found the cause was a genuine DUPLICATE POST,
not link penalties: reach went from ~700-1,300 to 1 after day07 was crossposted twice in two
hours. Designing around a penalty there is no evidence for, at the cost of making a buyer
hunt for the link, would be cargo cult.

⭐⭐ AND THAT IS WHY THE MARKER MATTERS MORE HERE THAN FOR VIDEOS.
A video is posted once. A COMIC GETS REBUILT -- for a price change, an art regen, a
re-render -- and every rebuild would re-post it. That is exactly the duplicate pattern that
took the page's reach to 1 and had to be cleaned up by hand. So posting is keyed on the case
and refuses a second time unless --force is passed, the same shape as the FB_POSTED markers
in the video pipeline.

The image is the product's own Gumroad cover, fetched by URL: Gumroad already hosts it
publicly, and Graph's /photos endpoint takes a `url` directly. The comic build deletes
cases/ when it finishes, so nothing generated during the build survives to post time -- the
storefront is the only durable copy.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

# Same page and API version the video pipeline posts with (_fb_ig_upload.py). Hardcoded there
# too -- a page id is not a secret, and keeping it out of the secret store means one less
# thing to have drifted when a post silently goes to nowhere.
FB_PAGE_ID = "1164008466785123"
GRAPH = "https://graph.facebook.com/v19.0"

# The caption carries an emoji, and a Windows console defaults to cp1252 -- printing it there
# raises UnicodeEncodeError and kills the run *after* the post has already gone out, which
# would look like a failure worth retrying. Actions runners are UTF-8, but this has to be
# runnable locally to check a caption before posting it.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER_DIR = os.path.join(os.path.dirname(HERE), "promo")


def slugify(name):
    """Match pipeline.yml's slug so a marker lines up with the rest of the ledgers."""
    return re.sub(r"[^a-z0-9-]", "", (name or "").lower().replace(" ", "-"))[:40]


def gumroad(args):
    r = subprocess.run(["gumroad", *args, "--json"], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"gumroad {' '.join(args[:3])} failed: {(r.stderr or r.stdout)[:300]}")
    return json.loads(r.stdout)


def find_product(case_or_permalink):
    """The published product for this case. Refuses a draft: posting a link to an unpublished
    product sends every click to a 404, which is worse than not posting."""
    want = slugify(case_or_permalink)
    best = None
    for p in gumroad(["products", "list"])["products"]:
        if p.get("custom_permalink") == case_or_permalink or p.get("id") == case_or_permalink:
            best = p
            break
        # Match on the case name appearing in the product title, the way the funnel does --
        # product names are "SHADOW GASP #NN: TITLE" and never the raw case name.
        if want and (want in slugify(p.get("name", "")) or slugify(p.get("name", "")) in want):
            best = p
    if not best:
        raise SystemExit(f"no Gumroad product matches {case_or_permalink!r}")
    if not best.get("published"):
        raise SystemExit(f"{best['name']!r} is still a DRAFT -- publish it before promoting it, "
                         "or every click lands on a 404")
    return best


def cover_url(product):
    covers = product.get("covers") or []
    for c in covers:
        if c.get("url"):
            return c["url"]
    return product.get("preview_url") or product.get("thumbnail_url")


def build_caption(product, hook=None):
    """Hook first, then what it is, then the link. Nothing clever."""
    name = product.get("name", "SHADOW GASP")
    price = product.get("price", 0) / 100
    url = product.get("short_url") or ""
    pages = ""
    fi = product.get("file_info") or {}
    if fi.get("Length"):
        pages = fi["Length"].replace(" pages", "pp")

    if not hook:
        # The product description's opening paragraph is already written to hook a reader --
        # it is the same copy the storefront leads with. Strip markup, take the first
        # sentence or two.
        desc = re.sub(r"<[^>]+>", " ", product.get("description") or "")
        desc = " ".join(desc.split())
        parts = re.split(r"(?<=[.!?])\s+", desc)
        hook = " ".join(parts[:2])[:280] if parts else ""

    bits = [hook, "", name]
    detail = " · ".join([x for x in ("A documentary comic", pages, "instant PDF",
                                     f"${price:.0f}" if price else "") if x])
    bits += [detail, "", f"👉 {url}"]
    return "\n".join(b for b in bits if b is not None).strip()


def post_photo(token, image_url, caption):
    data = urllib.parse.urlencode({
        "url": image_url,
        "message": caption,
        "access_token": token,
    }).encode()
    req = urllib.request.Request(f"{GRAPH}/{FB_PAGE_ID}/photos", data=data,
                                 headers={"User-Agent": "shadow-gasp-comic-pipeline"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="case name, product id, or permalink")
    ap.add_argument("--hook", default=None, help="override the opening line")
    ap.add_argument("--force", action="store_true",
                    help="post again even though this comic was already posted")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve the product and print the caption; post nothing")
    a = ap.parse_args()

    product = find_product(a.case)
    slug = slugify(product.get("custom_permalink") or product.get("name"))
    marker = os.path.join(MARKER_DIR, f"{slug}.json")
    caption = build_caption(product, a.hook)
    img = cover_url(product)

    print(f"product : {product['name']}  (${product.get('price', 0) / 100:.0f})")
    print(f"link    : {product.get('short_url')}")
    print(f"image   : {img}")
    print("caption :")
    print("\n".join("    " + l for l in caption.splitlines()))

    if not img:
        raise SystemExit("product has no cover image to post")

    if os.path.exists(marker) and not a.force:
        prev = json.load(open(marker, encoding="utf-8"))
        print(f"\nALREADY POSTED on {prev.get('posted_at')} as {prev.get('fb_post_id')} -- "
              "skipping. Pass --force to post a second time.")
        return

    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("FB_PAGE_ACCESS_TOKEN is not set")

    if a.dry_run:
        # Prove the token and page are usable without publishing anything.
        req = urllib.request.Request(
            f"{GRAPH}/{FB_PAGE_ID}?fields=name,fan_count&access_token={urllib.parse.quote(token)}",
            headers={"User-Agent": "shadow-gasp-comic-pipeline"})
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.loads(r.read().decode())
        print(f"\nDRY RUN -- token valid for page {page.get('name')!r} "
              f"({page.get('fan_count')} followers). Nothing posted.")
        return

    try:
        res = post_photo(token, img, caption)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Facebook refused the post: {e.code} {e.read().decode()[:400]}")

    post_id = res.get("post_id") or res.get("id")
    print(f"\nposted: {post_id}")
    os.makedirs(MARKER_DIR, exist_ok=True)
    json.dump({"case": product["name"], "permalink": product.get("custom_permalink"),
               "fb_post_id": post_id, "url": product.get("short_url"),
               "posted_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"},
              open(marker, "w", encoding="utf-8"), indent=2)
    print(f"marker written: promo/{slug}.json")


if __name__ == "__main__":
    main()
