"""Offer a Telegram "Retry" button for a comic build that Gumroad's 10-creates/day cap refused.

Owner's request (2026-09-29): retrying #118-129 by hand, some go through and some hit the cap
again -- every one that is refused must come back with its own Retry button, until the whole
back catalogue is on Gumroad.

Runs from gumroad_retry_watch.yml on EVERY Comic Pipeline completion (workflow_run fires for
re-run attempts too), always on main's code -- which is the point: a re-run executes the OLD
commit it was first built from, so a button added inside the pipeline would never appear on the
re-runs of #118-129. The button's callback (gumretry:<run_id>:<issue>) is handled by the comics
bot Worker, which re-runs that run. Its completion lands back here, so the loop closes by itself.

A run gets a button only when its LATEST attempt logged Gumroad's cap refusal AND the issue still
has no product (a later success on another path must not resurrect a button).
"""
import argparse
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

CAP = "only create 10 products per day"
UA = "shadow-gasp-gumroad-retry/1.0"


def log(*a):
    print(*a, flush=True)


def run_log(run_id):
    meta = json.loads(subprocess.run(["gh", "run", "view", str(run_id), "--json", "attempt"],
                                     check=True, capture_output=True, text=True).stdout)
    attempt = meta.get("attempt") or 1
    out = subprocess.run(["gh", "run", "view", str(run_id), "--attempt", str(attempt), "--log"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return attempt, out


def gumroad_has_issue(issue):
    tok = os.environ["GUMROAD_ACCESS_TOKEN"]
    key = None
    for _ in range(40):
        q = {"access_token": tok}
        if key:
            q["page_key"] = key
        req = urllib.request.Request("https://api.gumroad.com/v2/products?" +
                                     urllib.parse.urlencode(q), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        for p in d.get("products", []):
            if re.search(rf"#0*{int(issue)}:", p.get("name", "")):
                return True
        key = d.get("next_page_key")
        if not key:
            return False
    return False


def telegram(text, button_text, data):
    tok, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    body = urllib.parse.urlencode({
        "chat_id": chat, "text": text, "disable_web_page_preview": "true",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": button_text,
                                                          "callback_data": data}]]}),
    }).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body,
                                timeout=30) as r:
        return json.loads(r.read()).get("ok")


def check(run_id):
    attempt, text = run_log(run_id)
    if CAP not in text:
        log(f"run {run_id} attempt {attempt}: no Gumroad cap refusal -- nothing to offer")
        return
    m = re.search(r'--issue-no "?(\d+)', text)
    if not m:
        log(f"run {run_id}: cap refusal but no issue number in the log -- skipping")
        return
    issue = int(m.group(1))
    c = re.search(r"INPUT_CASE: (.+)", text)
    case = c.group(1).strip() if c else "?"
    if gumroad_has_issue(issue):
        log(f"run {run_id}: #{issue} already has a Gumroad product -- no button")
        return
    ok = telegram(
        f"⏳ SHADOW GASP #{issue} ({case[:70]}) is built, but Gumroad's 10-per-day limit refused "
        f"it (attempt {attempt}).\n\nTap Retry to re-run it -- the script and art are reused, "
        f"so it's ~10 min and no GPU. Still capped = a new Retry button comes back here.",
        f"🔁 Retry #{issue}", f"gumretry:{run_id}:{issue}")
    log(f"run {run_id}: #{issue} capped on attempt {attempt} -> Retry button sent ({ok})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_ids", nargs="+")
    for rid in ap.parse_args().run_ids:
        try:
            check(rid.strip())
        except Exception as e:           # one bad run must not hide the others' buttons
            log(f"run {rid}: check failed ({e})")


if __name__ == "__main__":
    main()
