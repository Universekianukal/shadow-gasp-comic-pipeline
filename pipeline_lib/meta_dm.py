"""Send ONE step of the comment -> free issue #1 funnel, on Instagram or (job["platform"] == "fb") Facebook.

Dispatched by the comics bot (meta_dm.yml) with an opaque job token only -- this repo is public and
workflow inputs are visible, so the commenter's details are fetched from the Worker's /meta/job and
NEVER printed. Steps (job["action"]):
  ask      private reply to the comment, once per comment. Instagram: text only (Meta allows nothing
           else there). Facebook: carries the Yes / No buttons straight away.
  offer    Instagram only -- after they reply: Yes / No quick-reply buttons
  yes      reserve a slot under the shared free-code cap, mint a single-use 100%-off Gumroad code
           (the same method as gen_code.yml) and DM the link + the subscribe page
  no       a warm "come back any time" message + the subscribe page
  already  they have their copy already
The outcome always goes back to the Worker's /meta/done, which tells the owner in Telegram.
"""
import argparse
import json
import os
import secrets
import subprocess
import sys

import requests

GRAPH = "https://graph.facebook.com/v19.0"
SUBSCRIBE = "https://shadowgasp.gumroad.com/subscribe"
# Cloudflare refuses python-requests' default User-Agent at the edge (1010).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
YES_PAYLOAD, NO_PAYLOAD = "FREE_YES", "FREE_NO"


def ask_text(username):
    hi = f"Hey @{username}!" if username else "Hey!"
    return (f"{hi} 🎁 We'd love to gift you Issue #1: NORJAK, the D.B. Cooper mystery in comic form. "
            "It's our way of saying hello, a free copy of our very first comic. "
            "If you enjoy it, an honest review would mean a lot, but there's no pressure. Reply YES 👇")


OFFER_TEXT = "Would you like to read Issue #1 free and share your honest review? 👇"
QUICK = [
    {"content_type": "text", "title": "📖 Yes, send it", "payload": YES_PAYLOAD},
    {"content_type": "text", "title": "Not right now", "payload": NO_PAYLOAD},
]


def fb_ask_text(name):
    """Facebook's private reply may carry the buttons, so it asks the question directly."""
    hi = f"Hey {name}!" if name else "Hey!"
    return (f"{hi} 🎁 We'd love to gift you Issue #1: NORJAK, the D.B. Cooper mystery in comic form. "
            "It's our way of saying hello, a free copy of our very first comic. "
            "If you enjoy it, an honest review would mean a lot, but there's no pressure. Want it?")


def yes_text(link):
    return (f"Here you go! 🎁\n{link}\n"
            "This link is just for you. Enjoy the story 🖤\n"
            f"Want to hear about new issues? → {SUBSCRIBE}")


NO_TEXT = ("No problem 🕯️ The file stays open.\n"
           f"New cases drop every week → {SUBSCRIBE}\n"
           "Comment COMIC any time and it's yours.")
ALREADY_TEXT = ("You've already got your free copy of Issue #1 🖤 Enjoy! If you liked it, an honest review means the world.\n"
                f"New cases → {SUBSCRIBE}")
SOLD_OUT_TEXT = ("Ah, all our free copies of Issue #1 have been claimed 😔 Thank you so much for the interest!\n"
                 f"Follow us for the next giveaway and new cases → {SUBSCRIBE}")


def env(k):
    return os.environ.get(k, "").strip()


def worker(path, body):
    return requests.post(env("WORKER_URL").rstrip("/") + path, json=body,
                         headers={"X-Shared-Secret": env("WORKER_SHARED_SECRET"), "User-Agent": UA}, timeout=30)


def fetch_job(token):
    r = worker("/meta/job", {"job": token})
    if r.status_code != 200:
        raise RuntimeError(f"job not found ({r.status_code})")
    return r.json()


class MetaError(RuntimeError):
    """A refusal from Meta, carrying its error code (e.g. 10903 = can't private-reply to this person)."""

    def __init__(self, text, code=None):
        super().__init__(text)
        self.code = code


