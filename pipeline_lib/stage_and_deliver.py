"""Build the comic PDF, create a Gumroad DRAFT product (not public) with it,
send the plain PDF to Telegram, then register it with the Cloudflare Worker
(a plain HTTPS call to the Worker's own public URL, protected by a shared
secret — no separate Cloudflare API token needed). The Worker owns all
approval state in its own KV binding and sends the follow-up message with
Approve / Reject / Increase Pages buttons.
"""
import argparse
import glob
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import urllib.parse
import urllib.request

GUMROAD_BIN = "gumroad"
DEFAULT_CATEGORY = "comics-and-graphic-novels"

# Flat tier pricing keyed by target page count, shared with the Worker's
# "Increase Pages" buttons (worker/worker.js pageCountKeyboard). 25pp is the
# pipeline's own default page count and keeps the base $2.99 price.
PAGE_PRICE_TIERS = {20: "0", 25: "2.99", 35: "3.99", 50: "4.99", 75: "6.99", 100: "8.99"}


def gumroad(args_list):
    result = subprocess.run([GUMROAD_BIN, *args_list, "--json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gumroad CLI failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def pick_preview_panels(comic_dir, script, limit=3):
    """Pick interior panels to use as extra product previews / promo images.

    Deliberately drawn from the OPENING THIRD of the book only. The temptation
    is to grab the splash pages because they're the most striking, but splashes
    are the story's biggest beats — including the final page. Using those as
    free previews gives away the reveals and the ending, which is the opposite
    of what a preview is for. Early pages set atmosphere and raise the question
    without answering it.
    """
    panels_dir = os.path.join(comic_dir, "panels")
    pages = script.get("pages", [])
    early = pages[:max(1, len(pages) // 3)]

    files = []
    for page in early:
        if page.get("type") == "splash" and page.get("panel"):
            files.append(page["panel"]["file"])
        else:
            for row in page.get("rows", []):
                for cell in row:
                    files.append(cell["file"])

    chosen = [f for f in files if os.path.exists(os.path.join(panels_dir, f))]
    return [os.path.join(panels_dir, f) for f in chosen[:limit]]


def slugify(title):
    """Title -> URL slug, so the product lives at /l/norjak rather than /l/vkzul.

    Gumroad hands out a random slug unless a custom permalink is set, and a
    random one is unshareable, unmemorable and tells a buyer nothing.
    """
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:40].strip("-") or "issue"


def stage_draft(name, pdf_path, cover_path, price, description, tags, category,
                preview_paths=None, thumbnail_path=None, permalink=None):
    # Deliberate defaults, all left OFF because the API's absence of a flag IS
    # the off state: pay-what-you-want, installments, quantity selection,
    # purchase limits and shipping. None help a $2.99 single-file download.
    args = ["products", "create", "--name", name, "--price", price,
            "--file", pdf_path, "--file-name", os.path.basename(pdf_path),
            # Once a PDF is downloaded there's nothing to return, which is why
            # no-refunds is the norm for low-cost digital downloads. Fine print
            # deliberately left blank.
            "--refund-period", "none"]
    if description:
        args += ["--description", description]
    if cover_path and os.path.exists(cover_path):
        args += ["--cover-image", cover_path]
    thumb = thumbnail_path or cover_path
    if thumb and os.path.exists(thumb):
        args += ["--thumbnail", thumb]
    for p in (preview_paths or []):
        args += ["--preview-image", p]
    for t in (tags or []):
        args += ["--tag", t]
    if category:
        args += ["--category", category]
    if permalink:
        args += ["--custom-permalink", permalink]
    data = gumroad(args)
    return data.get("product", data)["id"]


def telegram_send_document(token, chat_id, file_path, caption):
    boundary = "----shadowgaspboundary"
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n"]
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n")
    filename = os.path.basename(file_path)
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; "
                 f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n")
    header = "".join(parts).encode()
    with open(file_path, "rb") as f:
        body = header + f.read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def register_with_worker(worker_url, shared_secret, token, case_name, product_id, title):
    req = urllib.request.Request(
        f"{worker_url.rstrip('/')}/register",
        data=json.dumps({
            "token": token, "case": case_name, "product_id": product_id, "title": title,
        }).encode(),
        headers={"Content-Type": "application/json", "X-Shared-Secret": shared_secret},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return r.status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--target-pages", default="25")
    ap.add_argument("--price", default=None, help="Overrides the tier price derived from --target-pages")
    args = ap.parse_args()
    if args.price is None:
        args.price = PAGE_PRICE_TIERS.get(int(args.target_pages), "2.99")

    comic_dir = args.case_dir
    scripts = glob.glob(os.path.join(comic_dir, "script_issue*.json"))
    if not scripts:
        raise SystemExit("No script_issueNN.json found")
    script_path = scripts[0]
    script = json.load(open(script_path, encoding="utf-8"))

    build_comic = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_comic.py")
    subprocess.run([sys.executable, build_comic, "--script", script_path], cwd=comic_dir, check=True)

    pdf_path = os.path.join(comic_dir, script["output"])
    cover_path = os.path.join(comic_dir, "panels", "cover.jpg")

    description = script.get("subject", "")
    tags = [t.strip() for t in script.get("keywords", "").split(",") if t.strip()][:5]

    # Purpose-built social promo graphic (hook-led, not a comic page). Built
    # here at build time because the case folder is deleted after this run --
    # it rides along as a Gumroad preview so it can be fetched again at
    # publish time and handed over for posting.
    panels = os.path.join(comic_dir, "panels")
    hook = script.get("promo_hook") or script.get("tagline", "")
    sub = "documentary comic"

    # Three different shapes for three different jobs. cover.jpg stays 9:16
    # because that's the comic's actual front cover page inside the PDF — but
    # Gumroad's product hero is wide and its storefront tile is square, so
    # reusing the portrait cover for those just gets it cropped badly.
    promo_path = os.path.join(comic_dir, "promo.jpg")
    banner_path = None
    try:
        import gen_promo_card
        promo_path = gen_promo_card.build(pdf_path, promo_path)
    except Exception as e:
        print(f"WARNING: promo card build failed ({e}) — continuing without it")
        promo_path = None

    # Square storefront tile, styled as a comic cover. A shop tile for a comic
    # IS its cover -- series banner, title, issue number. A bare atmospheric
    # image reads as a documentary still rather than something purchasable.
    thumb_path = cover_path
    try:
        import gen_store_tile
        thumb_path = gen_store_tile.build(pdf_path, os.path.join(comic_dir, "store_tile.jpg"))
    except Exception as e:
        print(f"WARNING: store tile build failed ({e}) — falling back to cover")

    # Product-page hero: the comic shown as an object, not a mood image.
    try:
        import gen_store_hero
        cover_path = gen_store_hero.build(pdf_path, os.path.join(comic_dir, "store_hero.jpg"))
    except Exception as e:
        print(f"WARNING: store hero build failed ({e}) — falling back")
        if banner_path and os.path.exists(banner_path):
            cover_path = banner_path

    previews = ([promo_path] if promo_path else []) + pick_preview_panels(comic_dir, script)
    product_id = stage_draft(
        name=f"{script['series']} #{script['issue_no']}: {script['title']}",
        pdf_path=pdf_path, cover_path=cover_path, price=args.price,
        description=description, tags=tags, category=DEFAULT_CATEGORY,
        preview_paths=previews, thumbnail_path=thumb_path,
        permalink=slugify(script["title"]),
    )
    print(f"Staged Gumroad draft: {product_id}")

    # Custom landing page, built from the same script data, using the
    # product's own just-uploaded cover URL. Only ever published if Gumroad's
    # own sanitizer reports it clean -- a broken landing page would make the
    # product unpurchasable, worse than just leaving the default page.
    try:
        import gen_landing_page
        cover_data = gumroad(["products", "view", product_id])
        cover_url = (cover_data.get("product", cover_data)).get("thumbnail_url")
        if cover_url:
            landing_path = os.path.join(comic_dir, "landing.html")
            with open(landing_path, "w", encoding="utf-8") as f:
                f.write(gen_landing_page.build_html(script, cover_url))
            ok, err = gen_landing_page.publish_if_safe(product_id, landing_path)
            print(f"Landing page: {'published' if ok else 'SKIPPED (' + str(err) + ')'}")
    except Exception as e:
        print(f"WARNING: landing page step failed ({e}) — default product page stays in place")

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    result = telegram_send_document(
        bot_token, chat_id, pdf_path,
        caption=f"{args.title} — full comic (see next message for approval buttons)",
    )
    if not result.get("ok"):
        raise SystemExit(f"Telegram send failed: {result}")
    print(f"Delivered PDF to Telegram, message_id={result['result']['message_id']}")

    approval_token = secrets.token_urlsafe(8)
    register_with_worker(
        worker_url=os.environ["WORKER_URL"],
        shared_secret=os.environ["WORKER_SHARED_SECRET"],
        token=approval_token,
        case_name=args.title,
        product_id=product_id,
        title=args.title,
    )
    print(f"Registered with Worker, token={approval_token}")


if __name__ == "__main__":
    main()
