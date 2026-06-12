# Skycards/Changes — GitHub Actions → Kubernetes (Flux) CronJobs

**Date:** 2026-06-12
**Status:** Approved (pending spec review)

## Goal

Replace the three scheduled GitHub Actions data-fetch workflows with Kubernetes
CronJobs running on a Flux-managed cluster. Behavior must stay 1:1 with today:
fetch an API, diff the JSON against the last git commit, commit + push the
change back to the GitHub repo, and post a Discord webhook linking to that
commit. The repo history *is* the product, so git commit/push is retained.

## What exists today

Three workflows, all delegating to the reusable `fetch-single-api.yml`, plus a
composite `send-discord` action:

| Workflow | Schedule | Work |
|----------|----------|------|
| `fetch-api-data.yml` | `*/30 * * * *` | matrix: airports + models |
| `fetch-fleets-data.yml` | `0 9 * * *` | airlines |
| `compare-airports.yml` | after "Fetch API Data" (`workflow_run`) | runs `compare_airports.py`, commits `airport_differences.json` |

`fetch-single-api.yml` pipeline (per API):
1. checkout (with write token)
2. determine timestamp — from `timestamp_url` (validated numeric) or `date +%s%3N`
3. `curl` the API with `User-Agent`/`X-Client-Version` headers → `jq '.'` → output file
4. `git diff` change detection, plus an "only `updatedAt` changed" check that suppresses webhooks
5. capture previous version via `git show HEAD:<file>`
6. build webhook message: `python3 scripts/format_changes.py --type <data_name> ...` → message.md + meta + caption + tldr
7. commit (summary in body) + push, with a 3× `git pull --rebase` retry loop for the parallel-matrix race
8. substitute the real commit URL into the message (`__COMMIT_URL__` placeholder)
9. send Discord: loop `WEBHOOK_*` env vars; inline post, or file attachment when message > 1900 chars
10. mention rule: `@everyone` only when `mention_everyone && is_misc != 'true'`

## Decisions

- **State model:** keep git commit/push from inside the pod (deploy token).
- **Secrets:** Sealed Secrets.
- **Image:** single image, built + pushed to GHCR via a small Actions workflow; `args` select the work.
- **Manifests:** in this repo under `deploy/`.
- **compare-airports chaining:** chained into the airports job (same pod, after
  the airports commit/push). K8s has no native "run after Job X" trigger, and a
  separate offset CronJob re-introduces the timing race the `workflow_run`
  trigger was hiding. `compare_airports.py` only reads `airports.json`.
- **Clone strategy:** `git clone --filter=blob:none` (partial clone). Full
  commit graph (the compare step needs `git log -1 -- airport_differences.json`
  history), blobs fetched on demand — cheap despite the large, fast-growing
  JSON history.
- **Language:** Python only. No bash entrypoint/lib. `pipeline.py` reuses
  `format_changes.py` and `compare_airports.py` unchanged via subprocess.

## Architecture

### Single image (`deploy/Dockerfile`)

- Base `python:3.11-slim` + `git`, `ca-certificates` (curl/jq no longer needed).
- `pip install -r requirements.txt` (just `requests`).
- Copies `scripts/`, `compare_airports.py`.
- Runs as a non-root user.
- Entrypoint: `python /app/scripts/pipeline.py`. CronJob `args` select the work.

The repo data (JSON files) is **not** baked into the image — it is cloned fresh
at runtime so each run diffs against current `main`.

### `scripts/pipeline.py` (new — the only substantial new code)

A single CLI orchestrator. Subcommands:

- `fetch` — args: `--api-url`, `--output-file`, `--data-name`,
  `--timestamp-param` (default `updatedAt`), `--timestamp-url` (optional),
  `--mention-everyone/--no-mention-everyone`, `--compare-after` (flag; set only
  on airports). Runs steps 2–10 above.
- `compare` — runs the airport-comparison pipeline (also reachable via
  `--compare-after` on the airports fetch). Runs `compare_airports.py`, diffs
  `airport_differences.json`, captures previous `airport_differences.json` +
  `airports.json` from the last commit that touched the differences file,
  builds the `--type comparison` message, commits + pushes, sends Discord.

Internal helpers (in `pipeline.py` or a small `scripts/changes/` package):

