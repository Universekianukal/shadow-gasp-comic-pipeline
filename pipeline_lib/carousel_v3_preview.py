"""Build v3 (panel-story) carousels for some issues on the runner and send them to Telegram as
PREVIEW albums -- no Post buttons, nothing is committed or published.

    python pipeline_lib/carousel_v3_preview.py --issues 1,51
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

import add_epubs  # noqa: E402  (dash-safe gumroad calls + the buyer's PDF)
import carousel_panels  # noqa: E402


def entry_for(issue):
    d = os.path.join(REPO, "carousel", "entries")
    name = next(f for f in os.listdir(d) if f.startswith(f"{issue:03d}-"))
    return json.load(open(os.path.join(d, name), encoding="utf-8"))


def hook_of(entry):
    first = entry["caption"].split("\n")[0]
    return re.sub(r"\s*\U0001F56F\ufe0f?\s*$", "", first).strip()


def send_album(paths, caption):
    api = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
    media, form = [], []
    for i, p in enumerate(paths):
        m = {"type": "photo", "media": f"attach://s{i}"}
        if i == 0:
            m["caption"] = caption[:1000]
        media.append(m)
        form += ["-F", f"s{i}=@{p}"]
    r = subprocess.run(["curl", "-sS", "-X", "POST", f"{api}/sendMediaGroup", "-F",
                        f"chat_id={os.environ['TELEGRAM_CHAT_ID']}", "-F", "media=" + json.dumps(media)] + form,
                       capture_output=True, text=True)
    if '"ok":true' not in r.stdout:
        raise RuntimeError(r.stdout[:300])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", required=True)
    a = ap.parse_args()
    products = {add_epubs.issue_no(p["name"]): p for p in
                add_epubs.gumroad(["products", "list", "--all"]).get("products", []) if p.get("published")}
    for n in [int(x) for x in a.issues.replace(" ", "").split(",") if x]:
        entry = entry_for(n)
        with tempfile.TemporaryDirectory() as tmp:
            url, fname, _ = add_epubs.buyer_pdf(products[n]["id"])
            pdf = os.path.join(tmp, "comic.pdf")
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                        timeout=600) as r, open(pdf, "wb") as f:
                f.write(r.read())
            paths, picks = carousel_panels.build_slides(pdf, n, entry["title"], hook_of(entry),
                                                        os.path.join(tmp, "out"))
            print(json.dumps(picks), flush=True)
            send_album(paths, f"PREVIEW — #{n} {entry['title']} (v3, story chosen from the narration)\n"
                              f"{picks['how']}")
            print(f"#{n}: sent {len(paths)} slides", flush=True)


if __name__ == "__main__":
    main()
