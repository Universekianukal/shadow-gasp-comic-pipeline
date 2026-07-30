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

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-5"


def call_claude(system, user, max_tokens=1200):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": MODEL, "max_tokens": max_tokens,
            "system": system, "messages": [{"role": "user", "content": user}],
        }).encode(),
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {e.read().decode()}") from e
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"].strip()
    raise RuntimeError(f"No text block in response: {json.dumps(data)[:500]}")


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
    args = ap.parse_args()

    system = (
        "You write short, punchy Facebook promo posts for SHADOW GASP, an "
        "independent true-crime documentary comic series. Tone: intriguing and "
        "factual, never sensationalised or disrespectful to real victims. "
        "Hook the reader with the real mystery, then point to the comic. "
        "Include 4-6 relevant hashtags at the end. Output ONLY the post text, "
        "ready to paste — no preamble, no options, no quotes around it."
    )
    user = (
        f"Case: {args.case}\n"
        f"Gumroad link (include it near the end of the post): {args.url}\n\n"
        f"Write the Facebook post now. Keep it under 120 words."
    )

    post = call_claude(system, user)

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    tg_send(bot_token, chat_id, f"🔗 Shareable link:\n{args.url}")
    tg_send(bot_token, chat_id, f"📋 Facebook post (copy-paste):\n\n{post}")
    print("Sent link + promo post to Telegram")


if __name__ == "__main__":
    main()
