#!/usr/bin/env python3
"""Data-fetch pipeline entrypoint (replaces the GitHub Actions workflows).

Subcommands:
  fetch    Fetch one API, diff vs main, commit + push, send Discord webhooks.
           With --compare-after, runs the airport comparison afterward.
  compare  Run the airport comparison and publish its changes.
"""

import argparse
import re
import subprocess
import time

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