def send(payload):
    """Send one message; returns Meta's JSON reply (a private reply returns the recipient's scoped id)."""
    r = requests.post(f"{GRAPH}/{env('FB_PAGE_ID')}/messages", params={"access_token": env("FB_PAGE_ACCESS_TOKEN")},
                      json=payload, timeout=30)
    if not r.ok:
        code = None
        try:
            err = r.json().get("error", {})
            msg, code = err.get("message", ""), err.get("code")
        except ValueError:
            msg = r.text[:200]
        raise MetaError(f"Meta refused the message ({r.status_code}): {msg}", code)
    try:
        return r.json()
    except ValueError:
        return {}


def to_user(sid, text, quick=None):
    msg = {"text": text}
    if quick:
        msg["quick_replies"] = quick
    return {"recipient": {"id": sid}, "messaging_type": "RESPONSE", "message": msg}


def gumroad(*args):
    r = subprocess.run([os.path.expanduser("~/.local/bin/gumroad"), *args, "--json"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout or "{}")
    except ValueError:
        return {"success": False, "error": (r.stderr or r.stdout)[:200]}


def mint_link(product_id):
    """Single-use 100%-off code, exactly as gen_code.yml makes them. Never printed."""
    code = "SG" + secrets.token_hex(4).upper()
    made = gumroad("offer-codes", "create", "--product", product_id, "--name", code,
                   "--percent-off", "100", "--max-purchase-count", "1")
    if not made.get("success"):
        raise RuntimeError("Gumroad would not create the code")
    url = (gumroad("products", "view", product_id).get("product") or {}).get("short_url")
    if not url:
        raise RuntimeError("could not read the product link")
    return f"{url.rstrip('/')}/{code}"


def run(job):
    a = job.get("action")
    result = {"ok": True}
    if a == "ask" and job.get("platform") == "fb":
        # Facebook: the one private reply already carries Yes / No (Instagram's may not).
        resp = send({"recipient": {"comment_id": job["comment_id"]},
                     "message": {"text": fb_ask_text(job.get("name", "")), "quick_replies": QUICK}})
        result["recipient_id"] = str(resp.get("recipient_id", ""))
    elif a == "ask":
        resp = send({"recipient": {"comment_id": job["comment_id"]}, "message": {"text": ask_text(job.get("username", ""))}})
        # The commenter's scoped id -- the id their reply will arrive with. Reported to the bot (never
        # printed), which records "asked" under it so the reply gets the Yes / No buttons.
        result["recipient_id"] = str(resp.get("recipient_id", ""))
    elif a == "offer":
        send(to_user(job["recipient"], OFFER_TEXT, QUICK))
    elif a == "yes":
        r = worker("/free-codes/reserve", {"slug": job["slug"], "cap": int(job["cap"])})
        if r.status_code == 409:
            send(to_user(job["recipient"], SOLD_OUT_TEXT))
            result.update(sold_out=True, cap=job["cap"])
        elif r.status_code != 200:
            raise RuntimeError(f"could not reserve a free copy ({r.status_code})")
        else:
            count = r.json().get("count")
            send(to_user(job["recipient"], yes_text(mint_link(job["product_id"]))))
            result.update(count=count, cap=job["cap"])
    elif a == "no":
        send(to_user(job["recipient"], NO_TEXT))
    elif a == "already":
        send(to_user(job["recipient"], ALREADY_TEXT))
    else:
        raise RuntimeError(f"unknown action {a!r}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--action-only", action="store_true", help="print action=<step> for GITHUB_OUTPUT and exit")
    a = ap.parse_args()
    try:
        job = fetch_job(a.job)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    if a.action_only:
        print(f"action={job.get('action', '')}")
        return
    try:
        result = run(job)
        print(f"step '{job.get('action')}' sent")
    except Exception as e:
        result = {"ok": False, "error": str(e)[:300]}
        if isinstance(e, MetaError) and e.code is not None:
            result["err_code"] = e.code
        print(f"FAILED step '{job.get('action')}': {e}", file=sys.stderr)
    try:
        worker("/meta/done", {"job": a.job, **result})
    except Exception as e:
        print(f"could not report to the bot: {e}", file=sys.stderr)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
