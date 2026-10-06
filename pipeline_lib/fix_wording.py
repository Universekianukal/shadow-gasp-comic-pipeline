"""Telegram "✏️ Fix wording" -> save a word swap for Gumroad's adult-keyword filter and re-run the
build that tripped it.

Runs from fix_wording.yml. The button in Telegram (sent by stage_and_deliver.py) opens that
workflow's Run form; the owner types the issue number, the word Gumroad objects to, and what to
write instead. This:
  1. adds the swap to gumroad_word_swaps.json and pushes it to main;
  2. looks the issue up in gumroad_wording_pending.json (written by the build) for its run id;
  3. re-runs that run. A re-run executes its ORIGINAL commit, but stage_and_deliver.py reads
     gumroad_word_swaps.json from main at run time, so the new swap applies. The script comes
     back from the KV cache and the art from the Kaggle kernel: ~10 minutes, no GPU. The re-run
     updates the existing draft in place (stage_draft's rebuild path) or creates it.
"""
import argparse
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWAPS = os.path.join(ROOT, "pipeline_lib", "gumroad_word_swaps.json")
PENDING = os.path.join(ROOT, "pipeline_lib", "gumroad_wording_pending.json")


def log(*a):
    print(*a, flush=True)


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    body = urllib.parse.urlencode({"chat_id": chat, "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body, timeout=30)
    except Exception as e:
        log(f"telegram send failed ({e})")


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, check=check, capture_output=True, text=True)


def save_swap(word, replacement):
    with open(SWAPS, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("swaps", {})[word] = replacement
    with open(SWAPS, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    git("config", "user.name", "shadow-gasp-bot")
    git("config", "user.email", "bot@shadowgasp.example")
    git("add", SWAPS)
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        log(f"swap '{word}' -> '{replacement}' was already saved")
        return
    git("commit", "-m", f"gumroad wording: '{word}' -> '{replacement or '(drop)'}'")
    for _ in range(4):   # a build may push ledgers at the same moment
        if git("push", "origin", "HEAD:main", check=False).returncode == 0:
            log(f"saved swap '{word}' -> '{replacement}' to main")
            return
        git("pull", "--rebase", "origin", "main")
    raise SystemExit("could not push the swap to main")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True)
    ap.add_argument("--word", required=True)
    ap.add_argument("--replacement", default="")
    ap.add_argument("--rerun", default="true")
    a = ap.parse_args()

    issue = re.sub(r"\D", "", a.issue).lstrip("0")
    word = re.sub(r"[^\w]+", " ", a.word).strip().lower()
    replacement = " ".join(a.replacement.split())
    if not issue or not word:
        raise SystemExit("need an issue number and the word Gumroad objects to")
    if word in replacement.lower().split():
        raise SystemExit("the replacement still contains the word -- Gumroad would refuse it again")

    save_swap(word, replacement)

    if a.rerun.lower() != "true":
        telegram(f"✅ Saved: '{word}' → '{replacement or '(dropped)'}'. Not re-running #{issue} "
                 "(rerun=false); every build from now on uses it.")
        return

    try:
        with open(PENDING, encoding="utf-8") as fh:
            rec = json.load(fh).get(issue)
    except Exception:
        rec = None
    run_id = (rec or {}).get("run_id")
    if not run_id:
        msg = (f"✅ Saved: '{word}' → '{replacement or '(dropped)'}'.\n⚠️ No recorded build for "
               f"#{issue}, so nothing was re-run. Start the build again (/make or the Comic "
               "Pipeline workflow) with the same case, pages, issue number and Kaggle account.")
        log(msg)
        telegram(msg)
        return

    r = subprocess.run(["gh", "run", "rerun", str(run_id)], capture_output=True, text=True)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    url = f"https://github.com/{repo}/actions/runs/{run_id}"
    if r.returncode != 0:
        msg = (f"✅ Saved: '{word}' → '{replacement or '(dropped)'}'.\n⚠️ Could not re-run #{issue} "
               f"({(r.stderr or r.stdout).strip()[:200]}). Re-run it from {url}")
        log(msg)
        telegram(msg)
        raise SystemExit(1)
    msg = (f"✅ Saved: '{word}' → '{replacement or '(dropped)'}'.\n🔁 Re-running #{issue} "
           f"({rec.get('case', '')[:60]}) -- ~10 min, script and art reused. The PDF and the "
           f"Gumroad draft come back here.\n{url}")
    log(msg)
    telegram(msg)


if __name__ == "__main__":
    main()
