# Skycards API Data Repository

This repository automatically fetches and stores data from the Skycards API endpoints as JSON files.

## ⚠️ Disclaimer

This project is **not affiliated with, endorsed by, or connected to Skycards** in any way. This is an independent data collection project that uses publicly available API endpoints. All data remains the property of Skycards and their respective owners.

## Data Sources

- **airports.json** - Airport data from `https://api.skycards.oldapes.com/airports`
- **models.json** - Aircraft models data from `https://api.skycards.oldapes.com/models`
- **airlines.json** - Airline data from `https://api.skycards.oldapes.com/airlines` (the required snapshot timestamp is fetched from `https://api.skycards.oldapes.com/airlines/timestamp`)

## Automation

The data is fetched by Kubernetes CronJobs running on a Flux-managed cluster.
Each run:

1. Clones this repository and fetches an API endpoint with a current timestamp parameter
2. Saves the response as a JSON file (formatted with `jq`)
3. Commits and pushes the change only if the data has actually changed
4. Posts a Discord webhook summary linking to the commit

## Schedule

- **airports** and **models**: every 30 minutes (`*/30 * * * *`)
- **airlines**: daily at 09:00 UTC (`0 9 * * *`)
- **airport comparison**: chained onto the airports job (runs immediately after it)
- **Manual run**: `kubectl -n skycards create job --from=cronjob/fetch-airports manual-run`

Behavioral notes:

- **Smart Commits**: Only commits when actual changes are detected; changes limited to the `updatedAt` field are committed but do not trigger a webhook.
- **Timestamp Parameter**: Appends `?updatedAt=<current_timestamp>` to API requests (airlines uses a `timestamp` parameter fetched from its `/timestamp` endpoint).
- **Conventional Commits**: Uses [Conventional Commits](https://www.conventionalcommits.org/) format for commit messages.
- **Concurrent Push Safety**: Handles race conditions when jobs push simultaneously (`git pull --rebase` retry loop).

## Architecture

A single container image (`ghcr.io/skycards/changes`) runs `scripts/pipeline.py`;
each CronJob selects its work via arguments. The Python modules are:

1. **`scripts/pipeline.py`** - CLI entrypoint with `fetch` and `compare` subcommands; clones the repo, fetches, formats, commits/pushes, and notifies.
2. **`scripts/git_sync.py`** - Git operations: partial clone, change detection, capture-previous, commit, push-with-retry.
3. **`scripts/discord_notify.py`** - Posts Markdown summaries to every configured Discord webhook.
4. **`scripts/format_changes.py`** / **`compare_airports.py`** - Build the change summaries (unchanged from the previous setup).

This design allows for:

- Independent processing of each API endpoint (one CronJob each)
- Separate commits for each data source
- Better error isolation (if one job fails, others continue)
- Race condition handling for concurrent pushes

## Files

- `deploy/Dockerfile` - Container image for the pipeline
- `deploy/cronjob-*.yaml` - CronJob definitions (airports, models, airlines)
- `deploy/kustomization.yaml` - Kustomize entrypoint for Flux
- `deploy/secret.example.yaml` - Secret template (`GIT_TOKEN` + `WEBHOOK_*`); sealed before committing
- `.github/workflows/build-image.yml` - Builds and pushes the image to GHCR on code changes
- `scripts/` - The Python pipeline and its tests
- `airports.json` - Latest airport data (created automatically)
- `models.json` - Latest aircraft models data (created automatically)
- `airlines.json` - Latest airline data (created automatically)

## Deployment

Build/push the image (CI does this on merge), create the
`skycards-changes-secrets` SealedSecret, then apply `deploy/` via Flux.

## Commit Messages

The system uses [Conventional Commits](https://www.conventionalcommits.org/) format for all automated commits:

**Format**: `chore(<data_name>): update data - <timestamp>`

**Examples**:

- `chore(airports): update data - 2025-01-15 14:30:00 UTC`
- `chore(models): update data - 2025-01-15 14:30:00 UTC`

## Discord Webhooks

This repository can send Discord webhook notifications when data is updated. If you would like your Discord webhook to be added to receive notifications of data changes, please contact me.

Notifications include a formatted summary of what changed — aircraft stat changes
and added/removed models, airports and airline fleets grouped by continent →
country (→ region), each linking back to the commit. The Flightradar24 comparison
is reported as a Skycards "to be added / to be removed" worklist: new items this
update, a merged count of entries resolved (covered by the airports update), any
count-only movements, and an overall standing of how far the worklist stretches.
When a summary is too long for a single Discord message, a short TLDR is posted
with the full summary attached as a Markdown file.

## Data Format

The JSON files contain the raw response from the Skycards API endpoints, preserving the original structure and format provided by the API. The files are automatically formatted with proper indentation for improved readability.
