"""Keep a finished 40-page comic ready for each of the next shorts, and put it live in time.

Runs from .github/workflows/auto_upcoming_comic.yml every few hours. One tick does at most:
  * auto-publish drafts whose review window has closed, and
  * dispatch ONE new build (never two: parallel builds race the issue number and the Kaggle slot).

Why not `pick_case --source upcoming`: its "next short" is everything above the highest day that
has published, and day 91 went out early (2026-09-12), so it would build day 92 while the channel
is on day 6x. It also only knows a comic exists through `comicAt`, which the explicit /make and
/topics builds never set. This module orders days the SAME way render_queue.yml's auto-advance
does -- the lowest day 47..117 with a committed hook clip and no YOUTUBE_UPLOADED marker -- and
decides "has a comic" from issues.json + the Gumroad catalogue.

Review window (user's choice, 2026-09-29): the draft reaches Telegram with Publish/Reject as usual.
Nothing tapped -> it is published PUBLISH_AFTER_UTC on the evening its short is next in line
(publish_queue holds uploads to ~23:40 UTC). Reject deletes the product; a product that existed
and then vanished is remembered as rejected and never rebuilt.

State lives in autopilot/upcoming_comics.json (committed by the workflow).
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(ROOT, "issues.json")
STATE = os.path.join(ROOT, "autopilot", "upcoming_comics.json")

VIDEO_REPO = "Universekianukal/shadow-gasp-pipeline"
FIRST_AUTO_DAY, LAST_DAY = 47, 117       # same bounds as render_queue.yml
BUFFER = 2                               # keep the next N shorts covered
TARGET_PAGES = "40"
PUBLISH_AFTER_UTC = 17 * 60 + 40         # 17:40 UTC = ~6h before the ~23:40 UTC upload
RETRY_AFTER_H = 5                        # a build takes ~3h; don't re-dispatch before this
MAX_ATTEMPTS = 3
MIN_SLOT_HOURS = 3.0                     # 40pp ~ 2h of T4, plus margin
SLOT_TOKEN = {"-": "KAGGLE_API_TOKEN", "B": "KAGGLE_B_API_TOKEN", "C": "KAGGLE_C_API_TOKEN"}
UA = "shadow-gasp-comic-autopilot/1.0"
# Owner, 2026-09-29: 09-29 and 09-30 belong to the back catalogue still waiting on Gumroad's
# 10-creates/day cap, so the autopilot must not spend a create (or publish anything) before
# 2026-10-01 00:00 IST. Override with the COMIC_AUTOPILOT_FROM repo variable (ISO timestamp).
ACTIVE_FROM = os.environ.get("COMIC_AUTOPILOT_FROM") or "2026-10-01T00:00:00+05:30"


def log(*a):
    print(*a, flush=True)


def now():
    return dt.datetime.now(dt.timezone.utc)


def case_slug(name):
    """Byte-for-byte the Worker's caseSlug(): the key issues.json is written under."""
    return re.sub(r"[^a-z0-9-]", "", str(name or "").lower().replace(" ", "-"))[:40]


