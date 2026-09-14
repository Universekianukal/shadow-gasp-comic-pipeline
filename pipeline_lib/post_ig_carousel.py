"""Publish one comic carousel to Instagram (the Telegram /carousel draft's "Post" button).

The slides are built ahead of time (gen_carousel.py) and committed under carousel/<dir>/1..5.jpg;
carousel/index.json lists them with the caption. Instagram fetches each slide by its raw GitHub
URL. The folder name carries a content hash: IG binds a fetch refusal (9004/2207052) to a URL for
good, so regenerated slides must live at a new path.

Posting is refused a second time (marker carousel/<slug>.posted.json) unless --force -- the same
guard as post_fb_promo.py, for the same reason: a duplicate post is what took the page's reach
to 1 in August.
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

IG_USER_ID = "17841425663819735"
GRAPH = "https://graph.facebook.com/v19.0"
RAW = "https://raw.githubusercontent.com/Universekianukal/shadow-gasp-comic-pipeline/main"
HERE = os.path.dirname(os.path.abspath(__file__))
CAR_DIR = os.path.join(os.path.dirname(HERE), "carousel")
UA = {"User-Agent": "shadow-gasp-comic-pipeline"}
# Where the workflow's report step reads the outcome from (overridable so tests can run off-runner).
RESULT = os.environ.get("CAR_RESULT_PATH", "/tmp/car_posted.json")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def entry_for(slug):
    idx = json.load(open(os.path.join(CAR_DIR, "index.json"), encoding="utf-8"))
    for e in idx:
        if e.get("slug") == slug:
            return e
    raise SystemExit(f"no carousel {slug!r} in carousel/index.json")


def slide_urls(e):
    return [f"{RAW}/carousel/{e['dir']}/{i}.jpg" for i in range(1, int(e.get("slides", 5)) + 1)]


def _post(path, params, token):
    data = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=data, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as ex:
        body = ex.read().decode()[:500]
        if "9004" in body or "2207052" in body:
            raise SystemExit("Instagram refused to fetch a slide (9004/2207052). That refusal sticks to the "
                             "URL: rebuild the slides so they get a new folder, then post again.\n" + body)
        raise SystemExit(f"Instagram {path} failed: {ex.code} {body}")


def _wait(cid, token, what):
    deadline = time.time() + 300
    while time.time() < deadline:
        q = urllib.parse.urlencode({"fields": "status_code,status", "access_token": token})
        with urllib.request.urlopen(urllib.request.Request(f"{GRAPH}/{cid}?{q}", headers=UA), timeout=60) as r:
            st = json.loads(r.read().decode())
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"Instagram rejected {what} while processing: {st.get('status')}")
        time.sleep(5)
    raise SystemExit(f"Instagram {what} never finished processing")


def post_carousel(urls, caption, token):
    """Children (is_carousel_item) -> parent CAROUSEL container -> publish."""
    kids = []
    for i, u in enumerate(urls, 1):
        c = _post(f"{IG_USER_ID}/media", {"image_url": u, "is_carousel_item": "true"}, token)
        _wait(c["id"], token, f"slide {i}")
        kids.append(c["id"])
        print(f"slide {i}/{len(urls)} ready")
    parent = _post(f"{IG_USER_ID}/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                            "caption": caption}, token)
    _wait(parent["id"], token, "the carousel")
    return _post(f"{IG_USER_ID}/media_publish", {"creation_id": parent["id"]}, token)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="check every slide URL + the token; post nothing")
    a = ap.parse_args()
    e = entry_for(a.slug)
    urls = slide_urls(e)
    caption = (os.environ.get("CAROUSEL_CAPTION", "").strip() or e.get("caption", ""))[:2200]
    marker = os.path.join(CAR_DIR, f"{a.slug}.posted.json")
    prev = json.load(open(marker, encoding="utf-8")) if os.path.exists(marker) else {}
    print(f"carousel: #{e.get('issue')} {e.get('title')}  ({len(urls)} slides, folder {e['dir']})")

    for u in urls:  # every slide must be publicly fetchable before Instagram is asked to fetch it
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA, method="HEAD"), timeout=60) as r:
            if r.status != 200:
                raise SystemExit(f"slide not reachable ({r.status}): {u}")
    print("all slides reachable")

    if prev.get("ig") and not a.force:
        print(f"ALREADY POSTED to Instagram on {prev['ig'].get('posted_at')} as {prev['ig'].get('id')} -- "
              "skipping. Use force to post again.")
        json.dump({"result": "already"}, open(RESULT, "w"))
        return
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise SystemExit("FB_PAGE_ACCESS_TOKEN is not set")
    if a.dry_run:
        q = urllib.parse.urlencode({"fields": "username", "access_token": token})
        with urllib.request.urlopen(urllib.request.Request(f"{GRAPH}/{IG_USER_ID}?{q}", headers=UA), timeout=60) as r:
            print(f"DRY RUN -- token valid for {json.loads(r.read().decode()).get('username')}. Nothing posted.")
        return

    res = post_carousel(urls, caption, token)
    post_id = res.get("id")
    print(f"posted carousel: {post_id}")
    prev["ig"] = {"id": post_id, "posted_at": datetime.datetime.utcnow().isoformat() + "Z", "dir": e["dir"]}
    json.dump(prev, open(marker, "w", encoding="utf-8"), indent=2)
    json.dump({"result": "posted", "post_id": post_id, "permalink": e.get("permalink"), "issue": e.get("issue")},
              open(RESULT, "w"))


if __name__ == "__main__":
    main()
