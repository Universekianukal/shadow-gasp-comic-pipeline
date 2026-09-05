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


# Instagram's feed accepts 0.80 (4:5) to 1.91 (landscape) and nothing outside it.
IG_MIN_RATIO, IG_MAX_RATIO = 0.80, 1.91


def _measure(url):
    """(width, height) of a remote image, or None. Best-effort: a cover we cannot measure is
    simply not preferred, never fatal."""
    try:
        from PIL import Image
        import io as _io
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return Image.open(_io.BytesIO(r.read())).size
    except Exception:
        return None


def cover_url(product, platform="fb"):
    """Pick the cover to post, by SHAPE rather than by position.

    ⭐ A comic has five covers on Gumroad and only two are postable to Instagram. Taking
    covers[0] -- the obvious choice, and what this did first -- lands on the 1005x565 banner;
    the book cover itself is 1005x1519 (ratio 0.66), which Instagram rejects outright, and two
    of the marketing strips are 1.93 and 2.21, also rejected. Only the square 1005x1005 promo
    card and the 1.78 banner are inside IG's 0.80-1.91 window.

    Square wins on both platforms anyway: it is the card gen_promo_card.py builds for exactly
    this purpose, and it occupies more of a feed than a letterbox does.
    """
    covers = [c["url"] for c in (product.get("covers") or []) if c.get("url")]
    if not covers:
        u = product.get("preview_url") or product.get("thumbnail_url")
        return u, None
    scored = []
    for u in covers:
        size = _measure(u)
        if not size:
            continue
        w, h = size
        ratio = w / h if h else 0
        if platform == "ig" and not (IG_MIN_RATIO <= ratio <= IG_MAX_RATIO):
            continue                      # Instagram would refuse it; do not offer it
        scored.append((abs(ratio - 1.0), u, (w, h, ratio)))
    if not scored:
        if platform == "ig":
            raise SystemExit(
                "no cover is inside Instagram's 0.80-1.91 aspect window -- the book cover is "
                "~0.66 and the marketing strips are ~1.9-2.2. Add a square promo card as a "
                "Gumroad cover first.")
        return covers[0], None
    scored.sort()                          # closest to square first
    _, url, dims = scored[0]
    return url, dims


def build_caption(product, hook=None, platform="fb"):
    """Hook first, then what it is, then the link. Nothing clever.

    ⭐ INSTAGRAM CAPTIONS HAVE NO CLICKABLE LINKS. A URL in an IG caption is inert text -- a
    reader has to memorise or retype it, which nobody does. Printing "👉 https://..." there
    would look like a funnel while carrying almost no one through. So the IG variant points at
    the bio instead, which is the only tappable link an IG feed post has.
    """
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
    bits += [detail, ""]
    if platform == "ig":
        bits += ["🔗 Link in bio — the full issue is on Gumroad.", "",
                 "#truecrime #unsolved #coldcase #documentarycomic #shadowgasp"]
    else:
        bits += [f"👉 {url}"]
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


