"""Build the comic PDF, create a Gumroad DRAFT product (not public) with it,
then deliver to Telegram with Approve / Reject / Increase Pages buttons whose
callback_data encodes the Gumroad product_id directly — so the Cloudflare
Worker handling button taps never needs the PDF file itself, just the
Gumroad API to publish/delete that product_id.
"""
import argparse
import glob
import json
import mimetypes
import os
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


def stage_draft(name, pdf_path, cover_path, price, description, tags, category):
    args = ["products", "create", "--name", name, "--price", price,
            "--file", pdf_path, "--file-name", os.path.basename(pdf_path)]
    if description:
        args += ["--description", description]
    if cover_path and os.path.exists(cover_path):
        args += ["--cover-image", cover_path, "--thumbnail", cover_path]
    for t in (tags or []):
        args += ["--tag", t]
    if category:
        args += ["--category", category]
    data = gumroad(args)
    return data.get("product", data)["id"]


def telegram_send_document(token, chat_id, file_path, caption, reply_markup):
    boundary = "----shadowgaspboundary"
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n"]
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n")
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"reply_markup\"\r\n\r\n"
                 f"{json.dumps(reply_markup)}\r\n")
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


def approval_keyboard(case_id, product_id):
    return {"inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": f"approve:{case_id}:{product_id}"},
        {"text": "❌ Reject", "callback_data": f"reject:{case_id}:{product_id}"},
        {"text": "\U0001F4C4 Increase Pages", "callback_data": f"pages_menu:{case_id}:{product_id}"},
    ]]}


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
    )
    print(f"Staged Gumroad draft: {product_id}")

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    result = telegram_send_document(
        token, chat_id, pdf_path,
        caption=f"{args.title} — draft ready for review (Gumroad draft: {product_id})",
        reply_markup=approval_keyboard(args.case_id, product_id),
    )
    if not result.get("ok"):
        raise SystemExit(f"Telegram send failed: {result}")
    print(f"Delivered to Telegram, message_id={result['result']['message_id']}")


if __name__ == "__main__":
    main()
