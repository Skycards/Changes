# Skycards API Data Repository

This repository automatically fetches and stores data from the Skycards API endpoints as JSON files.

## ⚠️ Disclaimer

This project is **not affiliated with, endorsed by, or connected to Skycards** in any way. This is an independent data collection project that uses publicly available API endpoints. All data remains the property of Skycards and their respective owners.

## Data Sources

- **airports.json** - Airport data from `https://api.skycards.oldapes.com/airports`
- **models.json** - Aircraft models data from `https://api.skycards.oldapes.com/models`

## Automation

The repository uses GitHub Actions to automatically fetch updated data every 30 minutes. The workflow:

1. Fetches data from both API endpoints with a current timestamp parameter
2. Saves the responses as JSON files
3. Commits changes only if the data has been updated
4. Runs automatically every 30 minutes via scheduled workflow

## Workflow Details

- **Schedule**: Every 30 minutes (`*/30 * * * *`)
- **Manual Trigger**: The workflow can also be triggered manually via GitHub's Actions tab
- **Smart Commits**: Only commits when actual changes are detected in each API response
- **Individual Processing**: Each API endpoint is processed separately using a matrix strategy
- **Timestamp Parameter**: Appends `?updatedAt=<current_timestamp>` to API requests
- **Conventional Commits**: Uses [Conventional Commits](https://www.conventionalcommits.org/) format for commit messages
- **Concurrent Push Safety**: Handles race conditions when parallel jobs try to push simultaneously

## Architecture

The system uses a modular approach with two GitHub Actions workflows:

1. **Main Scheduler** (`.github/workflows/fetch-api-data.yml`) - Runs on schedule and defines the API endpoints in a matrix
2. **Reusable Fetcher** (`.github/workflows/fetch-single-api.yml`) - Handles fetching and committing individual API endpoints

This design allows for:

- Independent processing of each API endpoint
- Separate commits for each data source
- Easy addition of new API endpoints by updating the matrix
- Better error isolation (if one API fails, others continue)
- Race condition handling for concurrent pushes from parallel jobs

## Files

- `.github/workflows/fetch-api-data.yml` - Main workflow with scheduling and matrix configuration
- `.github/workflows/fetch-single-api.yml` - Reusable workflow for fetching individual APIs
- `airports.json` - Latest airport data (created automatically)
- `models.json` - Latest aircraft models data (created automatically)

## Manual Execution

You can manually trigger the data fetch by:

1. Going to the "Actions" tab in this repository
2. Selecting the "Fetch API Data" workflow
3. Clicking "Run workflow"

## Commit Messages

The system uses [Conventional Commits](https://www.conventionalcommits.org/) format for all automated commits:

**Format**: `chore(<data_name>): update data - <timestamp>`

**Examples**:

- `chore(airports): update data - 2025-01-15 14:30:00 UTC`
- `chore(models): update data - 2025-01-15 14:30:00 UTC`

## Discord Webhooks

This repository can send Discord webhook notifications when data is updated. If you would like your Discord webhook to be added to receive notifications of data changes, please contact me.

## Data Format

The JSON files contain the raw response from the Skycards API endpoints, preserving the original structure and format provided by the API. The files are automatically formatted with proper indentation for improved readability.
