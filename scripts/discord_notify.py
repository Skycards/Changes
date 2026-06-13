"""Post Markdown change messages to subscribed Discord webhooks.

Routing is type-keyed. WEBHOOKS_CONFIG (ConfigMap JSON) maps each message type
to a list of {webhook, mention} subscriptions; WEBHOOK_URLS (Secret JSON) maps
webhook names to URLs. Each subscriber of a message's type receives it with its
own mention prefix (empty = no mention).
"""

import json
import os
import re

import requests

AVATAR = "https://avatars.githubusercontent.com/u/224248835?s=256"
LIMIT = 1900
VALID_TYPES = ("airports", "models", "airlines", "comparison", "misc")


def load_webhook_routes(env=None):
    """Parse WEBHOOKS_CONFIG + WEBHOOK_URLS into {type: [(name, url, mention), ...]}.

    Warns and skips unknown message types and subscriptions whose webhook name
    has no URL. Returns {} when no config is present.
    """
    env = os.environ if env is None else env
    config = json.loads(env.get("WEBHOOKS_CONFIG") or "{}")
    urls = json.loads(env.get("WEBHOOK_URLS") or "{}")

    routes = {}
    for msg_type, subs in config.items():
        if msg_type not in VALID_TYPES:
            print(f"Unknown webhook type '{msg_type}' in WEBHOOKS_CONFIG; skipping.")
            continue
        resolved = []
        for sub in subs:
            name = sub.get("webhook")
            url = urls.get(name)
            if not url:
                print(f"Webhook '{name}' (type '{msg_type}') has no URL; skipping.")
                continue
            resolved.append((name, url, sub.get("mention", "")))
        routes[msg_type] = resolved
    return routes


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


def send_discord(message_file, tldr, link, username, routing_key, caption="",
                 routes=None, session=None):
    routes = load_webhook_routes() if routes is None else routes
    session = requests.Session() if session is None else session

    try:
        with open(message_file, encoding="utf-8") as fh:
            message = fh.read()
    except FileNotFoundError:
        message = ""
    if not message:
        print("No message file or empty message; nothing to send.")
        return

    subscribers = routes.get(routing_key, [])
    if not subscribers:
        print(f"No webhooks subscribed to '{routing_key}'; nothing to send.")
        return

    long_message = len(message) > LIMIT
    if long_message:
        attach = _strip_discord_artifacts(message)
        file_title = message.split("\n", 1)[0]
        body = caption or tldr

    for name, url, mention in subscribers:
        if not long_message:
            payload = build_inline_payload(message, username, mention)
            r = session.post(url, json=payload)
            r.raise_for_status()
        else:
            content = build_attachment_content(file_title, body, link, mention)
            payload = {"content": content, "username": username,
                       "avatar_url": AVATAR,
                       "attachments": [{"id": 0, "filename": "changes.md"}]}
            r = session.post(
                url,
                data={"payload_json": json.dumps(payload)},
                files={"files[0]": ("changes.md", attach, "text/markdown")},
            )
            r.raise_for_status()
