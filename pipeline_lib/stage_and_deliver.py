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
import secrets
import subprocess
import sys
import urllib.parse
import urllib.request

GUMROAD_BIN = "gumroad"
DEFAULT_CATEGORY = "comics-and-graphic-novels"


def gumroad(args_list):
    result = subprocess.run([GUMROAD_BIN, *args_list, "--json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gumroad CLI failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def pick_preview_panels(comic_dir, script, limit=3):
    """Pick a few striking interior panels to use as extra product previews.

    Splash panels are the full-page dramatic beats, so they're the best
    stand-alone images — and unlike the cover they carry no title/logo text,
    which makes them far more usable as social promo images later.
    """
    panels_dir = os.path.join(comic_dir, "panels")
    splashes, others = [], []
    for page in script.get("pages", []):
        if page.get("type") == "splash" and page.get("panel"):
            splashes.append(page["panel"]["file"])
        else:
            for row in page.get("rows", []):
                for cell in row:
                    others.append(cell["file"])
    chosen = [f for f in (splashes + others) if os.path.exists(os.path.join(panels_dir, f))]
    return [os.path.join(panels_dir, f) for f in chosen[:limit]]


def stage_draft(name, pdf_path, cover_path, price, description, tags, category,
                preview_paths=None):
    args = ["products", "create", "--name", name, "--price", price,
            "--file", pdf_path, "--file-name", os.path.basename(pdf_path)]
    if description:
        args += ["--description", description]
    if cover_path and os.path.exists(cover_path):
        args += ["--cover-image", cover_path, "--thumbnail", cover_path]
    for p in (preview_paths or []):
        args += ["--preview-image", p]
    for t in (tags or []):
        args += ["--tag", t]
    if category:
        args += ["--category", category]
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
    ap.add_argument("--price", default="2.99")
    args = ap.parse_args()

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

    product_id = stage_draft(
        name=f"{script['series']} #{script['issue_no']}: {script['title']}",
        pdf_path=pdf_path, cover_path=cover_path, price=args.price,
        description=description, tags=tags, category=DEFAULT_CATEGORY,
        preview_paths=pick_preview_panels(comic_dir, script),
    )
    print(f"Staged Gumroad draft: {product_id}")

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
