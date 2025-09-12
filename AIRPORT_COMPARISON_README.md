# Airport Count Comparison & Detailed Analysis

Automatically compares airport counts between Flightradar24 and our `airports.json` data, then identifies specific airports that have been added or removed.

## Components

### Python Script (`compare_airports.py`)

- Scrapes airport data from https://www.flightradar24.com/data/airports
- Maps country names to ISO country codes (e.g., "Norway" → "NO")
- Compares airport counts between FR24 and our `airports.json` file
- For countries with different counts, fetches detailed airport lists from individual FR24 country pages
- Identifies specific airports that are added or removed
- Saves detailed differences with airport metadata to `airport_differences.json`
- Uses only Python built-in libraries (no external dependencies)

### GitHub Action (`.github/workflows/compare-airports.yml`)

- Runs after the main "Fetch API Data" workflow completes
- Can be triggered manually via workflow_dispatch
- Executes the comparison script and generates a report
- Commits both the report and the detailed `airport_differences.json` file
- Sends Discord notifications when differences are found

## How It Works

1. **Data Scraping**: Extracts data from Flightradar24's airport directory page
2. **Country Mapping**: Converts country names to ISO codes (e.g., "United States" → "US")
3. **Airport Counting**: Groups airports by country code from our `airports.json` file
4. **Initial Comparison**: Shows countries with matching/different airport counts
5. **Detailed Analysis**: For countries with differences:
   - Fetches individual country pages from FR24
   - Extracts airport metadata (name, IATA, ICAO, coordinates, links)
   - Compares airport lists using IATA/ICAO codes as identifiers
   - Identifies specific added/removed airports
6. **Result Storage**: Saves detailed differences to `airport_differences.json`

## Example Output

```
=== AIRPORT COUNT COMPARISON ===

✅ NO: 57 airports (match)
❌ US: FR24=1604, Ours=1594 (diff: +10)
✅ DE: 149 airports (match)
❌ FR: FR24=157, Ours=147 (diff: +10)

=== SUMMARY ===
Countries with matching counts: 195
Countries with different counts: 33
Total countries compared: 228

==================================================
DETAILED ANALYSIS
==================================================

Analyzing detailed differences for 33 countries...

Processing Norway (NO): FR24=57, Ours=56
  Fetching airports for Norway from https://www.flightradar24.com/data/airports/norway
  Found 57 airports for Norway
  Added: 1 airports
  Removed: 0 airports

Note: 5-second delay between country requests to avoid HTTP 429 errors

✅ Detailed differences saved to airport_differences.json
📊 Summary:
   • 33 countries with differences
   • 89 airports added (in FR24 but not in our data)
   • 12 airports removed (in our data but not in FR24)
```

## JSON Output Format

The `airport_differences.json` file contains detailed information:

```json
{
	"summary": {
		"total_countries_with_differences": 33,
		"total_added_airports": 89,
		"total_removed_airports": 12
	},
	"countries": {
		"NO": {
			"country_name": "Norway",
			"iso_code": "NO",
			"fr24_count": 57,
			"skycards_count": 56,
			"difference": 1,
			"added_airports": [
				{
					"name": "Honefoss Eggemoen Airport",
					"iata": "QUE",
					"icao": "ENEG",
					"lat": 60.211742,
					"lon": 10.314016,
					"link": "https://www.flightradar24.com/data/airports/que"
				}
			],
			"removed_airports": [
				{
					"name": "Toronto Buttonville Municipal Airport",
					"iata": "",
					"icao": "",
					"lat": 43.862221,
					"lon": -79.370003
				}
			],
			"added_count": 1,
			"removed_count": 1
		}
	}
}
```

## Usage

### Manual Execution

```bash
python compare_airports.py
```

### GitHub Action

- Automatically runs after the API data fetch workflow
- Manual trigger: Go to Actions → Compare Airport Counts → Run workflow
- Results are committed to the repository and notifications sent to Discord

## Maintenance

If you see "Unknown country mapping" warnings, add the new country names to the `create_country_mapping()` function in `compare_airports.py`.

## Benefits

- **Automated Monitoring**: Catches discrepancies in airport data automatically
- **No Dependencies**: Uses only Python standard library for maximum compatibility
- **Comprehensive Coverage**: Handles 238+ countries and territories
- **Clear Reporting**: Easy-to-understand output showing exactly where differences exist
- **Detailed Analysis**: Identifies specific missing/extra airports with complete metadata
- **Structured Output**: Saves machine-readable JSON with airport details for further processing
- **Rate Limiting**: 5-second delays between requests to avoid HTTP 429 errors
- **Integration**: Seamlessly fits into existing GitHub Actions workflow
