# Skycards / FR24 Airport Wishlist

A public Google Sheet that tracks airports (and airport data fixes) that Skycards players want in the game. Skycards is a game published by Flightradar24 (FR24) and uses their data for airports, flights and more, so every request here is really a request to FR24.

Sheet: <https://docs.google.com/spreadsheets/d/1_UJ58i3ojnDrto_T4jljMa3BhfN6s54CuaAON4_3qJ8/edit?usp=sharing>

Anyone with the link can view it.

## Who is involved

- Maintained by Bas (this repo's owner).
- Co-maintained by Nyax and Nick.
- Olov and David (the Skycards devs) also maintain it.
- Mike from Flightradar24 has access and handles the airports on the list.

## Tabs

The sheet's main tab is `Wishlist`. It starts with a summary row (pending additions, how many of those are already in FR24 with a hidden pin, open issues, open removals), then the header row, then one row per request.

Other tabs may appear from time to time while we review data. They are temporary and use the same layout.

## Workflow

1. Other players suggest airports (or fixes) to Bas, Nyax or Nick.
2. A maintainer adds the request to the sheet as `Pending`.
3. Once the airport has been updated in FR24, the status is changed to `Accepted`. Maintainers do this by hand, or Mike (FR24) or the Skycards devs do it when they apply the change.

## Columns

| Column | Meaning |
| --- | --- |
| Type | `Addition` (airport FR24 lacks or has hidden), `Issue` (wrong data on an existing FR24 airport), `Removal` (airport that should go away). |
| Status | `Pending` (requested, not yet applied) or `Accepted` (FR24 has applied it and it is live). Accepted rows stay on the sheet as history. |
| Region | Continent, e.g. Africa, North America, Antarctica. |
| Country | Country name (FR24 spelling, e.g. `Congo-Kinshasa`). |
| Subdivision | State or province, often empty. |
| Airport name | The name it should have. |
| IATA / ICAO / LID | Codes the airport should have. LID is the local identifier: any identifier assigned by the country the airport is in (for example the FAA code in the US). It matches the `lid` field in FR24's airport data. |
| Lat, Lon, Alt (ft) | Coordinates and elevation in feet. Only filled in when relevant: new airports and pin movements. |
| FR24 state / issue type | See below. |
| Link 1, Link 2 | Evidence, hyperlinked in the sheet. On additions: a flight id, a registration, or the flight number when it is a scheduled service. On issues: a source such as SkyVector, Wikipedia or IATA. |
| Notes | Free text: traffic description, and for fixes the current vs. correct value ("Currently named 'X' in fr24, should be 'Y'"). |

### FR24 state values (additions)

- `Not in FR24` — FR24 has no such airport; it must be created.
- `In FR24, pin hidden` — the airport exists in FR24 but its pin is hidden, so Skycards does not show it. Needs the pin switched on.
- `In FR24, pin hidden, needs moving` — as above, and the pin is also in the wrong place.
- `Live (pin on)` — already visible; used for accepted rows.
- `Live (pin on), needs moving` — visible but the pin position is off.

### Issue types (corrections and issues)

`Name`, `Code` (IATA or ICAO), `Elevation`, `Pin position`, `Timezone`, `Country`, or a comma-separated combination such as `Code, Name`. Removals use `In Fr24`.

## How it relates to this repo

- `airports.json` mirrors FR24's mobile airport dataset (same ids), so an accepted wishlist row only shows up here once FR24 applies it and the daily airport comparison (`compare_airports.py`, see `AIRPORT_COMPARISON_README.md`) picks it up.
- Pending additions that are "In FR24, pin hidden" are never in `airports.json`, because FR24's feed omits hidden pins.
- The comparison reports name, IATA/ICAO and LID differences, which is the quickest way to see that a wishlist item was applied.