# ---------------------------------------------------------------- video side
def video_upcoming(workdir):
    """Days in the order the channel will publish them, plus each day's case name."""
    tok = os.environ.get("GH_TOKEN", "")
    url = f"https://x-access-token:{tok}@github.com/{VIDEO_REPO}.git" if tok else \
        f"https://github.com/{VIDEO_REPO}.git"
    if not os.path.isdir(os.path.join(workdir, ".git")):
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none",
                        "--no-checkout", url, workdir], check=True)
    names = set(subprocess.run(["git", "-C", workdir, "ls-tree", "-r", "--name-only", "HEAD",
                                "_pipeline/batch/"], check=True, capture_output=True,
                               text=True).stdout.split())

    def show(path):
        return json.loads(subprocess.run(["git", "-C", workdir, "show", f"HEAD:{path}"],
                                         check=True, capture_output=True, text=True).stdout)

    days = show("_pipeline/batch/state.json").get("days", {})
    queue = show("_pipeline/batch/queue.json")
    # The owner publishes by hand in day order (60, 61, 62, 63, 65 ...), so the highest day the
    # queue has seen is where the channel really is. A lower unpublished day (55, 64) is a
    # skipped leftover: render_queue could still auto-advance onto it, so it stays in the list,
    # but it must not use up the "next N" buffer.
    frontier = max((int(k) for k in queue if str(k).isdigit()), default=0)
    out = []
    for n in range(FIRST_AUTO_DAY, LAST_DAY + 1):
        base = f"_pipeline/batch/day{n:02d}/"
        if base + "YOUTUBE_UPLOADED" in names:
            continue
        if (queue.get(str(n)) or {}).get("status") == "published":
            continue
        if base + "images/seq/01.mp4" not in names:
            continue                     # render_queue steps over a day with no hook clip
        case = (days.get(str(n)) or {}).get("case")
        if not case and base + "pick.json" in names:
            # state.json stops at day 97 (entries 98-117 lost when the two 09-09 pregen chains'
            # conflicts were merged), but every pregenerated day has its own pick.json.
            try:
                case = show(base + "pick.json").get("case")
            except Exception as e:
                log(f"  day {n}: unreadable pick.json ({e})")
        if case:
            out.append((n, case))
    return out, frontier


