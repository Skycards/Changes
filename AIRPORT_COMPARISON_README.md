# Airport Count Comparison & Detailed Analysis

Automatically compares airport counts between Flightradar24 and our `airports.json` data, then identifies specific airports that have been added or removed.

## Components

### Python Script (`compare_airports.py`)

- Fetches FR24's mobile-app airport dataset with a single GET to
  `https://www.flightradar24.com/mobile/airports/format/4?version=1` — one
  JSON document listing every FR24 airport (id, name, iata, icao, city, lat,
  lon, country, alt, size, timezone, countryId). This is the dataset our
  `airports.json` mirrors (the ids are the same), unlike the website's
  `/data/airports` pages, which are maintained separately and drift from it.
- Validates the payload before comparing: it must parse as JSON and contain
  at least 5,000 rows with distinct integer ids. A Cloudflare challenge page
  or a shrunken/degenerate payload fails that check, and the run aborts
  (exit 1) without touching `airport_differences.json` — a bad fetch can
  never be mistaken for a mass removal. A failed write of the output file
  also exits 1.
- Matches airports by id (Skycards ids are FR24 mobile ids). Matched
  airports are compared on name (whitespace-collapsed), IATA, and ICAO, and
  any differences land in a `changes` map on a `changed_airports` entry.
  Rows FR24 has that we don't become `added_airports`; rows we have that
  FR24 doesn't become `removed_airports`. Our rows with neither an IATA nor
  an ICAO code are excluded from matching and counts — they're remnants of
  airports FR24 has already deleted.
- Maps FR24 country names to ISO country codes (e.g., "Norway" → "NO")
- Groups matched and removed airports by *our own* `placeCode`, so an FR24
  country mislabel can never manufacture a phantom added/removed pair. Added
  airports are grouped by FR24's country label via the name → ISO mapping; a
  label that doesn't map lands in a top-level `unmapped` list in the output
  instead of being silently dropped.
- For the countries our data subdivides (currently US, CA, AU, CN — detected
  dynamically from placeCodes containing a `-`), added airports get a state
  placeCode derived from their FR24 coordinates via a point-in-polygon
  lookup (`state_lookup.py`) against `data/ne_50m_admin_1_states.geojson`, a
  stripped-down Natural Earth 50m admin-1 boundaries file (public domain;
  regenerate with `python3 scripts/build_state_boundaries.py`, which also
  covers BR, IN, ID, RU, ZA for future use). Measured accuracy is ~99.7%
  overall; a point that can't be placed (typically a remote island) falls
  back to the bare country code.
- Records a per-state breakdown under `states` in the differences file for
  subdivisioned countries (states with differences only), built from the
  same placeCodes as the country-level counts, so the two always sum
  consistently.
- Saves detailed differences with airport metadata to `airport_differences.json`
- Uses only Python built-in libraries (no external dependencies)

### GitHub Action (`.github/workflows/compare-airports.yml`)

- Runs after the main "Fetch API Data" workflow completes
- Can be triggered manually via workflow_dispatch
- Executes the comparison script and generates a report
- Commits both the report and the detailed `airport_differences.json` file
- Sends Discord notifications when differences are found

## How It Works

1. **Data Fetch**: One GET to FR24's mobile-app airports endpoint returns a single JSON document listing every FR24 airport
2. **Validation**: The payload must parse as JSON and contain at least 5,000 rows with distinct integer ids; anything less (a Cloudflare challenge, a truncated response, a schema change) aborts the run before any comparison happens, so a bad fetch can never produce false mass-removals
3. **Country Mapping**: Converts FR24's country names to ISO codes (e.g., "United States" → "US") for airports FR24 has that we don't
4. **Id Matching**: Matches airports on both sides by id — Skycards ids are FR24 mobile ids, so this is a direct join rather than a name/IATA/ICAO lookup
5. **Field Comparison**: Matched airports are compared on name (whitespace-collapsed), IATA, and ICAO; any difference produces a `changed_airports` entry with a `changes` map of the old and new value for each field
6. **Grouping**: Matched and removed airports are grouped by our own `placeCode` (immune to FR24 country mislabels); airports FR24 has that we don't are grouped by the ISO code their FR24 country name maps to, or land in a top-level `unmapped` list if it doesn't map
7. **State Attribution**: For the countries our data subdivides (US, CA, AU, CN), added airports get a state placeCode from their FR24 coordinates via a point-in-polygon lookup against Natural Earth admin-1 boundaries
8. **Result Storage**: Saves per-country differences — plus a per-state breakdown for subdivisioned countries and any unmapped rows — to `airport_differences.json`

