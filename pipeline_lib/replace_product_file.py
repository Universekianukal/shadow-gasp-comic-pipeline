"""Swap the downloadable PDF on a PUBLISHED product for the freshly rebuilt one. FILE ONLY.

Why this exists. On 2026-09-14 Kaggle's status API answered 503 and three builds shipped books of
"ART PENDING" placeholders (see the fetch check in gen_flux_kaggle.run_batch). They were published
before anyone noticed: $24 products whose download was a 108 KB PDF of grey boxes. A rerun rebuilt
the real books from the finished kernels, but stage_draft() correctly refuses to touch a published
product, and refresh_store_assets.py only does images. Nothing could replace the file itself.

This is that narrow half, run only when someone names the product on purpose:
  - the same seller check and product resolution as refresh_store_assets.py,
  - refuses if the rebuilt PDF still carries a single ART PENDING page,
  - `products update <id> --file` (which APPENDS a file embed), then prune_stale_files() so the
    buyer's download list holds the new PDF, then a matching EPUB (attach_epub),
  - reads the product back and prints what a buyer now gets.
It never touches price, name, description, tags, permalink, covers, thumbnail or published state.

Usage (from the repo root, after the case has been built):
    python pipeline_lib/replace_product_file.py --case-dir cases/<slug> --product <id-or-permalink>
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from refresh_store_assets import assert_account, build_pdf, placeholder_pages, resolve_product  # noqa: E402
from stage_and_deliver import _file_kind, attach_epub, gumroad, prune_stale_files  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--product", required=True, help="Gumroad product id or custom permalink")
    ap.add_argument("--expect-account", default="Shadow Gasp",
                    help="Seller name that must be logged in; '' to skip the check")
    ap.add_argument("--min-mb", type=float, default=2.0,
                    help="Refuse a rebuilt PDF smaller than this (the placeholder books were ~0.1 MB)")
    ap.add_argument("--dry-run", action="store_true", help="Build and check, write nothing")
    args = ap.parse_args()

    assert_account(args.expect_account)
    product = resolve_product(args.product)
    pid = product["id"]
    print(f"product: {product['name']} ({pid}) published={product.get('published')} "
          f"sales={product.get('sales_count')} file_info={product.get('file_info')}", flush=True)

    script, pdf_path = build_pdf(args.case_dir)
    mb = os.path.getsize(pdf_path) / 1e6
    blanks = placeholder_pages(pdf_path)
    print(f"rebuilt PDF: {os.path.basename(pdf_path)}  {mb:.1f} MB  placeholder pages: {blanks}", flush=True)
    if blanks is None:
        raise SystemExit("cannot inspect the PDF (PyMuPDF missing) -- refusing to replace a live file blind")
    if blanks:
        raise SystemExit(f"{blanks} page(s) are still ART PENDING -- the art did not come back from Kaggle. "
                         "Refusing to replace one blank book with another.")
    if mb < args.min_mb:
        raise SystemExit(f"rebuilt PDF is only {mb:.2f} MB -- that is the size of a placeholder book, not a "
                         f"finished one. Refusing.")

    if args.dry_run:
        print("dry run -- nothing written to Gumroad", flush=True)
        return

    gumroad(["products", "update", pid, "--file", pdf_path, "--file-name", os.path.basename(pdf_path)])
    print("uploaded the rebuilt PDF", flush=True)
    prune_stale_files(pid)
    # The EPUB is made from the PDF, so a replaced PDF needs a matching EPUB.
    try:
        attach_epub(pid, pdf_path, product["name"])
    except Exception as e:
        print(f"WARNING: EPUB not refreshed ({e})", flush=True)

    # ⭐ Read it back: what a buyer downloads is the content document's fileEmbeds, not `files`.
    pages = gumroad(["products", "content", "get", pid])
    if isinstance(pages, dict):
        pages = pages.get("pages", [pages])
    embeds = [(n.get("attrs") or {}).get("id") for page in pages
              for n in ((page.get("description") or {}).get("content") or []) if n.get("type") == "fileEmbed"]
    view = gumroad(["products", "view", pid])
    after = view.get("product", view) or {}
    kinds = {f["id"]: _file_kind(f) for f in after.get("files") or []}
    got = sorted(kinds.get(i, "?") for i in embeds)
    print(f"buyer-visible files now: {got}  file_info: {after.get('file_info')}  "
          f"published={after.get('published')}", flush=True)
    if got.count("pdf") != 1 or len(got) > 2:
        raise SystemExit(f"expected exactly 1 PDF (+ 1 EPUB) after the swap, found {got} -- check "
                         "the product's Content tab by hand")


if __name__ == "__main__":
    main()
