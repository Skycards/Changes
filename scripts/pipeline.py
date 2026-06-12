#!/usr/bin/env python3
"""Data-fetch pipeline entrypoint (replaces the GitHub Actions workflows).

Subcommands:
  fetch    Fetch one API, diff vs main, commit + push, send Discord webhooks.
           With --compare-after, runs the airport comparison afterward.
  compare  Run the airport comparison and publish its changes.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

import discord_notify as dn
import git_sync as gs
import requests

# Kept byte-identical to the previous curl-based requests so the upstream API
# sees no behavior change.
HEADERS = {"User-Agent": "GitHub-Actions/1.0", "X-Client-Version": "3.0.0"}


def format_json(raw_text, path):
    """Pretty-print JSON via `jq '.'` — byte-identical to the historical
    curl|jq commits, so no first-run reformatting diff."""
    with open(path, "w", encoding="utf-8") as fh:
        subprocess.run(["jq", "."], input=raw_text, stdout=fh, check=True,
                       text=True)


def determine_timestamp(timestamp_url, session=None):
    if not timestamp_url:
        return str(int(time.time() * 1000))
    session = requests.Session() if session is None else session
    ts = session.get(timestamp_url, headers=HEADERS).text.strip()
    if not re.fullmatch(r"[0-9]+", ts):
        raise ValueError(f"Invalid timestamp received: {ts!r}")
    return ts


def resolve_mention(mention_everyone, is_misc):
    # @everyone only for gameplay-relevant (non-misc) changes when enabled.
    return "@everyone" if (mention_everyone and not is_misc) else ""


def fetch_api(api_url, timestamp_param, timestamp, session):
    resp = session.get(api_url, params={timestamp_param: timestamp},
                       headers=HEADERS)
    return resp.text


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
FORMAT_CHANGES = os.path.join(SCRIPTS_DIR, "format_changes.py")
COMPARE_SCRIPT = os.path.join(SCRIPTS_DIR, "..", "compare_airports.py")


def _utc_stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def run_fetch(args, workdir, session):
    out_path = os.path.join(workdir, args.output_file)
    timestamp = determine_timestamp(args.timestamp_url or None, session)
    print(f"Fetching {args.data_name} from {args.api_url} "
          f"({args.timestamp_param}={timestamp})")
    format_json(fetch_api(args.api_url, args.timestamp_param, timestamp, session),
                out_path)

    changed, only_updatedat = gs.detect_changes(args.output_file, cwd=workdir)
    if not changed:
        print(f"No changes for {args.data_name}.")
        return

    msg_file = os.path.join(tempfile.gettempdir(), "webhook_message.md")
    meta_file = os.path.join(tempfile.gettempdir(), "webhook_meta.txt")
    caption_file = os.path.join(tempfile.gettempdir(), "webhook_caption.txt")
    tldr = ""
    if not only_updatedat:
        prev = os.path.join(tempfile.gettempdir(), "previous.json")
        with open(prev, "w", encoding="utf-8") as fh:
            fh.write(gs.show_file("HEAD", args.output_file, cwd=workdir))
        tldr = subprocess.run(
            [sys.executable, FORMAT_CHANGES, "--type", args.data_name,
             "--old", prev, "--new", out_path, "--link", "__COMMIT_URL__",
             "--out", msg_file, "--meta-out", meta_file,
             "--caption-out", caption_file],
            cwd=workdir, check=True, capture_output=True, text=True).stdout.strip()

    body = tldr or None
    gs.commit([args.output_file],
              f"chore({args.data_name}): update data - {_utc_stamp()}",
              body=body, cwd=workdir)
    gs.push_with_retry(cwd=workdir)

    if only_updatedat:
        print("Only updatedAt changed - skipping webhooks.")
        return

    link = gs.COMMIT_URL.format(sha=gs.head_sha(cwd=workdir))
    _substitute(msg_file, "__COMMIT_URL__", link)
    is_misc = _read(meta_file).strip() == "true"
    dn.send_discord(msg_file, tldr=tldr, caption=_read(caption_file),
                    link=link, username="Skycards",
                    mention=resolve_mention(args.mention_everyone, is_misc),
                    session=session)


def run_compare(workdir, session):
    out = "airport_differences.json"
    subprocess.run([sys.executable, os.path.abspath(COMPARE_SCRIPT)],
                   cwd=workdir, check=True)
    changed, _ = gs.detect_changes(out, cwd=workdir)
    if not changed:
        print("No changes in airport comparison.")
        return

    last = gs.last_commit_touching(out, cwd=workdir)
    prev_diff = os.path.join(tempfile.gettempdir(), "previous_differences.json")
    prev_air = os.path.join(tempfile.gettempdir(), "previous_airports.json")
    for ref_path, dest in ((out, prev_diff), ("airports.json", prev_air)):
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(gs.show_file(last, ref_path, cwd=workdir) if last else "")

    msg_file = os.path.join(tempfile.gettempdir(), "cmp_message.md")
    tldr = subprocess.run(
        [sys.executable, FORMAT_CHANGES, "--type", "comparison",
         "--old", prev_diff, "--new", os.path.join(workdir, out),
         "--old-airports", prev_air,
         "--airports", os.path.join(workdir, "airports.json"),
         "--link", "__COMMIT_URL__", "--out", msg_file],
        cwd=workdir, check=True, capture_output=True, text=True).stdout.strip()

    gs.commit([out],
              f"chore(comparison): update airport comparison data - {_utc_stamp()}",
              body=tldr or None, cwd=workdir)
    gs.push_with_retry(cwd=workdir)

    link = gs.COMMIT_URL.format(sha=gs.head_sha(cwd=workdir))
    _substitute(msg_file, "__COMMIT_URL__", link)
    dn.send_discord(msg_file, tldr=tldr, link=link,
                    username="Skycards Airport Comparison", mention="",
                    session=session)


def _substitute(path, placeholder, value):
    text = _read(path)
    if text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(placeholder, value))


def build_parser():
    parser = argparse.ArgumentParser(description="Skycards data-fetch pipeline.")
    sub = parser.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch")
    f.add_argument("--data-name", required=True)
    f.add_argument("--api-url", required=True)
    f.add_argument("--output-file", required=True)
    f.add_argument("--timestamp-param", default="updatedAt")
    f.add_argument("--timestamp-url", default="")
    f.add_argument("--compare-after", action="store_true")
    f.add_argument("--mention-everyone", dest="mention_everyone",
                   action="store_true")
    f.add_argument("--no-mention-everyone", dest="mention_everyone",
                   action="store_false")
    f.set_defaults(mention_everyone=True)

    sub.add_parser("compare")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    token = os.environ["GIT_TOKEN"]
    author_name = os.environ.get("GIT_AUTHOR_NAME", "Skycards Changes")
    author_email = os.environ.get("GIT_AUTHOR_EMAIL", "noreply@github.com")
    session = requests.Session()
    with tempfile.TemporaryDirectory() as workdir:
        repo_dir = os.path.join(workdir, "repo")
        gs.clone(repo_dir, token, author_name=author_name,
                 author_email=author_email)
        if args.command == "fetch":
            run_fetch(args, repo_dir, session)
            if args.compare_after:
                run_compare(repo_dir, session)
        else:
            run_compare(repo_dir, session)


if __name__ == "__main__":
    main()
