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
