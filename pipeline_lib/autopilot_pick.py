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


def published_permalinks(products):
    """Permalinks of every PUBLISHED Gumroad product, lowercased.

    `products` is the list from `gumroad products list --all` -- the --all matters,
    the API returns only the newest 10 without it.
    """
    out = set()
    for p in products or []:
        if not p.get("published"):
            continue
        for key in ("permalink", "custom_permalink"):
            v = (p.get(key) or "").strip().lower()
            if v:
                out.add(v)
    return out


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


def pick(kind, wanted, published, root=".", force_slug=""):
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
        permalink = (e.get("permalink") or e["slug"]).strip().lower()
        if published is not None and permalink not in published:
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


def remaining(kind, wanted, published, root="."):
    """How many comics still need at least one platform -- for the Telegram line."""
    n = 0
    for e in load_entries(root):
        permalink = (e.get("permalink") or e["slug"]).strip().lower()
        if published is not None and permalink not in published:
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

    published = None
    if a.products:
        raw = json.loads(pathlib.Path(a.products).read_text(encoding="utf-8"))
        published = published_permalinks(
            raw.get("products") if isinstance(raw, dict) else raw)

    entry, info = pick(a.kind, wanted, published, a.root, a.slug)

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
        lines.append(f"remaining={remaining(a.kind, wanted, published, a.root)}")

    out = "\n".join(lines)
    print(out)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(out + "\n")


if __name__ == "__main__":
    main()
