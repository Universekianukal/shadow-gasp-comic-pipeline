"""Rewrite the detail line on promo posts that are already live.

The promo caption used to read

    A documentary comic · 34pp · instant PDF

and now reads "A documentary comic · true crime. told in ink" (owner, 2026-09-19: the format
and the page count both go). post_fb_promo.py only affects the NEXT post, so the handful
already published need this.

⭐ SURGICAL, NOT REBUILT. It would be easier to call build_caption() again and send the result,
and it would be wrong: the hook is taken from the product description, which has been edited
since, and the price line was only dropped on 09-17. Rebuilding would quietly rewrite posts in
ways nobody asked for. So this replaces THAT ONE LINE in the live message and leaves every
other character alone.

⭐ FACEBOOK ONLY. Instagram and Threads have no edit endpoint at all -- the only way to change
a published caption there is to delete and repost, which forfeits the post's engagement and its
permalink. Those are handled by hand, deliberately, not by this script.

    python pipeline_lib/retro_promo_caption.py            # report, change nothing
    python pipeline_lib/retro_promo_caption.py --apply    # write it back
"""
import argparse
import glob
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v19.0"

# What the line should say now. Kept here rather than imported from post_fb_promo so that a
# later edit to the live caption cannot silently rewrite posts that are already out.
NEW_DETAIL = "A documentary comic · true crime. told in ink"

# The old line in all its forms: "A documentary comic", then any number of " · <bit>" parts
# (34pp, instant PDF, and on the oldest posts a price). Anchored to the whole line so a
# stray mention of the phrase inside the hook is left alone.
DETAIL_RE = re.compile(r"^A documentary comic(?: · [^\n]*)?$", re.MULTILINE)


def graph(method, path, params, token):
    params = dict(params or {}, access_token=token)
    if method == "GET":
        url = f"{GRAPH}/{path}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(f"{GRAPH}/{path}",
                                     data=urllib.parse.urlencode(params).encode(),
                                     method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def markers(root="."):
    """Every promo marker that names a real Facebook post.

    norjak's fb id is the literal string "manual" -- it was posted by hand before this
    pipeline existed and recorded only so /promo would not offer it twice. There is no post
    to edit, so it is skipped rather than sent to the API as an id.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(root, "promo", "*.json"))):
        try:
            d = json.loads(open(path, encoding="utf-8").read())
        except Exception as e:
            print(f"  ! {path}: unreadable ({e})")
            continue
        fb = (d.get("fb") or {}).get("id")
        if not fb:
            continue
        if fb == "manual":
            print(f"  - {d.get('permalink')}: posted by hand, no post id to edit -- skipped")
            continue
        out.append((d.get("permalink") or os.path.basename(path), fb))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the change back (default: report only)")
    ap.add_argument("--only", default="", help="limit to one permalink, for testing a single post first")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()

    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("FB_PAGE_ACCESS_TOKEN is not set")

    posts = markers(a.root)
    if a.only:
        posts = [p for p in posts if p[0] == a.only]
    print(f"{len(posts)} Facebook promo post(s) to inspect\n")

    changed = skipped = failed = 0
    for slug, pid in posts:
        try:
            msg = graph("GET", pid, {"fields": "message"}, token).get("message", "")
        except urllib.error.HTTPError as e:
            print(f"✗ {slug}: could not read post ({e.code} {e.read().decode('utf-8','replace')[:160]})")
            failed += 1
            continue

        if not DETAIL_RE.search(msg or ""):
            print(f"· {slug}: no detail line to change -- left alone")
            skipped += 1
            continue

        new = DETAIL_RE.sub(NEW_DETAIL, msg)
        old_line = DETAIL_RE.search(msg).group(0)
        print(f"{'→' if a.apply else '?'} {slug}  ({pid})")
        print(f"    was: {old_line}")
        print(f"    now: {NEW_DETAIL}")

        if not a.apply:
            continue
        try:
            graph("POST", pid, {"message": new}, token)
        except urllib.error.HTTPError as e:
            print(f"    ✗ edit refused: {e.code} {e.read().decode('utf-8','replace')[:200]}")
            failed += 1
            continue
        # ⭐ Read it back. A Graph write can answer {"success": true} and leave a photo post's
        # message exactly as it was; the only proof the edit took is the post itself.
        back = graph("GET", pid, {"fields": "message"}, token).get("message", "")
        if DETAIL_RE.search(back or "") and NEW_DETAIL in back:
            print("    ✓ verified live")
            changed += 1
        else:
            print("    ✗ API accepted the write but the post still shows the old text")
            failed += 1

    print(f"\nchanged {changed}, unchanged {skipped}, failed {failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
