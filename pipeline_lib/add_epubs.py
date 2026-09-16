"""Give published comics an EPUB next to their PDF (build_epubs.yml).

    python pipeline_lib/add_epubs.py --issues all [--dry-run] [--force] [--epubcheck path/to/epubcheck.jar]

For each comic: download the PDF a buyer gets, convert it (pdf_to_epub.py), validate it with
epubcheck, upload it to the product and prune, then read the product back and require exactly one
PDF and one EPUB in the buyer's download list. Comics that already carry an EPUB are skipped
unless --force. One failure never stops the rest; the run fails at the end if any did.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pdf_to_epub  # noqa: E402
from build_carousel_store import buyer_pdf, download  # noqa: E402
from stage_and_deliver import _file_kind, gumroad, prune_stale_files  # noqa: E402


def issue_no(name):
    m = re.search(r"#\s*0*(\d+)", name or "")
    return int(m.group(1)) if m else None


def buyer_files(pid):
    """Kinds of the files a buyer downloads, e.g. ['epub', 'pdf']."""
    pages = gumroad(["products", "content", "get", pid])
    embedded = set(re.findall(r'"id":\s*"([^"]+)"', json.dumps(pages)))
    view = gumroad(["products", "view", pid])
    files = (view.get("product", view) or {}).get("files") or []
    return sorted(_file_kind(f) for f in files if f["id"] in embedded)


def epubcheck(jar, path):
    if not jar:
        print("  epubcheck: skipped (no jar)", flush=True)
        return
    r = subprocess.run(["java", "-jar", jar, "--quiet", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("epubcheck failed:\n" + (r.stdout + r.stderr)[-1500:])
    print("  epubcheck: valid", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", default="all", help="'all' or comma-separated issue numbers")
    ap.add_argument("--dry-run", action="store_true", help="build and validate, upload nothing")
    ap.add_argument("--force", action="store_true", help="rebuild even if the comic has an EPUB")
    ap.add_argument("--epubcheck", default="")
    a = ap.parse_args()

    products = [p for p in gumroad(["products", "list", "--all"]).get("products", [])
                if p.get("published") and issue_no(p.get("name"))]
    if a.issues != "all":
        want = {int(x) for x in a.issues.replace(" ", "").split(",") if x}
        products = [p for p in products if issue_no(p["name"]) in want]
    products.sort(key=lambda p: issue_no(p["name"]))

    done, skipped, failed = [], [], []
    for p in products:
        pid, name = p["id"], p["name"]
        print(f"#{issue_no(name)} {name}", flush=True)
        try:
            if not a.force and "epub" in buyer_files(pid):
                print("  already has an EPUB -- skipped", flush=True)
                skipped.append(name)
                continue
            with tempfile.TemporaryDirectory() as tmp:
                url, fname = buyer_pdf(pid)
                pdf = download(url, os.path.join(tmp, fname))
                epub = os.path.join(tmp, os.path.splitext(fname)[0] + ".epub")
                _, pages = pdf_to_epub.build(pdf, epub, name, pid)
                print(f"  built {os.path.basename(epub)}: {pages} pages, "
                      f"{os.path.getsize(epub) / 1e6:.1f} MB", flush=True)
                epubcheck(a.epubcheck, epub)
                if a.dry_run:
                    done.append(name)
                    continue
                gumroad(["products", "update", pid, "--file", epub, "--file-name", os.path.basename(epub)])
                prune_stale_files(pid)
            got = buyer_files(pid)
            if got != ["epub", "pdf"]:
                raise RuntimeError(f"buyer download list is {got}, expected ['epub', 'pdf']")
            print("  buyers now get: PDF + EPUB", flush=True)
            done.append(name)
        except Exception as e:  # noqa: BLE001 - one comic must not stop the rest
            print(f"::error::{name}: {e}", flush=True)
            failed.append(name)

    print(f"\nEPUB {'built (dry run)' if a.dry_run else 'attached'}: {len(done)}  "
          f"skipped: {len(skipped)}  failed: {len(failed)} {failed or ''}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