- `clone_repo()` — partial clone of `https://x-access-token:$GIT_TOKEN@github.com/Skycards/Changes.git` into a temp workdir; configures `user.name`/`user.email`. Token never logged.
- `git_push_with_retry()` — port of the 3× `pull --rebase` / `push` loop.
- `detect_changes()` — `git diff` + the "only `updatedAt`" suppression logic.
- `send_discord()` — port of the `send-discord` composite action: iterates
  `WEBHOOK_*` env, inline vs. multipart file attachment at the 1900-char limit,
  same caption/tldr/link fallback, same mention-prefix-on-own-line behavior.
- `format_changes.py` and `compare_airports.py` are invoked as subprocesses with
  the same arguments the workflows use today — left unchanged.

Git auth: HTTPS with a fine-grained PAT (`contents: write`) in the clone URL.

### CronJobs (`deploy/`)

| CronJob | Schedule | `args` |
|---------|----------|--------|
| `fetch-airports` | `*/30 * * * *` | `fetch --data-name airports --api-url …/airports --output-file airports.json --mention-everyone --compare-after` |
| `fetch-models` | `*/30 * * * *` | `fetch --data-name models --api-url …/models --output-file models.json --mention-everyone` |
| `fetch-airlines` | `0 9 * * *` | `fetch --data-name airlines --api-url …/airlines --output-file airlines.json --timestamp-param timestamp --timestamp-url …/airlines/timestamp --no-mention-everyone` |

Each CronJob:
- `concurrencyPolicy: Forbid`
- `restartPolicy: OnFailure`
- `successfulJobsHistoryLimit: 1`, `failedJobsHistoryLimit: 3`
- `startingDeadlineSeconds` set
- modest CPU/memory requests + limits
- `envFrom` the sealed Secret (git token + `WEBHOOK_*`)
- image ref from a shared field / overlay so the build can bump the tag

The mention behavior keeps the original split: airports/models may `@everyone`
(subject to the `is_misc` check), airlines never does.

### Secrets (Sealed Secrets)

One `SealedSecret` → `Secret skycards-changes-secrets` with:
- `GIT_TOKEN` — fine-grained PAT, `contents: write` on `Skycards/Changes`
- `WEBHOOK_*` — one key per Discord webhook (consumed by the `WEBHOOK_`-prefix loop)

Delivered as: a committed plaintext template (`deploy/secret.example.yaml`) + a
`kubeseal` command. The encrypted `SealedSecret` is what gets committed.

### Flux wiring (`deploy/kustomization.yaml`)

Kustomize base: Namespace + SealedSecret + 3 CronJobs. The existing Flux
`Kustomization` points its `path:` at `deploy/`. A commented example
`GitRepository` + `Kustomization` is included for dropping into the GitOps repo
if this repo isn't already a Flux source.

### Image CI (`.github/workflows/build-image.yml`)

- Trigger: `push` to `main` with `paths:` limited to `deploy/**`, `scripts/**`,
  `compare_airports.py`, `requirements.txt`. The bot's `chore(...)` commits only
  touch root `*.json`, so they never trigger a build — no build spam.
- Also `workflow_dispatch`.
- Builds + pushes `ghcr.io/skycards/changes:<sha>` and `:latest`.

## Migration / cleanup

- The three data-fetch workflows (`fetch-api-data.yml`, `fetch-fleets-data.yml`,
  `compare-airports.yml`, `fetch-single-api.yml`) and the `send-discord` action
  are **deleted** once the CronJobs are validated in-cluster. Keep them in place
  during initial rollout for easy rollback.
- `requirements.txt` added at repo root.

## Out of scope

- Migrating off git as the state store.
- Flux image-automation (auto-bumping the running tag) — manual/CI tag bump for now.
- Any change to `format_changes.py` / `compare_airports.py` logic.

## Testing

- Unit: `git_push_with_retry`, `detect_changes` (incl. only-`updatedAt`), and
  `send_discord` payload construction (inline vs. attachment threshold, mention
  prefix) — with mocked git/HTTP.
- Integration (manual, pre-cutover): run the image locally against a throwaway
  branch / test webhook; confirm commit + Discord output matches the current
  workflow output for a known diff.
- Existing `scripts/tests` for `format_changes.py` continue to pass unchanged.
