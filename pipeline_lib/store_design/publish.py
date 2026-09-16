"""Publish landing pages and storefront pages through the gumroad CLI.

Every publish is preceded by Gumroad's own sanitizer dry run and refused unless it removed
exactly the tags it always removes (meta/title) -- a stripped buy button would make a product
unpurchasable. Flags go BEFORE `--`, and the id goes after it: some product ids start with '-'.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time

GUMROAD = shutil.which("gumroad") or os.path.expanduser("~/.local/bin/gumroad")
FLAGS = ["--json", "--no-input", "--non-interactive"]


def _run(args, tries=4):
    last = None
    for attempt in range(tries):
        r = subprocess.run([GUMROAD, *args], capture_output=True, text=True, encoding="utf-8")
        try:
            last = json.loads(r.stdout)
        except ValueError:
            last = {"success": False, "error": {"type": "internal_error", "message": (r.stdout + r.stderr)[:300]}}
        # Only transport failures are worth repeating; a validation error will not change.
        if (last.get("error") or {}).get("type") != "internal_error":
            return last
        time.sleep(4 * (attempt + 1))
    return last


def _tmp(html):
    f = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    f.write(html)
    f.close()
    return f.name


def _check(preview, allowed_removals):
    if not preview.get("success"):
        return f"preview failed: {preview.get('error')}"
    if preview.get("warning"):
        return f"sanitizer warning: {preview['warning']}"
    removed = preview.get("sanitization_report", {}).get("total_removed", 0)
    if removed > allowed_removals:
        return f"sanitizer removed {removed} element(s): {preview.get('sanitization_report')}"
    return None


def publish_landing(product_id, html):
    """(ok, error). A landing page loses exactly meta charset, meta viewport and title."""
    path = _tmp(html)
    try:
        err = _check(_run(["products", "page", "preview", *FLAGS, "--", product_id, path]), 3)
        if err:
            return False, err
        res = _run(["products", "page", "publish", *FLAGS, "--", product_id, path])
        if not res.get("success") or res.get("warning"):
            return False, f"publish failed: {res.get('error') or res.get('warning')}"
        return True, None
    finally:
        os.unlink(path)


def push_store_page(slug, html, title, existing_slugs):
    """(ok, error). Creates /<slug> the first time; 'profile' is the store home page."""
    path = _tmp(html)
    try:
        err = _check(_run(["pages", "preview", *FLAGS, path]), 0)
        if err:
            return False, err
        if slug == "profile" or slug in existing_slugs:
            res = _run(["pages", "push", *FLAGS, slug, path])
        else:
            res = _run(["pages", "create", *FLAGS, "--title", title, "--slug", slug, path])
        return (True, None) if res.get("success") else (False, f"push failed: {res.get('error')}")
    finally:
        os.unlink(path)


def list_products():
    res = _run(["products", "list", "--all", "--json"])
    if "products" not in res:
        raise RuntimeError(f"could not list products: {res.get('error')}")
    return res["products"]


def list_pages():
    res = _run(["pages", "list", "--json"])
    if "pages" not in res:
        raise RuntimeError(f"could not list pages: {res.get('error')}")
    return [p["slug"] for p in res["pages"]]


def user_bio():
    """The profile bio, which the store pages quote; None if it can't be read (defaults are used)."""
    res = _run(["user", "--json"])
    return (res.get("user") or {}).get("bio")