# ------------------------------------------------------------------- gumroad
def gumroad_products():
    tok = os.environ["GUMROAD_ACCESS_TOKEN"]
    out, key = [], None
    for _ in range(40):                  # the API pages at 10 -- always follow the cursor
        q = {"access_token": tok}
        if key:
            q["page_key"] = key
        req = urllib.request.Request("https://api.gumroad.com/v2/products?" +
                                     urllib.parse.urlencode(q), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        if not d.get("success"):
            raise RuntimeError(f"gumroad list failed: {d}")
        out += d.get("products", [])
        nxt = d.get("next_page_key")
        if not nxt or nxt == key:
            break
        key = nxt
    return out


def product_for_issue(products, issue):
    tag = f"#{int(issue)}:"
    tag2 = f"#{int(issue):02d}:"
    return next((p for p in products if tag in p.get("name", "") or tag2 in p.get("name", "")),
                None)


# -------------------------------------------------------------------- kaggle
def slot_hours_left(slot):
    tok = os.environ.get(SLOT_TOKEN[slot], "").strip()
    if not tok:
        return None
    req = urllib.request.Request("https://www.kaggle.com/api/v1/kernels/quota",
                                 headers={"Authorization": f"Bearer {tok}", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            g = json.loads(r.read()).get("gpuQuota", {})
    except Exception as e:
        log(f"  quota {slot}: unreadable ({e})")
        return None

    def s(k):
        return float((g.get(k) or {}).get("seconds", 0) or 0)
    return max(0.0, s("totalTimeAllowed") - s("timeUsed") - s("timeReserved")) / 3600


def best_slot():
    rows = {s: slot_hours_left(s) for s in SLOT_TOKEN}
    log("  kaggle hours left: " + ", ".join(f"{s}={'?' if h is None else f'{h:.1f}'}"
                                            for s, h in rows.items()))
    ok = [(h, s) for s, h in rows.items() if h is not None and h >= MIN_SLOT_HOURS]
    return max(ok)[1] if ok else None


# ------------------------------------------------------------------ plumbing
def gh(*args, capture=False):
    r = subprocess.run(["gh", *args], check=True, capture_output=capture, text=True)
    return r.stdout if capture else ""


def pipeline_busy():
    runs = json.loads(gh("run", "list", "--workflow", "pipeline.yml", "-L", "15",
                         "--json", "status,displayTitle", capture=True))
    return [r for r in runs if r["status"] in ("queued", "in_progress", "waiting", "pending")]


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=30)
    except Exception as e:
        log(f"  telegram failed: {e}")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def reserve(case):
    """issues.json entry for this case: existing number + pin, or max+1. Same as reserveCase()."""
    reg = load(REGISTRY, {"issues": {}, "kaggle": {}})
    reg.setdefault("kaggle", {})
    slug = case_slug(case)
    if slug in reg["issues"]:
        return int(reg["issues"][slug]), reg["kaggle"].get(slug), False
    nums = [v for v in reg["issues"].values() if isinstance(v, int)]
    return (max(nums) if nums else 0) + 1, None, True


def write_reservation(case, issue, slot):
    reg = load(REGISTRY, {"issues": {}, "kaggle": {}})
    reg.setdefault("kaggle", {})
    slug = case_slug(case)
    reg["issues"][slug] = issue
    reg["kaggle"][slug] = slot
    save(REGISTRY, reg)


# ---------------------------------------------------------------------- main
def tick(dry_run, workdir):
    t = now()
    state = load(STATE, {"days": {}})
    start = dt.datetime.fromisoformat(ACTIVE_FROM)
    if t < start and not dry_run:
        log(f"autopilot dormant until {ACTIVE_FROM} -- nothing built or published")
        return state
    days = state.setdefault("days", {})
    upcoming, frontier = video_upcoming(workdir)
    log(f"upcoming shorts (next 5): {[(d, c[:40]) for d, c in upcoming[:5]]}; "
        f"queue frontier = day {frontier}")
    if not upcoming:
        log("nothing upcoming -- the pregen batch is exhausted")
        return state

    products = gumroad_products()
    reg = load(REGISTRY, {"issues": {}})["issues"]
    window_open = t.hour * 60 + t.minute >= PUBLISH_AFTER_UTC
    up_days = {d for d, _ in upcoming}

    # Build targets: the next BUFFER days past the frontier, plus the auto-advance pick itself
    # when that is a leftover below it. "Next in line" (publishable tonight) = the auto-advance
    # pick and the first day past the frontier -- whichever the owner or render_queue sends.
    ahead = [u for u in upcoming if u[0] > frontier]
    targets = ([upcoming[0]] if upcoming[0][0] <= frontier else []) + ahead[:BUFFER]
    next_in_line = {upcoming[0][0]} | ({ahead[0][0]} if ahead else set())

    # 1. auto-publish: the next short's comic once the window opens, and any autopilot draft
    #    whose short has already gone out (its window is long gone).
    candidates = list(targets)
    candidates += [(int(k), v["case"]) for k, v in days.items() if int(k) not in up_days]
    for day, case in candidates:
        issue = reg.get(case_slug(case))
        p = product_for_issue(products, issue) if issue else None
        rec = days.get(str(day))
        if p and rec is not None:
            rec["product_id"] = p["id"]
            rec["published"] = bool(p.get("published"))
        if not p or p.get("published"):
            continue
        due = (day in next_in_line and window_open) or day not in up_days
        if not due:
            log(f"day {day} #{issue}: draft in review; auto-publishes after 17:40 UTC on its eve")
            continue
        log(f"day {day} #{issue}: review window closed -> auto-publish {p['id']}")
        if not dry_run:
            gh("workflow", "run", "action.yml", "-f", "action=publish", "-f", f"case={case}",
               "-f", f"product_id={p['id']}",
               "-f", f"chat_id={os.environ.get('TELEGRAM_CHAT_ID', '')}")
            telegram(f"⏰ Auto-publishing SHADOW GASP #{issue} ({case[:60]}) -- no Publish/Reject "
                     f"before its short (day {day}). Its funnel link goes on at upload.")
            if rec is not None:
                rec["auto_published_at"] = t.isoformat()

    # 2. build: first of the next BUFFER shorts with no comic at all.
    busy = pipeline_busy()
    for day, case in targets:
        slug = case_slug(case)
        issue = reg.get(slug)
        p = product_for_issue(products, issue) if issue else None
        rec = days.get(str(day))
        if p:
            log(f"day {day}: covered by #{issue} ({'published' if p.get('published') else 'draft'})")
            continue
        if rec and rec.get("product_id"):
            if not rec.get("rejected"):
                rec["rejected"] = t.isoformat()
                telegram(f"🚫 #{rec.get('issue')} for day {day} was rejected/deleted -- the "
                         f"autopilot will NOT rebuild it. /make it by hand if you want another go.")
            log(f"day {day}: product {rec['product_id']} vanished -> treated as rejected")
            continue
        if rec and rec.get("gave_up"):
            log(f"day {day}: gave up after {rec.get('attempts')} attempts")
            continue
        if busy:
            log(f"day {day}: needs a comic, but a Comic Pipeline run is active "
                f"({busy[0]['displayTitle']}) -- one build at a time")
            return state
        if rec and rec.get("dispatched_at"):
            age = (t - dt.datetime.fromisoformat(rec["dispatched_at"])).total_seconds() / 3600
            if age < RETRY_AFTER_H:
                log(f"day {day}: dispatched {age:.1f}h ago -- waiting")
                return state
            if rec.get("attempts", 0) >= MAX_ATTEMPTS:
                rec["gave_up"] = t.isoformat()
                telegram(f"❗ Autopilot gave up on day {day} ({case[:60]}) after "
                         f"{MAX_ATTEMPTS} builds with no Gumroad product. Check the runs.")
                continue

        issue_no, pinned, new = reserve(case)
        slot = pinned or best_slot()
        if not slot:
            log(f"day {day}: no Kaggle account has {MIN_SLOT_HOURS}h left -- waiting")
            if not (rec or {}).get("quota_warned"):
                telegram(f"⚠ Autopilot can't build day {day}'s comic: no Kaggle account has "
                         f"{MIN_SLOT_HOURS:.0f}h of GPU left. It will retry every few hours.")
                days.setdefault(str(day), {"case": case})["quota_warned"] = t.isoformat()
            return state
        log(f"day {day}: BUILD #{issue_no} '{case}' {TARGET_PAGES}pp on slot {slot}"
            f"{' (new issue)' if new else ' (existing issue, rebuild)'}")
        if dry_run:
            return state
        write_reservation(case, issue_no, slot)
        commit_and_push(f"autopilot: reserve #{issue_no} for {case_slug(case)} (kaggle {slot})")
        gh("workflow", "run", "pipeline.yml", "-f", f"case={case}", "-f",
           f"target_pages={TARGET_PAGES}", "-f", f"issue_no={issue_no}",
           "-f", f"kaggle_account={'' if slot == '-' else slot}")
        rec = days.setdefault(str(day), {})
        rec.update(case=case, issue=issue_no, slot=slot, dispatched_at=t.isoformat(),
                   attempts=rec.get("attempts", 0) + 1)
        rec.pop("quota_warned", None)
        telegram(f"🤖 Auto-building SHADOW GASP #{issue_no} for the day-{day} short "
                 f"({case[:60]}), {TARGET_PAGES}pp on Kaggle {slot}. Draft comes here for "
                 f"review; untouched, it goes live ~6h before the short.")
        return state
    log("next shorts are all covered -- nothing to build")
    return state


def commit_and_push(msg):
    for attempt in range(3):
        paths = [p for p in ("issues.json", "autopilot") if os.path.exists(os.path.join(ROOT, p))]
        subprocess.run(["git", "add", "-A", *paths], check=True, cwd=ROOT)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
            return
        subprocess.run(["git", "commit", "-q", "-m", msg], check=True, cwd=ROOT)
        subprocess.run(["git", "pull", "-q", "--rebase", "--autostash", "origin", "main"], cwd=ROOT)
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT).returncode == 0:
            return
    raise RuntimeError("could not push autopilot state")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--video-dir", default="/tmp/video-repo")
    a = ap.parse_args()
    before = json.dumps(load(STATE, {"days": {}}), sort_keys=True)
    state = tick(a.dry_run, a.video_dir)
    # Only commit when something happened -- a quiet tick every 2h must not spam the history.
    if not a.dry_run and json.dumps(state, sort_keys=True) != before:
        save(STATE, state)
        commit_and_push("autopilot: upcoming comics state")


if __name__ == "__main__":
    sys.exit(main())