**Update detection**: because matching is by id rather than by IATA/ICAO, a changed airport falls directly out of the join — there's no need to pair up leftover added/removed records after the fact. Every matched pair is checked for name, IATA, and ICAO differences regardless of whether its country's counts differ, and any difference produces a `changed_airports` entry with a `changes` map of the old and new value for each differing field.

## Example Output

```
Starting airport comparison...
Loaded state boundaries: 9 countries, 294 regions
Fetching FR24 mobile airports dataset...
  Fetching FR24 mobile airports from https://www.flightradar24.com/mobile/airports/format/4?version=1
FR24 payload version 1788190045 (2026-08-31 15:27 UTC)
Fetched 7042 airports from FR24
Loading our airports data...
Found 228 countries in our data
Comparing by airport id...
Skycards side: 7028 airports with codes (19 codeless excluded)
  geo state: DTX McKinney National Airport -> US-TX
  geo state: XYZ Example Airfield -> US (no state found)
  ...
Matched 6952 airports by id; 90 only in FR24 (added), 76 only in ours (removed), 3 changed
Differences by country:
  NO (Norway): +1 -0 ~1
  US (United States): +8 -3 ~2 | states: TX+1 CA-1 NY+2
  ...
⚠️  Unmapped FR24 country 'Some New Territory': Example Airport (XYZ)

✅ Detailed differences saved to airport_differences.json
📊 Summary:
   • 33 countries with differences
   • 89 airports added (in FR24 but not in our data)
   • 76 airports removed (in our data but not in FR24)
   • 3 airports changed (matched, but with updated fields)
```

## JSON Output Format

The `airport_differences.json` file contains detailed information:

```json
{
	"summary": {
		"total_countries_with_differences": 33,
		"total_added_airports": 89,
		"total_removed_airports": 12,
		"total_changed_airports": 5
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
					"placeCode": "NO"
				}
			],
			"removed_airports": [],
			"changed_airports": [
				{
					"name": "Fagernes Leirin Airport",
					"iata": "VDB",
					"icao": "ENFG",
					"placeCode": "NO",
					"changes": {
						"name": {
							"old": "Fagernes Airport",
							"new": "Fagernes Leirin Airport"
						}
					}
				}
			],
			"added_count": 1,
			"removed_count": 0,
			"changed_count": 1
		}
	}
}
```

For the countries our data subdivides (currently US, CA, AU, CN), the
country record also carries a `states` object — one entry per state with
differences, in the same added/removed shape:

```json
{
	"states": {
		"TX": {
			"state_name": "Texas",
			"fr24_count": 254,
			"skycards_count": 253,
			"difference": 1,
			"added_airports": [
				{
					"name": "McKinney National Airport",
					"iata": "DTX",
					"icao": "KTKI",
					"placeCode": "US-TX"
				}
			],
			"removed_airports": [],
			"added_count": 1,
			"removed_count": 0
		}
	}
}
```

When an FR24 country name doesn't map to an ISO code, its added airports are
collected in a top-level `unmapped` array instead of the `countries` object:

```json
{
	"unmapped": [
		{
			"name": "Some New Airport",
			"iata": "XYZ",
			"icao": "KXYZ",
			"country": "Some New Territory"
		}
	]
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

If you see `⚠️  Unmapped FR24 country` warnings (also collected under `unmapped` in the output file), add the new country name to the `create_country_mapping()` function in `compare_airports.py`.

## Benefits

- **Automated Monitoring**: Catches discrepancies in airport data automatically
- **No Dependencies**: Uses only Python standard library for maximum compatibility
- **Comprehensive Coverage**: Covers every country present in FR24's mobile airport dataset, not a fixed list
- **Clear Reporting**: Easy-to-understand output showing exactly where differences exist
- **Detailed Analysis**: Identifies specific missing/extra airports with complete metadata
- **Structured Output**: Saves machine-readable JSON with airport details for further processing
- **Resilient Fetching**: One request per run, with automatic retries (10s/15s/20s backoff) instead of a fixed request cadence
- **Integration**: Seamlessly fits into existing GitHub Actions workflow
