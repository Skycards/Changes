"""Git operations for the data-fetch pipeline.

Ported from the former fetch-single-api.yml / compare-airports.yml workflow
steps: partial clone, identity, change detection, capture-previous, commit,
push-with-retry.
"""

import subprocess


def _run(args, cwd=None, check=False):
    return subprocess.run(["git", *args], cwd=cwd, check=check,
                          capture_output=True, text=True)


def detect_changes(output_file, cwd=None):
    """Return (changed, only_updatedAt) for output_file vs HEAD."""
    quiet = _run(["diff", "--quiet", "HEAD", output_file], cwd=cwd)
    if quiet.returncode == 0:
        return (False, False)

    diff = _run(["diff", "HEAD", output_file], cwd=cwd)
    changed = [
        line for line in diff.stdout.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not (line.startswith("+++") or line.startswith("---"))
    ]
    if not changed:
        return (True, True)
    non_updatedat = [line for line in changed if "updatedAt" not in line]
    return (True, len(non_updatedat) == 0)
