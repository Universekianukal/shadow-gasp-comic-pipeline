"""Rebuild published comics' carousels in the v3 panel-story style (carousel_v3_rollout.yml).

    python pipeline_lib/carousel_v3_rollout.py --issues all

One comic at a time: the Fireworks story model can think silently for minutes, so the run commits
and pushes every COMMIT_EVERY comics -- a stalled or cancelled job never loses finished carousels.
The hook is the one each comic's current entry already carries (hook overrides included). Posted
markers are untouched; old slide folders just stop being referenced. Comics whose story fell back
to the art picker are listed at the end so they can be redone with issues=<list>.
"""
import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.request

import add_epubs
import carousel_panels
from carousel_v3_preview import entry_for, hook_of

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMIT_EVERY = 5


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True)


def push(msg):
    git("add", "-A", "carousel/")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return
    git("commit", "-q", "-m", msg)
    for attempt in range(5):
        if git("pull", "--rebase", "-q", "origin", "main").returncode == 0 and \
                git("push", "-q", "origin", "HEAD:main").returncode == 0:
            print(f"pushed: {msg}", flush=True)
            return
        git("rebase", "--abort")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("could not push carousels")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", default="all")
    a = ap.parse_args()
    products = {add_epubs.issue_no(p["name"]): p for p in
                add_epubs.gumroad(["products", "list", "--all"]).get("products", []) if p.get("published")}
    issues = sorted(products) if a.issues == "all" else [int(x) for x in a.issues.replace(" ", "").split(",") if x]
    done, fallback, failed = [], [], []
    for k, n in enumerate(issues, 1):
        t0 = time.time()
        try:
            old = entry_for(n)
            with tempfile.TemporaryDirectory() as tmp:
                url, _, _ = add_epubs.buyer_pdf(products[n]["id"])
                pdf = os.path.join(tmp, "comic.pdf")
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                            timeout=600) as r, open(pdf, "wb") as f:
                    f.write(r.read())
                entry = carousel_panels.build(pdf, n, old["title"], hook_of(old), old["permalink"], repo=REPO)
            how = entry["picks"]["how"]
            (fallback if how.startswith("art picker") else done).append(n)
            print(f"#{n}: {entry['slides']} slides -> {entry['dir']} ({time.time() - t0:.0f}s) {how[:90]}", flush=True)
        except Exception as e:  # noqa: BLE001 - one comic must not stop the rest
            print(f"::error::#{n}: {e}", flush=True)
            failed.append(n)
        if k % COMMIT_EVERY == 0:
            push(f"carousel v3: rebuilt up to #{n}")
    push("carousel v3: rebuilt the rest")
    print(f"\nstory model: {len(done)}  art-picker fallback: {fallback}  failed: {failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
