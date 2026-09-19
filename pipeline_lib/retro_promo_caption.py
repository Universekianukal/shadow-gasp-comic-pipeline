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


THREADS_GRAPH = "https://graph.threads.net/v1.0"


def threads_report(root="."):
    """Read-only: what the live Threads promos actually say.

    Threads has no edit endpoint, so the only way to change one is to delete and repost, which
    forfeits the post's engagement and its permalink. That is a decision someone has to take
    with the text in front of them -- so this prints it and stops. It never deletes anything.
    """
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        print("THREADS_ACCESS_TOKEN not set -- skipping the Threads report")
        return
    for path in sorted(glob.glob(os.path.join(root, "promo", "*.json"))):
        try:
            d = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            continue
        mid = (d.get("th") or {}).get("id")
        if not mid:
            continue
        q = urllib.parse.urlencode({"fields": "text,permalink,timestamp", "access_token": token})
        try:
            req = urllib.request.Request(f"{THREADS_GRAPH}/{mid}?{q}",
                                         headers={"User-Agent": "shadow-gasp-promo/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                post = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"✗ threads {d.get('permalink')}: {e.code} {e.read().decode('utf-8','replace')[:160]}")
            continue
        text = post.get("text") or ""
        stray = sorted({w for w in ("PDF", "pdf", "instant", "Instant", "download") if w in text})
        print(f"\nTHREADS {d.get('permalink')} ({mid})  {post.get('timestamp','')}")
        print(f"  {post.get('permalink','')}")
        print(f"  format wording present: {stray if stray else 'NONE'}")
        for line in text.split("\n"):
            print(f"  | {line}")


def threads_list(limit=25):
    """List what is actually ON the account, newest first. Read-only.

    ⭐ A GET on a single id cannot answer "was this deleted?". Meta returns one 400 for all of
    "does not exist, cannot be loaded due to missing permissions, or does not support this
    operation", so a missing post and a scope problem look identical. Listing the account's own
    threads says which posts exist, by id, without guessing.
    """
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("THREADS_ACCESS_TOKEN is not set")
    q = urllib.parse.urlencode({"fields": "id,text,permalink,timestamp,media_type",
                                "limit": limit, "access_token": token})
    req = urllib.request.Request(f"{THREADS_GRAPH}/me/threads?{q}",
                                 headers={"User-Agent": "shadow-gasp-promo/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"could not list: {e.code} {e.read().decode('utf-8','replace')[:300]}")
        raise SystemExit(1)
    items = data.get("data") or []
    print(f"{len(items)} post(s) live on the account, newest first")
    print("")
    for t in items:
        text = t.get("text") or ""
        first = (text.splitlines()[0][:88] if text else "")
        print(f"{t.get('id')}  {t.get('timestamp','')[:19]}  {t.get('media_type','')}")
        print(f"   {t.get('permalink','')}")
        print(f"   {first}")
    return items


def threads_delete(media_id):
    """Remove one Threads post by id. Used to retire a post that has been REPLACED.

    ⭐ The replacement is published FIRST and checked, then the old one goes. Deleting first
    would leave a gap if the repost then failed, and a Threads post cannot be un-deleted.

    Takes a bare id rather than a permalink on purpose: by the time this runs, promo/<slug>.json
    already names the NEW post, so reading the id from the marker would delete the replacement.
    """
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("THREADS_ACCESS_TOKEN is not set")
    q = urllib.parse.urlencode({"fields": "text,permalink", "access_token": token})
    req = urllib.request.Request(f"{THREADS_GRAPH}/{media_id}?{q}",
                                 headers={"User-Agent": "shadow-gasp-promo/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        post = json.loads(r.read().decode("utf-8"))
    print(f"about to delete {media_id}  {post.get('permalink','')}")
    for line in (post.get("text") or "").split("\n"):
        print(f"  | {line}")

    # Meta returns the real reason in the BODY; urllib raises HTTPError and throws the body
    # away unless it is read off the exception. A bare "HTTP Error 400: Bad Request" says
    # nothing about whether the id is wrong, the token lacks a scope, or deletes are not
    # allowed on this object at all.
    req = urllib.request.Request(
        f"{THREADS_GRAPH}/{media_id}?" + urllib.parse.urlencode({"access_token": token}),
        method="DELETE", headers={"User-Agent": "shadow-gasp-promo/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("delete response:", r.read().decode("utf-8")[:300])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"✗ DELETE refused: {e.code}")
        print(f"  {body[:500]}")
        raise SystemExit(1)

    # Prove it is gone rather than trusting the response.
    try:
        req = urllib.request.Request(f"{THREADS_GRAPH}/{media_id}?{q}",
                                     headers={"User-Agent": "shadow-gasp-promo/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            print("✗ still readable after delete:", r.read().decode("utf-8")[:200])
            raise SystemExit(1)
    except urllib.error.HTTPError as e:
        print(f"✓ gone (reading it now returns {e.code})")


def fb_delete(which, root="."):
    """DELETE Facebook promo posts, by permalink or "all".

    ⭐ THIS IS NOT A REPAIR. The captions on these posts were already corrected in place and
    read correctly; deleting them throws away their likes, comments and shares permanently for
    no copy gain. It exists because the owner asked for the posts gone (2026-09-19), not
    because anything is wrong with them.

    ⭐ The promo MARKER is deliberately left alone. promo/<slug>.json is what stops a comic
    being promoted twice; clearing it here, as a side effect of a delete, would quietly re-arm
    the autopilot to re-post these books on its next run. That is a separate decision.
    """
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("FB_PAGE_ACCESS_TOKEN is not set")

    wanted = {s.strip() for s in which.split(",")} if which != "all" else None
    posts = markers(root)
    if wanted is not None:
        posts = [p for p in posts if p[0] in wanted]
        missing = wanted - {p[0] for p in posts}
        for m in sorted(missing):
            print(f"✗ {m}: no Facebook promo marker with a real post id")
    print(f"{len(posts)} Facebook promo post(s) to delete\n")

    gone = failed = 0
    for slug, pid in posts:
        try:
            msg = graph("GET", pid, {"fields": "message,permalink_url"}, token)
        except urllib.error.HTTPError as e:
            print(f"✗ {slug}: cannot read {pid} ({e.code}) -- not deleting something I cannot see")
            failed += 1
            continue
        print(f"→ {slug}  {pid}")
        print(f"    {msg.get('permalink_url','')}")
        for line in (msg.get("message") or "").split("\n")[:4]:
            print(f"    | {line}")
        try:
            req = urllib.request.Request(
                f"{GRAPH}/{pid}?" + urllib.parse.urlencode({"access_token": token}),
                method="DELETE")
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"    delete response: {r.read().decode('utf-8')[:120]}")
        except urllib.error.HTTPError as e:
            print(f"    ✗ refused: {e.code} {e.read().decode('utf-8','replace')[:200]}")
            failed += 1
            continue
        # Prove it, rather than trusting {"success": true}.
        try:
            graph("GET", pid, {"fields": "id"}, token)
            print("    ✗ still readable after the delete")
            failed += 1
        except urllib.error.HTTPError as e:
            print(f"    ✓ gone (reading it now returns {e.code})")
            gone += 1

    print(f"\ndeleted {gone}, failed {failed}")
    print("NOTE: promo/<slug>.json still records these as posted, so /promo and the autopilot "
          "will not offer these comics again until those markers are cleared.")
    if failed:
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the change back (default: report only)")
    ap.add_argument("--only", default="", help="limit to one permalink, for testing a single post first")
    ap.add_argument("--root", default=".")
    ap.add_argument("--threads-delete", default="",
                    help="retire one Threads post by id, after its replacement is live")
    ap.add_argument("--threads-list", action="store_true",
                    help="read-only: list the posts actually live on the Threads account")
    ap.add_argument("--fb-delete", default="",
                    help="DELETE Facebook promo posts: comma-separated permalinks, or 'all'")
    a = ap.parse_args()

    if a.threads_list:
        threads_list()
        return

    if a.threads_delete:
        threads_delete(a.threads_delete)
        return

    if a.fb_delete:
        fb_delete(a.fb_delete, a.root)
        return

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
            # ⭐ "No detail line" is not the same as "nothing to fix". A post written with a
            # custom caption, or by an older version of build_caption, can still say PDF in a
            # shape this pattern does not know. Say so loudly instead of reporting it clean --
            # a silent pass here is exactly how the thing being fixed got missed in the first
            # place. Anything flagged needs a human to look and edit it by hand.
            stray = [w for w in ("PDF", "pdf", "instant", "Instant", "download", "Download")
                     if w in (msg or "")]
            if stray:
                print(f"! {slug}: no detail line, but the post still mentions {sorted(set(stray))}"
                      f" -- NEEDS A LOOK BY HAND")
                print("    ---- live message ----")
                for line in (msg or "").split("\n"):
                    print(f"    | {line}")
                print("    ----------------------")
            else:
                print(f"· {slug}: no detail line, and no format wording anywhere -- left alone")
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

    print("\n--- Threads (read-only; no edit endpoint exists) ---")
    threads_report(a.root)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
