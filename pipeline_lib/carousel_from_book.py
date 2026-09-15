"""Carousel for a NEW comic at build time (called by stage_and_deliver right after the PDF is made).

Hands the fresh PDF to carousel_from_pdf -- the same page picker and look used for every other comic,
including the ones rebuilt from their Gumroad PDFs -- and files the result under carousel/ (committed
with the ledgers), so /carousel <n> in Telegram shows it the moment the comic exists.

Never fatal: the caller wraps this in try/except, because a finished, priced book must not be lost to a
marketing asset.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import carousel_from_pdf  # noqa: E402


def build(comic_dir, script, pdf_path, permalink, repo=None):
    issue = int(str(script.get("issue_no", "0")).lstrip("0") or 0)
    title = (script.get("title") or "").strip()
    hook = (script.get("promo_hook") or title).strip()
    entry = carousel_from_pdf.build(pdf_path, issue, title, hook, permalink, repo=repo or carousel_from_pdf.g.REPO)
    print(f"carousel: {entry['slides']} slides from the book -> carousel/{entry['dir']} "
          f"(hook p{entry['picks']['hook']}, story {entry['picks']['story']})", flush=True)
    return entry
