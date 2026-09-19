"""Regenerate ONLY the store hero on comics that are already published.

The hero is a product's FIRST cover, which makes it the storefront thumbnail and the preview
image -- the most-seen picture the shop has. Until 2026-09-19 it printed

    Issue 66  ·  40 pages  ·  Instant PDF download

baked into the pixels. gen_store_hero.py now prints "Issue 66 · true crime. told in ink", but
a code change cannot reach an image that was uploaded months ago, so every published comic
needs its hero rebuilt.

⭐ WHY NOT refresh_store_assets.py: that rebuilds all five covers from the case directory, and
cases/ is deleted after every build -- the panel art survives only inside the Kaggle kernel.
The four non-hero covers are already on Gumroad, though, so nothing needs regenerating but the
hero itself. Everything here is derived from the buyer's PDF, which Gumroad will hand back.

⭐ WHY NOT replace_covers(): it ADDS every new cover before removing the old ones, and Gumroad
caps a product at 8. Five existing plus five new is ten, so that path cannot run on these books
at all. Add one, remove one, reorder -- the count goes 5 -> 6 -> 5 and never dips below what
was there, so a failure at any step leaves the page with a full set of images.

    python pipeline_lib/refresh_store_hero.py --only the-label          # one product
    python pipeline_lib/refresh_store_hero.py --dry-run                 # report all
    python pipeline_lib/refresh_store_hero.py --apply                   # do all
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_and_deliver import gumroad  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (shadow-gasp-hero-refresh)"}


def buyer_pdf(product_id):
    """(url, name) of the PDF a buyer downloads -- the file embedded in the product content."""
    view = gumroad(["products", "view", product_id])
    files = [f for f in ((view.get("product", view) or {}).get("files") or [])
             if f.get("filetype") == "pdf" and f.get("url")]
    if not files:
        raise RuntimeError("no PDF file on this product")
    embedded = set(re.findall(r'"id":\s*"([^"]+)"',
                              json.dumps(gumroad(["products", "content", "get", product_id]))))
    pick = [f for f in files if f["id"] in embedded] or files[-1:]
    return pick[0]["url"], pick[0].get("name", "comic.pdf")


def download(url, dest):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, \
            open(dest, "wb") as out:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            out.write(b)
    return dest


def covers_of(product_id):
    view = gumroad(["products", "view", product_id])
    return (view.get("product", view) or {}).get("covers") or []


def meta_for(product):
    """The text the hero prints, taken from the live product rather than a script JSON.

    The script that built the book is long gone -- cases/ is wiped after every build -- and the
    storefront is the authority on what a comic is called anyway.

    ⭐ THE HOOK COMES FROM THE LANDING PAGE, not the description. The original hero printed
    script["promo_hook"], a line written to land in one breath ("He tried to make orphaned
    children stutter to prove a theory. It was never published."). The first sentence of the
    description is a different kind of writing -- accurate, and flat ("In 1939, a University of
    Iowa researcher used orphaned children as subjects in an experiment that tried to induce
    stuttering."). Rebuilding 75 heroes off the description would quietly downgrade the copy on
    every one of them. The landing page still carries the real hook, so take it from there and
    fall back to the description only when there is no page to read.
    """
    name = product.get("name") or ""
    m = re.search(r"#\s*0*(\d+)", name)
    title = name.split(":", 1)[-1].strip() or name

    hook = ""
    try:
        from store_design import cases as _cases
        live = _cases.live_landing(product)
        if live:
            hook = (_cases.from_live_page(product, live) or {}).get("hook") or ""
    except Exception as e:
        print(f"  (could not read the landing page for its hook: {e})")

    if not hook:
        desc = " ".join(re.sub(r"<[^>]+>", " ", product.get("description") or "").split())
        hook = re.split(r"(?<=[.!?])\s+", desc)[0][:160] if desc else ""
        print("  (no hook on the landing page -- using the description's first sentence)")

    return {"series": "SHADOW GASP", "title": title,
            "issue_no": m.group(1) if m else "", "hook": hook}


def refresh(product, workdir, apply_it):
    import gen_store_hero

    pid, name = product["id"], product["name"]
    before = covers_of(pid)
    if not before:
        print(f"  ! {name}: no covers at all -- skipped, this needs a look by hand")
        return False
    old_hero = before[0]
    print(f"  {len(before)} covers, hero={old_hero.get('id')}")

    url, fname = buyer_pdf(pid)
    pdf = download(url, os.path.join(workdir, "comic.pdf"))
    print(f"  fetched the buyer's PDF ({fname}, {os.path.getsize(pdf) / 1e6:.1f} MB)")

    meta = meta_for(product)
    hero = gen_store_hero.build(pdf, os.path.join(workdir, "store_hero.jpg"), meta=meta)
    print(f"  rebuilt hero: Issue {meta['issue_no']} · true crime. told in ink")

    if not apply_it:
        print("  (dry run -- nothing uploaded)")
        return True

    # 1. ADD first. The product is never left with fewer images than it started with.
    gumroad(["products", "covers", "add", pid, "--image", hero])
    after_add = covers_of(pid)
    new = [c for c in after_add if c.get("id") not in {c2.get("id") for c2 in before}]
    if len(new) != 1:
        raise RuntimeError(f"expected exactly one new cover, got {[c.get('id') for c in new]}")
    new_id = new[0]["id"]

    # 2. Then remove the old hero, and 3. put the new one back at the front. `covers add`
    #    appends, so without the reorder the hero would sit last and the storefront would show
    #    an interior panel as the product's thumbnail.
    gumroad(["products", "covers", "remove", pid, old_hero["id"]])
    order = [new_id] + [c["id"] for c in before[1:]]
    gumroad(["products", "covers", "reorder", pid, *order])

    final = covers_of(pid)
    ok = final and final[0].get("id") == new_id and len(final) == len(before)
    print(f"  {'✓' if ok else '✗'} now {len(final)} covers, hero={final[0].get('id') if final else None}")
    return bool(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="", help="one custom_permalink")
    ap.add_argument("--limit", type=int, default=0, help="stop after N products")
    ap.add_argument("--outdir", default="", help="keep the rebuilt heroes here, to be looked at")
    a = ap.parse_args()

    products = gumroad(["products", "list", "--all"]).get("products", [])
    comics = [p for p in products
              if re.search(r"SHADOW GASP\s*#\s*\d+", p.get("name") or "") and p.get("published")]
    comics.sort(key=lambda p: int(re.search(r"#\s*0*(\d+)", p["name"]).group(1)))
    if a.only:
        comics = [p for p in comics if p.get("custom_permalink") == a.only]
        if not comics:
            raise SystemExit(f"no published comic with permalink {a.only!r}")
    if a.limit:
        comics = comics[:a.limit]

    print(f"{len(comics)} published comic(s); apply={a.apply}\n")
    if a.outdir:
        os.makedirs(a.outdir, exist_ok=True)

    done = failed = 0
    for p in comics:
        print(f"{p['name']}  ({p.get('custom_permalink')})")
        # An --outdir keeps the rebuilt image after the run so it can actually be LOOKED at.
        # A hero is a picture; "the script said ok" is not a check that it reads right.
        wd = (os.path.join(a.outdir, p.get("custom_permalink") or p["id"]) if a.outdir
              else tempfile.mkdtemp(prefix="hero_"))
        os.makedirs(wd, exist_ok=True)
        try:
            done += 1 if refresh(p, wd, a.apply) else 0
        except Exception as e:
            print(f"  ✗ {type(e).__name__}: {e}")
            failed += 1
        finally:
            if not a.outdir:
                shutil.rmtree(wd, ignore_errors=True)
            else:
                # The PDFs are 25 MB+ each; only the image is worth keeping.
                for junk in glob.glob(os.path.join(wd, "*.pdf")):
                    os.remove(junk)
        print()

    print(f"ok {done}, failed {failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
