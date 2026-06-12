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


REPO = "Skycards/Changes"
COMMIT_URL = "https://github.com/Skycards/Changes/commit/{sha}"


def clone(workdir, token, repo=REPO, author_name="Skycards Changes",
          author_email="noreply@github.com"):
    """Partial-clone repo into workdir (full history, blobs on demand)."""
    url = f"https://x-access-token:{token}@github.com/{repo}.git"
    subprocess.run(["git", "clone", "--filter=blob:none", url, workdir],
                   check=True, capture_output=True, text=True)
    _run(["config", "user.name", author_name], cwd=workdir, check=True)
    _run(["config", "user.email", author_email], cwd=workdir, check=True)


def show_file(ref, path, cwd=None):
    """Return blob contents at ref:path, or '' if absent."""
    res = _run(["show", f"{ref}:{path}"], cwd=cwd)
    return res.stdout if res.returncode == 0 else ""


def last_commit_touching(path, cwd=None):
    """Return the hash of the most recent commit that changed path, or ''."""
    res = _run(["log", "-1", "--format=%H", "--", path], cwd=cwd)
    return res.stdout.strip()


def head_sha(cwd=None):
    return _run(["rev-parse", "HEAD"], cwd=cwd, check=True).stdout.strip()


def commit(files, title, body=None, cwd=None):
    _run(["add", *files], cwd=cwd, check=True)
    args = ["commit", "-m", title]
    if body:
        args += ["-m", body]
    _run(args, cwd=cwd, check=True)


def push_with_retry(cwd=None, attempts=3):
    for i in range(1, attempts + 1):
        if _run(["push"], cwd=cwd).returncode == 0:
            return
        if i == attempts:
            raise RuntimeError(f"git push failed after {attempts} attempts")
        _run(["pull", "--rebase", "origin", "main"], cwd=cwd, check=True)