def _graph_post(url, params):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode(),
                                 headers={"User-Agent": "shadow-gasp-comic-pipeline"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def post_instagram(token, image_url, caption):
    """Container -> poll -> publish, the same three steps the video pipeline uses.

    ⚠️ ERROR 9004 / 2207052 STICKS TO THE URL. When Instagram refuses to fetch an image it
    binds that refusal to the asset, and retrying the SAME url returns the identical error
    forever -- proven on everydayhype, where a slide was refused across three runs spanning
    three hours while its siblings from the same batch went through every time. A different
    URL *string* for the same asset is not enough either; only genuinely re-uploaded bytes
    clear it. So this never retries: it says plainly that the asset is burned and what to do.
    """
    try:
        container = _graph_post(f"{GRAPH}/{IG_USER_ID}/media", {
            "image_url": image_url,          # a photo, not REELS -- no media_type for images
            "caption": caption,
            "access_token": token,
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        if "9004" in body or "2207052" in body:
            raise SystemExit(
                "Instagram refused to fetch this image (9004/2207052). That refusal is bound "
                "to the URL and retrying it will fail identically forever. Re-upload the cover "
                "to Gumroad so it gets a NEW asset path, then post again.\n" + body)
        raise SystemExit(f"Instagram container failed: {e.code} {body}")

    cid = container["id"]
    deadline = __import__("time").time() + 300
    while __import__("time").time() < deadline:
        q = urllib.parse.urlencode({"fields": "status_code,status", "access_token": token})
        with urllib.request.urlopen(
                urllib.request.Request(f"{GRAPH}/{cid}?{q}",
                                       headers={"User-Agent": "shadow-gasp-comic-pipeline"}),
                timeout=60) as r:
            st = json.loads(r.read().decode())
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise SystemExit(f"Instagram rejected the media while processing: {st.get('status')}")
        __import__("time").sleep(8)
    else:
        raise SystemExit(f"Instagram container {cid} never finished processing")

    res = _graph_post(f"{GRAPH}/{IG_USER_ID}/media_publish",
                      {"creation_id": cid, "access_token": token})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="case name, product id, or permalink")
    ap.add_argument("--platform", default="fb", choices=["fb", "ig"],
                    help="fb = Facebook page, ig = Instagram")
    ap.add_argument("--hook", default=None, help="override the opening line")
    ap.add_argument("--force", action="store_true",
                    help="post again even though this comic was already posted here")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve everything and emit the preview; post nothing")
    ap.add_argument("--preview-out", default=None,
                    help="write the resolved preview as JSON here (for the Telegram draft)")
    a = ap.parse_args()

    product = find_product(a.case)
    slug = slugify(product.get("custom_permalink") or product.get("name"))
    marker = os.path.join(MARKER_DIR, f"{slug}.json")
    caption = build_caption(product, a.hook, a.platform)
    img, dims = cover_url(product, a.platform)

    print(f"platform: {a.platform}")
    print(f"product : {product['name']}  (${product.get('price', 0) / 100:.0f})")
    print(f"link    : {product.get('short_url')}")
    print(f"image   : {img}" + (f"  {dims[0]}x{dims[1]} ratio {dims[2]:.2f}" if dims else ""))
    print("caption :")
    for _line in caption.splitlines():
        print("    " + _line)

    if not img:
        raise SystemExit("product has no cover image to post")

    # Markers are PER PLATFORM. One book can legitimately go to Facebook and Instagram; what
    # must never happen is the same book twice on the same surface.
    prev = json.load(open(marker, encoding="utf-8")) if os.path.exists(marker) else {}
    already = prev.get(a.platform)

    if a.preview_out:
        json.dump({"case": product["name"], "permalink": product.get("custom_permalink"),
                   "platform": a.platform, "image": img, "caption": caption,
                   "url": product.get("short_url"),
                   "price": round((product.get("price") or 0) / 100),
                   "already": bool(already)},
                  open(a.preview_out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"preview written: {a.preview_out}")

    if already and not a.force:
        print("")
        print(f"ALREADY POSTED to {a.platform} on {already.get('posted_at')} "
              f"as {already.get('id')} -- skipping. Pass --force to post again.")
        return

    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("FB_PAGE_ACCESS_TOKEN is not set")

    if a.dry_run:
        target = f"{GRAPH}/{IG_USER_ID}?fields=username,followers_count" if a.platform == "ig"             else f"{GRAPH}/{FB_PAGE_ID}?fields=name,fan_count"
        req = urllib.request.Request(f"{target}&access_token={urllib.parse.quote(token)}",
                                     headers={"User-Agent": "shadow-gasp-comic-pipeline"})
        with urllib.request.urlopen(req, timeout=60) as r:
            who = json.loads(r.read().decode())
        print("")
        print(f"DRY RUN -- token valid for {who}. Nothing posted.")
        return

    if a.platform == "ig":
        res = post_instagram(token, img, caption)
        post_id = res.get("id")
    else:
        try:
            res = post_photo(token, img, caption)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Facebook refused the post: {e.code} {e.read().decode()[:400]}")
        post_id = res.get("post_id") or res.get("id")

    print("")
    print(f"posted to {a.platform}: {post_id}")
    os.makedirs(MARKER_DIR, exist_ok=True)
    prev[a.platform] = {
        "id": post_id,
        "url": product.get("short_url"),
        "image": img,
        "posted_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    prev.setdefault("case", product["name"])
    prev.setdefault("permalink", product.get("custom_permalink"))
    json.dump(prev, open(marker, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"marker written: promo/{slug}.json")


if __name__ == "__main__":
    main()
