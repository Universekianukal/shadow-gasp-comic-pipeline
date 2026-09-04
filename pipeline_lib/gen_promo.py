"""After a comic goes live on Gumroad, generate a ready-to-paste Facebook
promo post and send it to Telegram as its own message (so it can be copied
cleanly without the surrounding status chatter).

Sent as a separate plain message on purpose: Telegram captions and edited
status lines are awkward to copy-paste in full on mobile.
"""
import argparse
import json
import os
import urllib.request

import llm as _llm


def call_llm(system, user, max_tokens=1200):
    """Write the promo post on whichever provider can actually be billed.

    ⚠️ This used to be a bare urllib POST to api.anthropic.com with the key read at
    MODULE level, which made it the last unswitchable LLM call in the repo. When the
    Anthropic balance ran out on 2026-09-02 the script step had already been moved to
    Fireworks and kept working, so "the pipeline runs on Fireworks" looked true -- while
    every publish silently died here on HTTP 400 "credit balance is too low". Partially
    migrating a pipeline hides the outage rather than fixing it.

    Default is `auto`, which prefers Anthropic and drops to Fireworks only when Anthropic
    refuses for billing (see llm.BillingError). So topping the balance back up restores
    Anthropic with no config change, which is the whole point.
    """
    client = _llm.LLM(
        provider=(os.environ.get("COMIC_LLM_PROVIDER") or "auto").strip().lower(),
        model=(os.environ.get("COMIC_LLM_MODEL") or "").strip() or None,
        # One paid attempt per prompt; llm.py still retries free transport faults on top.
        max_retries=1,
    )
    return client.text(user, system=system, max_tokens=max_tokens).strip()


def get_product_image_urls(product_id):
    """All image URLs off the published Gumroad product: the branded cover
    plus the interior panels uploaded as extra previews at build time.

    The local cases/ folder is deleted after the build run, so by publish time
    Gumroad is the only place these images still live.
    """
    import subprocess
    r = subprocess.run(
        [os.path.expanduser("~/.local/bin/gumroad"), "products", "view", product_id, "--json"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return []
    data = json.loads(r.stdout)
    p = data.get("product", data)
    urls = []
    for c in (p.get("covers") or []):
        u = c.get("original_url") or c.get("url")
        if u:
            urls.append(u)
    if not urls:
        u = p.get("preview_url") or p.get("thumbnail_url")
        if u:
            urls.append(u)
    return urls


def tg_send_photo(bot_token, chat_id, photo_url, caption):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
        data=json.dumps({
            "chat_id": chat_id, "photo": photo_url, "caption": caption,
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def tg_send(bot_token, chat_id, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=json.dumps({
            "chat_id": chat_id, "text": text, "disable_web_page_preview": False,
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--product-id")
    args = ap.parse_args()

    system = (
        "You write Facebook posts for SHADOW GASP, an independent true-crime "
        "documentary comic series.\n\n"
        "These go into large GENERAL-INTEREST groups — most readers have never "
        "heard of the case and don't care about comics. The post's ONLY job is "
        "to make someone want to read the comic, so it must NOT tell the case "
        "itself in enough detail to satisfy that curiosity for free.\n\n"
        "This is a curiosity gap, not a summary:\n"
        "- Open with ONLY the premise: who, roughly when, what kind of crime, "
        "in 1-2 sentences. This is a hook, not a plot recap.\n"
        "- Do NOT include suspects, evidence, the investigation's findings, "
        "how it was resolved, or how it ended — those are exactly what the "
        "comic is for. Giving them away in the post removes the reason to buy.\n"
        "- End the hook with an explicit open question the reader wants "
        "answered (e.g. 'Nobody knows who he really was.' / 'The case was "
        "never solved.' / 'What happened to her is still debated.').\n"
        "- Then ONE line pushing to the comic as the only place with the full "
        "story — e.g. 'The whole case, drawn out panel by panel, is in the "
        "comic — link in the comments.'\n"
        "- Never sensationalise or disrespect real victims. No invented facts.\n"
        "- 4-6 hashtags at the end.\n"
        "- Under 80 words total — shorter than before, since it's a hook, not "
        "a story.\n\n"
        "Output ONLY the post text, ready to paste — no preamble, no options, "
        "no surrounding quotes."
    )
    user = (
        f"Case: {args.case}\n\n"
        f"Write the Facebook group post now. Under 80 words."
    )

    post = call_llm(system, user)

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    tg_send(bot_token, chat_id, f"🔗 Shareable link:\n{args.url}")
    tg_send(bot_token, chat_id, f"📋 Facebook post (copy-paste):\n\n{post}")

    # Images to attach to the FB post. The first is the branded cover; the
    # rest are interior panels (no title/logo text on them), which tend to
    # read as content rather than an ad in a feed. Sent as options rather
    # than one pick, since which performs best is worth testing per case.
    # The purpose-built promo graphic is uploaded first at build time, so it's
    # the first cover here. That's the one to actually post — the rest are the
    # product's own cover/interior art, useful on the Gumroad page but not
    # what you want to lead with in a general-interest group.
    urls = get_product_image_urls(args.product_id) if args.product_id else []
    if urls:
        try:
            tg_send_photo(bot_token, chat_id, urls[0],
                          "🖼 PROMO GRAPHIC — this is the one to post")
        except Exception as e:
            tg_send(bot_token, chat_id, f"(Promo graphic couldn't be sent: {e})")
    # Two product settings have no API/CLI flag and can only be toggled in the
    # Gumroad web UI. The VAT one matters: it changes the tax rate charged to
    # EU buyers on an e-publication, so it isn't just cosmetic.
    tg_send(
        bot_token, chat_id,
        "⚙️ Two settings still need doing by hand on the Gumroad product page "
        "(no API flag exists for either):\n\n"
        "1. Tick “Mark as e-publication for VAT” — affects EU tax rate on a PDF comic.\n"
        "2. Leave “Publicly show number of sales” OFF until the numbers are worth showing.\n\n"
        "Everything else (price, no-refunds, category, tags, images, CTA) is already set automatically.",
    )
    print("Sent link + promo post + promo graphic + settings reminder to Telegram")


if __name__ == "__main__":
    main()
