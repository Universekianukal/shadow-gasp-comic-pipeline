"""Re-point a PUBLISHED product's storefront images at the art it actually ships with.

Why this exists. A build whose Kaggle art has not landed yet still produces a complete,
correct-looking book: build_comic draws an "ART PENDING" placeholder wherever a panel file is
missing, so the cover page renders as a titled grey rectangle and every downstream image --
the 16:9 product hero, the 1080 square tile, the thumbnail -- is generated faithfully from
that placeholder and uploaded to Gumroad. BELLA IN THE WYCH ELM (#30) went on sale that way
on 2026-09-09: three blank images on a $24 product page.

Re-running the pipeline fixed the PDF and nothing else. stage_draft() deliberately REFUSES to
touch a product that is already published or has sales -- correctly, because that path also
replaces the downloadable file and the price, and silently rewriting what buyers can already
see is far worse than a stale image. So the rerun printed

    WARNING: Gumroad draft NOT staged (permalink '...' belongs to a PUBLISHED product ...)

and the storefront kept the placeholders. This script is the narrow, safe half of that
refusal: IMAGES ONLY.

It never touches the file, the price, the description, the tags, the permalink or the
published state. The worst it can do is put the wrong picture on a product page, which is
exactly what it is here to fix, and which is undoable.

Usage (from the repo root, after the case has been built):

    python pipeline_lib/refresh_store_assets.py \
        --case-dir cases/<slug> --product <product-id-or-permalink>
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from stage_and_deliver import gumroad, pick_preview_panels, slugify  # noqa: E402


def resolve_product(ref):
    """Accept either a Gumroad product id or a custom permalink; return the product dict.

    Refuses to guess. A wrong id here writes someone else's storefront.
    """
    products = gumroad(["products", "list"]).get("products", [])
    for p in products:
        if p.get("id") == ref:
            return p
    for p in products:
        if p.get("custom_permalink") == ref \
                or (p.get("short_url") or "").rstrip("/").endswith("/" + ref):
            return p
    known = ", ".join(sorted(p.get("custom_permalink") or p.get("id") for p in products))
    raise SystemExit(f"no product matches {ref!r}. This account has: {known}")


def assert_account(expected):
    """⚠️ Verify the shop BEFORE any write, never after.

    The gumroad CLI carries a stored login and GUMROAD_ACCESS_TOKEN can override it per
    process, so "which shop am I in" is genuinely ambiguous at call time. Covers pushed to the
    wrong seller are visible in the wrong storefront the moment they land.
    """
    name = (gumroad(["user"]).get("user") or {}).get("name")
    print(f"gumroad account: {name}", flush=True)
    if expected and (name or "").strip().lower() != expected.strip().lower():
        raise SystemExit(f"refusing to write: expected the {expected!r} shop, logged in as {name!r}")


def build_pdf(comic_dir):
    scripts = glob.glob(os.path.join(comic_dir, "script_issue*.json"))
    if not scripts:
        raise SystemExit(f"no script_issueNN.json in {comic_dir}")
    script = json.load(open(scripts[0], encoding="utf-8"))
    # Rebuild rather than trusting a stale PDF on disk: this runs on a fresh runner where the
    # only thing that exists is what this run just fetched from the Kaggle kernel.
    subprocess.run([sys.executable, os.path.join(HERE, "build_comic.py"),
                    "--script", os.path.abspath(scripts[0])], cwd=comic_dir, check=True)
    pdf_path = os.path.join(comic_dir, script["output"])
    if not os.path.exists(pdf_path):
        raise SystemExit(f"build produced no {pdf_path}")
    return script, pdf_path


def placeholder_pages(pdf_path):
    """Count pages still carrying the missing-art placeholder.

    The whole failure mode this script exists for is invisible to every other check: the PDF is
    valid, the page count is right, the text is right, and the art is a grey rectangle. Look for
    the placeholder's own caption before shipping these images to a storefront, so a refresh run
    that fetched no art fails loudly instead of uploading the same blanks a second time.
    """
    try:
        import fitz
    except ImportError:
        return None
    doc = fitz.open(pdf_path)
    return sum(1 for page in doc if "ART PENDING" in page.get_text().upper())


def build_images(comic_dir, script, pdf_path):
    """The three shapes the storefront wants, all derived from the finished cover page."""
    import gen_store_hero
    import gen_store_tile
    import gen_promo_card

    hero = gen_store_hero.build(
        pdf_path, os.path.join(comic_dir, "store_hero.jpg"),
        meta={"series": script.get("series"), "title": script.get("title"),
              "issue_no": script.get("issue_no"), "hook": script.get("promo_hook")})
    tile = gen_store_tile.build(pdf_path, os.path.join(comic_dir, "store_tile.jpg"))
    # Same gallery order a first staging produces, so a refreshed page looks like a normally
    # staged one rather than a repair: promo card, then early interior panels.
    card = gen_promo_card.build(pdf_path, os.path.join(comic_dir, "promo.jpg"))
    previews = [card] + pick_preview_panels(comic_dir, script)
    return hero, tile, [p for p in previews if p and os.path.exists(p)]


def replace_covers(product_id, images):
    """ADD the new covers first, THEN remove the ones that were there before.

    ⭐ Order is the whole point. `covers add` APPENDS -- there is no replace -- and Gumroad caps
    a product at 8 previews, so the naive fix (remove everything, then add) leaves the product
    page imageless for the length of the upload, and any failure in the middle strands a live
    $24 product with no picture at all. Adding first means the worst outcome is a page with too
    many images, which is untidy rather than broken.

    The old ids are captured BEFORE the adds for the same reason stale ids once made `covers
    remove` look broken: they have to be the ids of the covers being replaced, not whatever the
    list happens to hold afterwards.
    """
    view = gumroad(["products", "view", product_id])
    before = [c["id"] for c in (view.get("product", view) or {}).get("covers", []) or []]
    print(f"covers before: {len(before)} {before}", flush=True)
    if len(before) + len(images) > 8:
        raise SystemExit(
            f"{len(before)} existing + {len(images)} new covers exceeds Gumroad's limit of 8. "
            "Remove some by hand first; adding fewer would leave a half-refreshed gallery.")

    for path in images:
        gumroad(["products", "covers", "add", product_id, "--image", path])
        print(f"  added {os.path.basename(path)}", flush=True)
    for cid in before:
        gumroad(["products", "covers", "remove", product_id, cid])
        print(f"  removed old cover {cid}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--product", required=True,
                    help="Gumroad product id or custom permalink")
    ap.add_argument("--expect-account", default="Shadow Gasp",
                    help="Seller name that must be logged in; '' to skip the check")
    ap.add_argument("--allow-placeholder-art", action="store_true",
                    help="Upload even if the rebuilt PDF still says ART PENDING")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build the images and report, write nothing to Gumroad")
    args = ap.parse_args()

    assert_account(args.expect_account)
    product = resolve_product(args.product)
    product_id = product["id"]
    print(f"product: {product['name']} ({product_id}) "
          f"published={product.get('published')}", flush=True)

    script, pdf_path = build_pdf(args.case_dir)

    blanks = placeholder_pages(pdf_path)
    print(f"placeholder pages in the rebuilt PDF: {blanks}", flush=True)
    if blanks and not args.allow_placeholder_art:
        raise SystemExit(
            f"{blanks} page(s) of the rebuilt book are still ART PENDING -- the art did not come "
            "back from Kaggle. Refusing to upload blank storefront images over blank ones. "
            "Fix the art, or pass --allow-placeholder-art if this is deliberate.")

    hero, tile, previews = build_images(args.case_dir, script, pdf_path)
    print(f"built hero={hero} tile={tile} previews={len(previews)}", flush=True)

    if args.dry_run:
        print("dry run -- nothing written to Gumroad", flush=True)
        return

    replace_covers(product_id, [hero] + previews)
    gumroad(["products", "thumbnail", "set", product_id, "--image", tile])
    print("thumbnail set", flush=True)

    # ⭐ Read it back. A write returning success is not proof the storefront changed, and
    # "refreshed!" over an unchanged placeholder is worse than an error.
    view = gumroad(["products", "view", product_id])
    after = view.get("product", view) or {}
    print(f"covers after: {[c['id'] for c in after.get('covers', []) or []]}", flush=True)
    print(f"thumbnail_url: {after.get('thumbnail_url')}", flush=True)
    print(f"preview_url:   {after.get('preview_url')}", flush=True)


if __name__ == "__main__":
    main()
