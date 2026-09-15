"""Carousel for a NEW comic, built at build time from the book itself (called by stage_and_deliver).

This is the only moment the real pages exist: cases/ is deleted when the build ends. So the build files
a ready-made carousel under carousel/ (committed with the ledgers) and /carousel <n> in Telegram shows it.

  slide 1   = the first splash panel from the opening third (raw art, no lettering), else the promo
              background, else the cover page -- with the script's promo_hook
  slides 2+ = three lettered story pages spread across the opening third -- never the ending
  last      = the cover page

Never fatal: the caller wraps this in try/except, because a finished, priced book must not be lost to a
marketing asset.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_carousel  # noqa: E402

STORY_OFFSET = 2        # PDF page 1 = cover, page 2 = title page, then the script's story pages


def render(doc, index, dest, dpi=200):
    doc[index].get_pixmap(dpi=dpi).save(dest)
    return dest


def pick_pages(n_story, n_pdf, exclude=None):
    """Three PDF page indexes spread across the opening third of the story, never the page whose
    splash art is already slide 1 (no picture may repeat in one carousel)."""
    third = max(4, n_story // 3)
    pool = [i for i in range(third) if i != exclude]
    picks = sorted({pool[0], pool[len(pool) // 2], pool[-1]}) if pool else []
    return [STORY_OFFSET + i for i in picks if STORY_OFFSET + i < n_pdf]


def build(comic_dir, script, pdf_path, permalink, repo=gen_carousel.REPO):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    doc = pymupdf.open(pdf_path)
    tmp = tempfile.mkdtemp(prefix="carousel_book_")
    story = script.get("pages", [])
    early = story[:max(1, len(story) // 3)]

    hook_art, hook_idx = None, None
    for i, page in enumerate(early):
        f = (page.get("panel") or {}).get("file") if page.get("type") == "splash" else None
        if f and os.path.exists(os.path.join(comic_dir, "panels", f)):
            hook_art, hook_idx = os.path.join(comic_dir, "panels", f), i   # that page is not reused below
            break
    if not hook_art and os.path.exists(os.path.join(comic_dir, "panels", "promo_bg.jpg")):
        hook_art = os.path.join(comic_dir, "panels", "promo_bg.jpg")
    cover = render(doc, 0, os.path.join(tmp, "cover.png"))
    hook_art = hook_art or cover

    art = [render(doc, i, os.path.join(tmp, f"p{i + 1}.png")) for i in pick_pages(len(story), doc.page_count, hook_idx)]
    if not art:
        raise RuntimeError("no story pages to put in a carousel")

    issue = int(str(script.get("issue_no", "0")).lstrip("0") or 0)
    title = script.get("title", "").strip()
    hook = (script.get("promo_hook") or title).strip()
    pages = str(doc.page_count)
    slides = gen_carousel.build(hook_art, art, cover, hook, title, issue, pages, issue == 1, os.path.join(tmp, "slides"))
    caption = gen_carousel.default_caption(hook, issue, title, pages)
    entry = gen_carousel.publish_entry(slides, permalink, issue, title, permalink, caption, repo=repo)
    print(f"carousel: {len(slides)} slides from the book -> carousel/{entry['dir']} "
          f"(pages {[i + 1 for i in pick_pages(len(story), doc.page_count, hook_idx)]})", flush=True)
    return entry
