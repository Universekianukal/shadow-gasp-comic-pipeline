"""Pick the next comic for the carousel / promo autopilots.

New file, used only by auto_carousel.yml and auto_promo.yml. Nothing that already
existed imports it, so the manual /carousel and /promo routes are unaffected.

The rule for both streams is the same, and it is deliberately the SAME rule the
existing posted-markers already encode, so the autopilot and a manual Telegram tap
can never disagree about what has gone out:

  carousel -- carousel/entries/<iii>-<slug>.json exists, and carousel/<slug>.posted.json
              has no entry for that platform.
  promo    -- promo/<slug>.json has no entry for that platform.

In both cases the posting script itself is still the real guard: post_ig_carousel /
post_threads_carousel / post_fb_promo each re-check their own marker and refuse a
second post unless --force. This module only decides what to OFFER them, so a slug
mismatch here can never cause a double post -- at worst the run is a no-op.

A comic is only eligible once its Gumroad product is PUBLISHED. Posting a carousel or
promo for a draft would funnel people at a product page that is still a draft (which
returns HTTP 200, so nothing would look wrong), and the COMIC-comment DM funnel would
hand out a dead link.
"""

import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Reuse the real slug function rather than copying it: a marker only lines up
    # with the rest of the ledgers if this slug matches pipeline.yml's exactly,
    # and two copies would drift. post_fb_promo imports only stdlib at module
    # level (Pillow is optional, inside a try), so this is cheap and safe.
    from post_fb_promo import slugify
except Exception:  # pragma: no cover - only if run outside the repo
    def slugify(name):
        return re.sub(r"[^a-z0-9-]", "", (name or "").lower().replace(" ", "-"))[:40]


def find_product(products, case_or_permalink):
    """The Gumroad product for this case, published or not.

    Mirrors post_fb_promo.find_product's matching rules deliberately, so the
    autopilot resolves a comic to exactly the product post_promo.yml would --
    but against a product list fetched ONCE, instead of shelling out to the
    Gumroad CLI per candidate.

    Product names are "SHADOW GASP #NN: TITLE" and never the raw case name, so
    an exact permalink/id hit is tried first and a two-way slug containment
    check second.
    """
    want = slugify(case_or_permalink)
    best = None
    for p in products or []:
        if p.get("custom_permalink") == case_or_permalink or p.get("id") == case_or_permalink:
            return p
        name_slug = slugify(p.get("name", ""))
        if want and (want in name_slug or name_slug in want):
            best = p
    return best


def is_published(products, case_or_permalink):
    """True only if a matching product exists AND is published.

    A draft must never be posted: the Gumroad page for a draft serves HTTP 200,
    so nothing would look broken, but every click and every COMIC-comment DM
    would land on a dead product.
    """
    p = find_product(products, case_or_permalink)
    return bool(p and p.get("published"))


def load_entries(root="."):
    """Every carousel entry, ordered by issue number (oldest comic first)."""
    d = pathlib.Path(root) / "carousel" / "entries"
    entries = []
    for f in sorted(d.glob("*.json")):
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if e.get("slug"):
            entries.append(e)
    entries.sort(key=lambda e: (e.get("issue") or 0))
    return entries


def _marker_platforms(path):
    """Which platforms this marker file already records a post for."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError, FileNotFoundError):
        return set()
    if not isinstance(data, dict):
        return set()
    # Both marker shapes are {platform: {id, posted_at, ...}}.
    return {k for k, v in data.items() if isinstance(v, dict) and v.get("id")}


def posted_platforms(kind, slug, root="."):
    root = pathlib.Path(root)
    if kind == "carousel":
        return _marker_platforms(root / "carousel" / f"{slug}.posted.json")
    return _marker_platforms(root / "promo" / f"{slug}.json")


def pick(kind, wanted, products, root=".", force_slug=""):
    """The next comic that still needs at least one of `wanted`.

    Returns (entry, [platforms it still needs]) or (None, reason).
    Oldest issue first, so the backlog drains in publication order rather than
    jumping around.
    """
    entries = load_entries(root)
    if not entries:
        return None, "no carousel entries found"

    if force_slug:
        entries = [e for e in entries if e["slug"] == force_slug]
        if not entries:
            return None, f"no entry with slug {force_slug!r}"

    saw_unpublished = 0
    for e in entries:
        if products is not None and not _entry_published(e, products):
            saw_unpublished += 1
            continue
        need = [p for p in wanted if p not in posted_platforms(kind, e["slug"], root)]
        if need:
            return e, need

    if force_slug:
        return None, f"{force_slug} is already posted everywhere, or its comic is not published"
    return None, (
        f"nothing left -- every published comic has been posted ({saw_unpublished} "
        f"unpublished comic(s) skipped)"
    )


def _entry_published(entry, products):
    """A carousel entry is eligible if EITHER its permalink or its title resolves
    to a published product -- entries carry a short permalink while Gumroad names
    are "SHADOW GASP #NN: TITLE", and different comics match on different ones."""
    for key in (entry.get("permalink"), entry.get("slug"), entry.get("title")):
        if key and is_published(products, key):
            return True
    return False


def remaining(kind, wanted, products, root="."):
    """How many comics still need at least one platform -- for the Telegram line."""
    n = 0
    for e in load_entries(root):
        if products is not None and not _entry_published(e, products):
            continue
        if [p for p in wanted if p not in posted_platforms(kind, e["slug"], root)]:
            n += 1
    return n


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["carousel", "promo"])
    ap.add_argument("--platforms", required=True,
                    help="comma separated, e.g. ig,fb,th")
    ap.add_argument("--products", default="",
                    help="JSON from `gumroad products list --all` (omit to skip the published check)")
    ap.add_argument("--slug", default="", help="force one slug instead of auto-picking")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()

    wanted = [p.strip() for p in a.platforms.split(",") if p.strip()]

    products = None
    if a.products:
        raw = json.loads(pathlib.Path(a.products).read_text(encoding="utf-8"))
        products = raw.get("products") if isinstance(raw, dict) else raw

    entry, info = pick(a.kind, wanted, products, a.root, a.slug)

    lines = []
    if entry is None:
        lines.append("slug=")
        lines.append(f"reason={info}")
    else:
        lines.append(f"slug={entry['slug']}")
        lines.append(f"permalink={entry.get('permalink') or entry['slug']}")
        lines.append(f"issue={entry.get('issue') or ''}")
        lines.append(f"title={entry.get('title') or ''}")
        lines.append(f"need={','.join(info)}")
        for p in wanted:
            lines.append(f"need_{p}={'true' if p in info else 'false'}")
        lines.append(f"remaining={remaining(a.kind, wanted, products, a.root)}")

    out = "\n".join(lines)
    print(out)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(out + "\n")


if __name__ == "__main__":
    main()
