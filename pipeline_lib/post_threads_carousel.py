"""Publish one comic carousel to Threads (the Telegram /carousel draft's "Post to Threads" button).

Same slides and listing as Instagram (post_ig_carousel.py -- reused, not changed), but Threads has its
own API, token and rules:
  * graph.threads.net: children (is_carousel_item) -> CAROUSEL container -> threads_publish.
  * Threads has NO DMs, so the caption's "check your DMs" line becomes a public-reply call to action
    (the comics bot answers COMIC comments with a public reply: the issue link + the free #1).
  * Threads makes only ONE hashtag a clickable topic, but the owner wants every hashtag visible in
    the text, as on the hand-made #1 post (2026-09-17) -- so the hashtag line is kept whole.
  * Text limit 500 characters.

The posted marker is the same per-platform file carousel/<slug>.posted.json, under key "th".
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post_ig_carousel import CAR_DIR, RESULT, UA, entry_for, slide_urls  # noqa: E402

GRAPH = "https://graph.threads.net/v1.0"
LIMIT = 500
CTA_FREE = "Curious how it ends? Comment COMIC and we'll reply with your copy."
CTA_ISSUE = "Curious how it ends? Comment COMIC and we'll reply with the link, plus your first case (#1) on us."

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def threads_caption(e):
    """The IG caption, with the DM call to action swapped for the public-reply one and a single tag."""
    cta = CTA_FREE if int(e.get("issue") or 0) == 1 else CTA_ISSUE
    out, placed = [], False
    for ln in (e.get("caption") or "").split("\n"):
        s = ln.strip()
        if "dm" in s.lower().split() or "dms" in s.lower() or "comment comic" in s.lower():
            if not placed:
                out.append(cta)
                placed = True
            continue
        out.append(ln)
    if not placed:  # no call-to-action line found: put it before the tag (or at the end)
        at = next((i for i in range(len(out) - 1, -1, -1) if out[i].strip().startswith("#")), len(out))
        out[at:at] = [cta, ""]
    text = "\n".join(out).strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    if len(text) > LIMIT:  # drop the tag first, then shorten the hook line
        text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("#")).strip()
    if len(text) > LIMIT:
        first, rest = text.split("\n", 1)
        first = first[: max(20, len(first) - (len(text) - LIMIT) - 1)].rstrip() + "…"
        text = first + "\n" + rest
    return text


def _call(method, path, params, token):
    q = urllib.parse.urlencode({**params, "access_token": token})
    if method == "GET":
        req = urllib.request.Request(f"{GRAPH}/{path}?{q}", headers=UA)
    else:
        req = urllib.request.Request(f"{GRAPH}/{path}", data=q.encode(), headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as ex:
        raise SystemExit(f"Threads {path.split('/')[-1]} failed: {ex.code} {ex.read().decode()[:500]}")


def _wait(cid, token, what):
    deadline = time.time() + 300
    while time.time() < deadline:
        st = _call("GET", cid, {"fields": "status,error_message"}, token)
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Threads rejected {what}: {st.get('status')} {st.get('error_message', '')}")
        time.sleep(4)
    raise SystemExit(f"Threads {what} never finished processing")


def post_threads(urls, caption, token, user):
    kids = []
    for i, u in enumerate(urls, 1):
        c = _call("POST", f"{user}/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true"}, token)
        _wait(c["id"], token, f"slide {i}")
        kids.append(c["id"])
        print(f"slide {i}/{len(urls)} ready")
    parent = _call("POST", f"{user}/threads", {"media_type": "CAROUSEL", "children": ",".join(kids), "text": caption}, token)
    _wait(parent["id"], token, "the carousel")
    post_id = _call("POST", f"{user}/threads_publish", {"creation_id": parent["id"]}, token).get("id")
    link = _call("GET", post_id, {"fields": "permalink"}, token).get("permalink", "")
    return post_id, link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="check every slide URL + the token; post nothing")
    ap.add_argument("--print-caption", action="store_true", help="print the Threads caption and stop (no token needed)")
    a = ap.parse_args()
    e = entry_for(a.slug)
    urls = slide_urls(e)
    caption = threads_caption(e)
    if a.print_caption:
        print(caption)
        print(f"-- {len(caption)} chars")
        return
    if not 2 <= len(urls) <= 20:
        raise SystemExit(f"a Threads carousel needs 2-20 slides, this one has {len(urls)}")
    marker = os.path.join(CAR_DIR, f"{a.slug}.posted.json")
    prev = json.load(open(marker, encoding="utf-8")) if os.path.exists(marker) else {}
    print(f"carousel: #{e.get('issue')} {e.get('title')}  ({len(urls)} slides, folder {e['dir']}) -> Threads")
    print(f"caption ({len(caption)} chars):\n{caption}\n")

    for u in urls:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA, method="HEAD"), timeout=60) as r:
            if r.status != 200:
                raise SystemExit(f"slide not reachable ({r.status}): {u}")
    print("all slides reachable")

    if prev.get("th") and not a.force:
        print(f"ALREADY POSTED to Threads on {prev['th'].get('posted_at')} as {prev['th'].get('id')} -- "
              "skipping. Use force to post again.")
        json.dump({"result": "already", "platform": "th"}, open(RESULT, "w"))
        return
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    user = os.environ.get("THREADS_USER_ID", "")
    if not token or not user:
        raise SystemExit("THREADS_ACCESS_TOKEN / THREADS_USER_ID are not set")
    if a.dry_run:
        who = _call("GET", "me", {"fields": "username"}, token)
        print(f"DRY RUN -- token valid for @{who.get('username')} (Threads). Nothing posted.")
        return

    post_id, link = post_threads(urls, caption, token, user)
    print(f"posted carousel to Threads: {post_id} {link}")
    prev["th"] = {"id": post_id, "posted_at": datetime.datetime.utcnow().isoformat() + "Z", "dir": e["dir"], "permalink": link}
    json.dump(prev, open(marker, "w", encoding="utf-8"), indent=2)
    json.dump({"result": "posted", "platform": "th", "post_id": post_id, "permalink": e.get("permalink"),
               "issue": e.get("issue")}, open(RESULT, "w"))


if __name__ == "__main__":
    main()
