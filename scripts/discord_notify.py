"""Post Markdown change messages to all configured Discord webhooks.

Port of the former .github/actions/send-discord composite action. Webhook URLs
are read from every WEBHOOK_*-prefixed environment variable.
"""

import json
import os
import re

import requests

AVATAR = "https://avatars.githubusercontent.com/u/224248835?s=256"
LIMIT = 1900


def webhook_urls(env=None):
    env = os.environ if env is None else env
    return [v for k, v in sorted(env.items()) if k.startswith("WEBHOOK_") and v]


def _strip_discord_artifacts(text):
    # Discord-only rendering hacks are noise in the raw file preview:
    #   leading-dash escapes (\-) that stop sub-lines becoming bullets, and
    #   angle brackets around link targets ([x](<url>)) that suppress embeds.
    lines = [re.sub(r"^(\s*)\\-", r"\1-", line) for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\]\(<([^>]*)>\)", r"](\1)", text)


def build_inline_payload(message, username, mention):
    prefix = f"{mention}\n" if mention else ""
    return {"content": f"{prefix}{message}", "username": username,
            "avatar_url": AVATAR, "attachments": []}


def build_attachment_content(file_title, body, link, mention):
    prefix = f"{mention}\n" if mention else ""
    return (f"{prefix}{file_title}\n{body}\n\n"
            f"See [commit](<{link}>) for full changes")


def send_discord(message_file, tldr, link, username, caption="", mention="",
                 env=None, session=None):
    env = os.environ if env is None else env
    session = requests.Session() if session is None else session

    try:
        with open(message_file, encoding="utf-8") as fh:
            message = fh.read()
    except FileNotFoundError:
        message = ""
    if not message:
        print("No message file or empty message; nothing to send.")
        return

    urls = webhook_urls(env)
    if len(message) <= LIMIT:
        payload = build_inline_payload(message, username, mention)
        for url in urls:
            r = session.post(url, json=payload)
            r.raise_for_status()
        return

    # Too long: attach the stripped message as a file, keep a short caption.
    attach = _strip_discord_artifacts(message)
    file_title = message.split("\n", 1)[0]
    body = caption or tldr
    content = build_attachment_content(file_title, body, link, mention)
    payload = {"content": content, "username": username, "avatar_url": AVATAR,
               "attachments": [{"id": 0, "filename": "changes.md"}]}
    for url in urls:
        r = session.post(
            url,
            data={"payload_json": json.dumps(payload)},
            files={"files[0]": ("changes.md", attach, "text/markdown")},
        )
        r.raise_for_status()
