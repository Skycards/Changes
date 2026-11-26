# Skycards / FR24 Airport Wishlist

A public Google Sheet that tracks airports (and airport data fixes) that Skycards players want in the game. Since Skycards mirrors the Flightradar24 (FR24) mobile airport dataset, every change ends up as a request to FR24.

Sheet: <https://docs.google.com/spreadsheets/d/1_UJ58i3ojnDrto_T4jljMa3BhfN6s54CuaAON4_3qJ8/edit?usp=sharing>

Anyone with the link can view it.

## Who is involved

- Maintained by Bas (this repo's owner).
- Olov and David (the Skycards devs) also maintain it.
- Mike from Flightradar24 has access and handles the airports on the list.

## Tabs

Normally the sheet has a single tab, `Wishlist`. The two `(review)` tabs are temporary: co-maintainers create them with proposed rows, and Bas reviews them before adding the accepted rows to `Wishlist`. At the time of writing both exist.

The sheet title is "Skycards / FR24 Airport Wishlist". Each tab has a summary row on top (pending additions, how many of those are already in FR24 with a hidden pin, open issues, open removals), then the header row, then one row per request.

| Tab | What it holds | Row types | Status |
| --- | --- | --- | --- |
| `Wishlist` | The main, permanent list: everything that is submitted to FR24. | Addition, Issue, Removal | Pending, Accepted |
| `New airports (review)` | Temporary. Additions proposed by co-maintainers, waiting for Bas's review before they go onto `Wishlist`. | Addition | Pending |
| `FR24 corrections (review)` | Temporary. Corrections to airports FR24 already has, proposed by co-maintainers, waiting for Bas's review. | Issue, Removal | Pending |

Snapshot taken 2026-11-26 (row counts drift quickly):

- `Wishlist`: 357 rows — 306 additions, 42 issues, 9 removals; 255 pending, 102 accepted.
- `New airports (review)`: 221 additions.
- `FR24 corrections (review)`: 420 rows — 413 issues, 7 removals.

## Columns

All three tabs use the same layout.

| Column | Meaning |
| --- | --- |
| Type | `Addition` (airport FR24 lacks or has hidden), `Issue` (wrong data on an existing FR24 airport), `Removal` (airport that should go away). |
| Status | `Pending` or `Accepted`. |
| Region | Continent, e.g. Africa, North America, Antarctica. |
| Country | Country name (FR24 spelling, e.g. `Congo-Kinshasa`). |
| Subdivision | State or province, often empty. |
| Airport name | The name it should have. |
| IATA / ICAO / LID | Codes the airport should have. LID is the FAA Location Identifier; it mirrors the `lid` field in FR24's airport data. |
| (3 unlabeled columns) | Latitude, longitude and elevation in feet. Filled in on the review tabs, mostly empty on `Wishlist`. |
| FR24 state / issue type | See below. |
| Link 1, Link 2 | Evidence. On additions these are 8-character hex ids (the FR24 flight ids that prove traffic). On issues they are source names such as SkyVector, Wikipedia or IATA. |
| Notes | Free text: traffic description, and for fixes the current vs. correct value ("Currently named 'X' in fr24, should be 'Y'"). |
| Last column | Unlabeled `0` / `1` helper. It is `1` on the accepted row sampled; its exact meaning is not documented yet. |

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

## Planned

In-repo skills will help keep the wishlist up to date (checking which rows FR24 has applied, moving rows between tabs, etc.). They are not written yet.
