#!/usr/bin/env python3
"""
Script to compare Flightradar24 airport counts with our airports.json data
"""

import json
import sys
import time
from collections import Counter
from typing import Dict, List, Tuple, Optional
import urllib.request
import state_lookup


# The FR24 mobile-app dataset: one JSON document with every airport. This is
# the dataset airports.json mirrors (same id space), unlike the website's
# /data/airports pages which are maintained separately and drift from it.
MOBILE_AIRPORTS_URL = "https://www.flightradar24.com/mobile/airports/format/4?version=1"

# A genuine payload has ~7,000 airports with distinct ids. A well-formed but
# shrunken or degenerate dataset (schema change, duplicated ids, partial
# rollout) must be treated as a failed fetch — never compared, which would
# report thousands of false removals.
MIN_MOBILE_ROWS = 5000


def parse_mobile_payload(text: str) -> List[Dict]:
    """Parse and validate the mobile airports payload. Raises ValueError."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"mobile payload is not JSON: {e}") from e
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("mobile payload has no 'rows' list")
    ids = {row.get("id") for row in rows
           if isinstance(row, dict) and isinstance(row.get("id"), int)}
    if len(ids) < MIN_MOBILE_ROWS:
        raise ValueError(
            f"mobile payload has only {len(ids)} usable airport ids "
            f"(< {MIN_MOBILE_ROWS}); treating as failed fetch")
    return rows


def fetch_mobile_airports() -> Optional[List[Dict]]:
    """Fetch FR24's full airport list. Returns None on any failure."""
    text, error = _fetch_text(MOBILE_AIRPORTS_URL, "FR24 mobile airports")
    if error:
        return None
    try:
        return parse_mobile_payload(text)
    except ValueError as e:
        print(f"Error parsing FR24 mobile payload: {e}")
        return None


def _has_code(row: Dict) -> bool:
    return bool((row.get('iata') or '').strip() or (row.get('icao') or '').strip())


def _added_airport_record(row: Dict, place_code: str) -> Dict:
    """Project a mobile row to the output shape for added/changed airports."""
    return {
        'name': row.get('name', ''),
        'iata': (row.get('iata') or '').strip() or None,
        'icao': (row.get('icao') or '').strip(),
        'placeCode': place_code,
    }


def _sort_airports(airports: List[Dict]) -> None:
    airports.sort(key=lambda ap: (ap.get('iata') or '', ap.get('name') or ''))


def _states_breakdown(iso_code: str, added: List[Dict], removed: List[Dict],
                      our_rows: List[Dict], lookup) -> Dict[str, Dict]:
    """Per-state breakdown for a subdivided country, states with diffs only.

    Matched airports carry our placeCode, added airports the geo-derived one,
    so both sides of every per-state count come from the same placeCodes.
    Added airports whose geo lookup failed (bare-country placeCode) appear in
    the country aggregate only. Counts come from the same code-filtered
    our_rows as the country-level counts, so per-state totals always sum
    consistently with them.
    """
    prefix = f"{iso_code}-"

    def state_of(airport):
        place = airport.get('placeCode') or ''
        if place.startswith(prefix):
            return place.split('-', 1)[1]
        return None

    our_counts = Counter(row['placeCode'].split('-', 1)[1]
                         for row in our_rows
                         if (row.get('placeCode') or '').startswith(prefix))
    added_by_state: Dict[str, List[Dict]] = {}
    removed_by_state: Dict[str, List[Dict]] = {}
    for airport in added:
        state = state_of(airport)
        if state:
            added_by_state.setdefault(state, []).append(airport)
    for airport in removed:
        state = state_of(airport)
        if state:
            removed_by_state.setdefault(state, []).append(airport)

    breakdown = {}
    for state in sorted(set(added_by_state) | set(removed_by_state)):
        state_added = added_by_state.get(state, [])
        state_removed = removed_by_state.get(state, [])
        our_count = our_counts.get(state, 0)
        fr24_count = our_count - len(state_removed) + len(state_added)
        breakdown[state] = {
            'state_name': lookup.state_name(f"{iso_code}-{state}"),
            'fr24_count': fr24_count,
            'skycards_count': our_count,
            'difference': fr24_count - our_count,
            'added_airports': state_added,
            'removed_airports': state_removed,
            'added_count': len(state_added),
            'removed_count': len(state_removed),
        }
    return breakdown


def compare_mobile_airports(mobile_rows: List[Dict], airports_data: Dict,
                            country_mapping: Dict[str, str],
                            lookup) -> Tuple[Dict, List[Dict]]:
    """Diff FR24's mobile dataset against airports.json by airport id.

    Skycards ids are FR24 mobile ids, so the join is exact: rows on both
    sides are matched (field changes), FR24-only rows are added, our-only
    rows are removed. Matched and removed airports group by our placeCode —
    FR24's country label never buckets an airport we already know, so FR24
    mislabels (RUE, SMZ, KIA) cannot fabricate diffs. Added airports group by
    FR24's label and, in countries our data subdivides, get a state placeCode
    from the geo lookup.

    Skycards rows with neither IATA nor ICAO are remnants of FR24-deleted
    airports; they are excluded from matching and from counts (equivalent to
    the old IATA-required rule on today's data: no row has ICAO without
    IATA).

    Returns (differences_by_iso, unmapped_added_rows).
    """
    our_rows = [row for row in airports_data.get('rows', [])
                if _has_code(row)]
    # ids are unique in airports.json today; a duplicate would shadow a
    # row here while our_counts counted it — worth a check if that ever
    # changes
    our_by_id = {row['id']: row for row in our_rows}
    mobile_by_id = {row['id']: row for row in mobile_rows
                    if isinstance(row, dict) and isinstance(row.get('id'), int)}

    # Countries whose placeCodes carry subdivisions (currently US CA AU CN).
    subdivided = {(row.get('placeCode') or '').split('-')[0]
                  for row in our_rows if '-' in (row.get('placeCode') or '')}

    our_counts = Counter((row.get('placeCode') or '').split('-')[0]
                         for row in our_rows)

    added: Dict[str, List[Dict]] = {}
    removed: Dict[str, List[Dict]] = {}
    changed: Dict[str, List[Dict]] = {}
    unmapped: List[Dict] = []

    for airport_id, row in mobile_by_id.items():
        ours = our_by_id.get(airport_id)
        if ours is None:
            iso = country_mapping.get(_normalize_country_name(row.get('country', '')))
            if not iso:
                unmapped.append({
                    'name': row.get('name', ''),
                    'iata': (row.get('iata') or '').strip() or None,
                    'icao': (row.get('icao') or '').strip(),
                    'country': row.get('country', ''),
                })
                continue
            place = iso
            if iso in subdivided:
                state = lookup.lookup(row.get('lon'), row.get('lat'), iso)
                if state:
                    place = state
            added.setdefault(iso, []).append(_added_airport_record(row, place))
        else:
            changes = _airport_field_changes(ours, row, ('name', 'iata', 'icao'))
            if changes:
                iso = (ours.get('placeCode') or '').split('-')[0]
                record = _added_airport_record(row, ours.get('placeCode') or iso)
                record['changes'] = changes
                changed.setdefault(iso, []).append(record)

    for airport_id, row in our_by_id.items():
        if airport_id not in mobile_by_id:
            iso = (row.get('placeCode') or '').split('-')[0]
            removed.setdefault(iso, []).append(_our_airport_record(row))

    differences = {}
    for iso in sorted(set(added) | set(removed) | set(changed)):
        iso_added = added.get(iso, [])
        iso_removed = removed.get(iso, [])
        iso_changed = changed.get(iso, [])
        for airports in (iso_added, iso_removed, iso_changed):
            _sort_airports(airports)
        our_count = our_counts.get(iso, 0)
        # By construction the mobile dataset's count for this country is ours
        # minus what it dropped plus what it has that we lack — counts and
        # lists can never disagree.
        fr24_count = our_count - len(iso_removed) + len(iso_added)
        record = _country_record(_country_display_name(iso, country_mapping),
                                 iso, fr24_count, our_count,
                                 iso_added, iso_removed, iso_changed)
        if iso in subdivided:
            breakdown = _states_breakdown(iso, iso_added, iso_removed,
                                          our_rows, lookup)
            if breakdown:
                record['states'] = breakdown
        differences[iso] = record
    return differences, unmapped


def _country_display_name(iso: str, country_mapping: Dict[str, str]) -> str:
    """Reverse-map an ISO code to a display name (first mapping hit)."""
    for name, code in country_mapping.items():
        if code == iso:
            return name
    return iso


def create_country_mapping() -> Dict[str, str]:
    """Create mapping from country names to ISO codes"""
    return {
        # A
        "Afghanistan": "AF",
        "Albania": "AL",
        "Algeria": "DZ",
        "American Samoa": "AS",
        "Angola": "AO",
        "Anguilla": "AI",
        "Antarctica": "AQ",
        "Antigua And Barbuda": "AG",
        "Argentina": "AR",
        "Armenia": "AM",
        "Aruba": "AW",
        "Australia": "AU",
        "Austria": "AT",
        "Azerbaijan": "AZ",

        # B
        "Bahamas": "BS",
        "Bahrain": "BH",
        "Bangladesh": "BD",
        "Barbados": "BB",
        "Belarus": "BY",
        "Belgium": "BE",
        "Belize": "BZ",
        "Benin": "BJ",
        "Bermuda": "BM",
        "Bhutan": "BT",
        "Bolivia": "BO",
        "Bosnia And Herzegovina": "BA",
        "Botswana": "BW",
        "Brazil": "BR",
        "British Virgin Islands": "VG",
        "Brunei": "BN",
        "Bulgaria": "BG",
        "Burkina Faso": "BF",
        "Burma Myanmar": "MM",
        "Myanmar (burma)": "MM",
        "Burundi": "BI",

        # C
        "Cambodia": "KH",
        "Cameroon": "CM",
        "Canada": "CA",
        "Cape Verde": "CV",
        "Cayman Islands": "KY",
        "Central African Republic": "CF",
        "Chad": "TD",
        "Chile": "CL",
        "China": "CN",
        "Colombia": "CO",
        "Comoros": "KM",
        "Congo": "CG",
        "Cook Islands": "CK",
        "Costa Rica": "CR",
        "Cote D'ivoire": "CI",
        "Croatia": "HR",
        "Cuba": "CU",
        "Curacao": "CW",
        "Cyprus": "CY",
        "Czech Republic": "CZ",
        "Czechia": "CZ",

        # D
        "Democratic Republic Of The Congo": "CD",
        "Denmark": "DK",
        "Djibouti": "DJ",
        "Dominica": "DM",
        "Dominican Republic": "DO",

        # E
        "Ecuador": "EC",
        "Egypt": "EG",
        "El Salvador": "SV",
        "Equatorial Guinea": "GQ",
        "Eritrea": "ER",
        "Estonia": "EE",
        "Ethiopia": "ET",

        # F
        "Falkland Islands": "FK",
        "Faroe Islands": "FO",
        "Fiji": "FJ",
        "Finland": "FI",
        "France": "FR",
        "French Guiana": "GF",
        "French Polynesia": "PF",

        # G
        "Gabon": "GA",
        "Gambia": "GM",
        "Georgia": "GE",
        "Germany": "DE",
        "Ghana": "GH",
        "Gibraltar": "GI",
        "Greece": "GR",
        "Greenland": "GL",
        "Grenada": "GD",
        "Guadeloupe": "GP",
        "Guam": "GU",
        "Guatemala": "GT",
        "Guinea": "GN",
        "Guinea-bissau": "GW",
        "Guyana": "GY",

        # H
        "Haiti": "HT",
        "Honduras": "HN",
        "Hong Kong": "HK",
        "Hungary": "HU",

        # I
        "Iceland": "IS",
        "India": "IN",
        "Indonesia": "ID",
        "Iran": "IR",
        "Iraq": "IQ",
        "Ireland": "IE",
        "Israel": "IL",
        "Italy": "IT",

        # J
        "Jamaica": "JM",
        "Japan": "JP",
        "Jordan": "JO",

        # K
        "Kazakhstan": "KZ",
        "Kenya": "KE",
        "Kiribati": "KI",
        "Kuwait": "KW",
        "Kyrgyzstan": "KG",

        # L
        "Laos": "LA",
        "Latvia": "LV",
        "Lebanon": "LB",
        "Lesotho": "LS",
        "Liberia": "LR",
        "Libya": "LY",
        "Liechtenstein": "LI",
        "Lithuania": "LT",
        "Luxembourg": "LU",

        # M
        "Macau": "MO",
        "Macedonia": "MK",
        "North Macedonia": "MK",
        "Madagascar": "MG",
        "Malawi": "MW",
        "Malaysia": "MY",
        "Maldives": "MV",
        "Mali": "ML",
        "Malta": "MT",
        "Marshall Islands": "MH",
        "Martinique": "MQ",
        "Mauritania": "MR",
        "Mauritius": "MU",
        "Mexico": "MX",
        "Micronesia": "FM",
        "Moldova": "MD",
        "Monaco": "MC",
        "Mongolia": "MN",
        "Montenegro": "ME",
        "Montserrat": "MS",
        "Morocco": "MA",
        "Mozambique": "MZ",

        # N
        "Namibia": "NA",
        "Nauru": "NR",
        "Nepal": "NP",
        "Netherlands": "NL",
        "New Caledonia": "NC",
        "New Zealand": "NZ",
        "Nicaragua": "NI",
        "Niger": "NE",
        "Nigeria": "NG",
        "North Korea": "KP",
        "Northern Mariana Islands": "MP",
        "Norway": "NO",

        # O
        "Oman": "OM",

        # P
        "Pakistan": "PK",
        "Palau": "PW",
        "Panama": "PA",
        "Papua New Guinea": "PG",
        "Paraguay": "PY",
        "Peru": "PE",
        "Philippines": "PH",
        "Poland": "PL",
        "Portugal": "PT",
        "Puerto Rico": "PR",

        # Q
        "Qatar": "QA",

        # R
        "Romania": "RO",
        "Russia": "RU",
        "Rwanda": "RW",

        # S
        "Saint Kitts And Nevis": "KN",
        "Saint Lucia": "LC",
        "Saint Vincent And The Grenadines": "VC",
        "Samoa": "WS",
        "San Marino": "SM",
        "Sao Tome And Principe": "ST",
        "Saudi Arabia": "SA",
        "Senegal": "SN",
        "Serbia": "RS",
        "Seychelles": "SC",
        "Sierra Leone": "SL",
        "Singapore": "SG",
        "Slovakia": "SK",
        "Slovenia": "SI",
        "Solomon Islands": "SB",
        "Somalia": "SO",
        "South Africa": "ZA",
        "South Korea": "KR",
        "South Sudan": "SS",
        "Spain": "ES",
        "Sri Lanka": "LK",
        "Sudan": "SD",
        "Suriname": "SR",
        "Swaziland": "SZ",
        "Eswatini": "SZ",
        "Sweden": "SE",
        "Switzerland": "CH",
        "Syria": "SY",

        # T
        "Taiwan": "TW",
        "Tajikistan": "TJ",
        "Tanzania": "TZ",
        "Thailand": "TH",
        "Timor-leste (east Timor)": "TL",
        "Togo": "TG",
        "Tonga": "TO",
        "Trinidad And Tobago": "TT",
        "Tunisia": "TN",
        "Turkey": "TR",
        "Turkmenistan": "TM",
        "Turks And Caicos Islands": "TC",
        "Tuvalu": "TV",

        # U
        "Uganda": "UG",
        "Ukraine": "UA",
        "United Arab Emirates": "AE",
        "United Kingdom": "GB",
        "United States": "US",
        "United States Minor Outlying Islands": "UM",
        "Uruguay": "UY",
        "Uzbekistan": "UZ",

        # V
        "Vanuatu": "VU",
        "Venezuela": "VE",
        "Vietnam": "VN",
        "Virgin Islands British": "VG",
        "Virgin Islands Us": "VI",

        # W
        "Wallis And Futuna": "WF",

        # Y
        "Yemen": "YE",

        # Z
        "Zambia": "ZM",
        "Zimbabwe": "ZW",

        # Additional mappings for territories and variations
        "Cocos (keeling) Islands": "CC",
        "Falkland Islands (malvinas)": "FK",
        "Guernsey": "GG",
        "Isle Of Man": "IM",
        "Ivory Coast": "CI",
        "Jersey": "JE",
        "Kosovo": "XK",
        "Macao": "MO",
        "Mayotte": "YT",
        "Reunion": "RE",
        "Saint Helena": "SH",
        "Saint Pierre And Miquelon": "PM"
    }


def _normalize_country_name(name: str) -> str:
    """Map FR24's UPPERCASE country names onto create_country_mapping() keys.

    The mapping capitalizes each space-separated word and lowercases the rest
    (e.g. "Myanmar (burma)", "Guinea-bissau", "Cocos (keeling) Islands"), so
    str.title() — which also capitalizes after "(" and "-" — would not match.
    """
    return ' '.join(word.capitalize() for word in name.split())


def _fetch_text(url: str, label: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch a FR24 URL with retries. Returns (body_text, error_message)."""
    retry_delays = [10, 15, 20]  # Retry delays in seconds
    last_error = None

    for attempt in range(4):  # 1 initial attempt + 3 retries
        try:
            if attempt == 0:
                print(f"  Fetching {label} from {url}")
            else:
                delay = retry_delays[attempt - 1]
                print(f"  Retry {attempt}/3 for {label} after {delay}s delay...")
                time.sleep(delay)

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode('utf-8'), None

        except Exception as e:
            last_error = str(e)
            print(f"  Error fetching {label} (attempt {attempt + 1}/4): {e}")

    error_msg = f"Failed after 4 attempts. Last error: {last_error}"
    print(f"  ❌ {error_msg}")
    return None, error_msg


def _our_airport_record(airport: Dict) -> Dict:
    """Project one airports.json row to the fields the comparison needs."""
    return {
        'name': airport.get('name', ''),
        'iata': airport.get('iata'),
        'icao': airport.get('icao', ''),
        'placeCode': airport.get('placeCode', ''),
    }


def _airport_field_changes(ours: Dict, fr24: Dict, fields: Tuple[str, ...]) -> Dict:
    """Diff the given fields between our record and FR24's, as
    {field: {'old': ours, 'new': fr24}}. Names compare whitespace-collapsed
    (original values are still reported); other fields treat ''/None as
    equal-empty, so an empty-vs-set value still counts as a change."""
    changes = {}
    for field in fields:
        old, new = ours.get(field), fr24.get(field)
        if field == 'name':
            if ' '.join((old or '').split()) == ' '.join((new or '').split()):
                continue
        elif (old or '') == (new or ''):
            continue
        changes[field] = {'old': old, 'new': new}
    return changes


def _country_record(country_name: str, iso_code: str, fr24_count: int,
                    our_count: int, added: List[Dict], removed: List[Dict],
                    changed: List[Dict]) -> Dict:
    """Assemble one country's difference record."""
    return {
        'country_name': country_name,
        'iso_code': iso_code,
        'fr24_count': fr24_count,
        'skycards_count': our_count,
        'difference': fr24_count - our_count,  # Positive means FR24 has more
        'added_airports': added,   # In FR24 but not in our data
        'removed_airports': removed,  # In our data but not in FR24
        'changed_airports': changed,  # Matched, but with updated fields
        'added_count': len(added),
        'removed_count': len(removed),
        'changed_count': len(changed),
    }


def load_airports_data(airports_file: str) -> Tuple[Dict[str, int], Dict]:
    """Load airports data and return both counts and full data"""
    try:
        with open(airports_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Count by placeCode (which includes country and sometimes region)
        place_counts = Counter()
        for airport in data.get('rows', []):
            iata = airport.get('iata')
            if iata is None or iata == '':
                continue

            place_code = airport.get('placeCode', '')
            if place_code:
                # Extract just the country code (before any hyphen for regions like US-TX)
                country_code = place_code.split('-')[0]
                place_counts[country_code] += 1

        return dict(place_counts), data

    except Exception as e:
        print(f"Error reading airports file: {e}")
        return {}, {}


def main():
    """Main function"""
    print("Starting airport comparison...")

    lookup = state_lookup.load_state_lookup('data/ne_50m_admin_1_states.geojson')

    print("Fetching FR24 mobile airports dataset...")
    mobile_rows = fetch_mobile_airports()
    if mobile_rows is None:
        print("Failed to fetch FR24 mobile airports data")
        sys.exit(1)
    print(f"Fetched {len(mobile_rows)} airports from FR24")

    print("Loading our airports data...")
    our_counts, airports_data = load_airports_data('airports.json')
    if not our_counts:
        print("Failed to read our airports data")
        sys.exit(1)
    print(f"Found {len(our_counts)} countries in our data")

    differences, unmapped = compare_mobile_airports(
        mobile_rows, airports_data, create_country_mapping(), lookup)

    for record in unmapped:
        print(f"⚠️  Unmapped FR24 country {record['country']!r}: "
              f"{record['name']} ({record.get('iata') or record.get('icao')})")

    output_data = {
        'summary': {
            'total_countries_with_differences': len(differences),
            'total_added_airports': sum(d['added_count'] for d in differences.values()),
            'total_removed_airports': sum(d['removed_count'] for d in differences.values()),
            'total_changed_airports': sum(d['changed_count'] for d in differences.values()),
        },
        'countries': differences,
    }
    if unmapped:
        output_data['unmapped'] = unmapped

    output_file = 'airport_differences.json'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Detailed differences saved to {output_file}")
        print(f"📊 Summary:")
        print(f"   • {output_data['summary']['total_countries_with_differences']} countries with differences")
        print(f"   • {output_data['summary']['total_added_airports']} airports added (in FR24 but not in our data)")
        print(f"   • {output_data['summary']['total_removed_airports']} airports removed (in our data but not in FR24)")
        print(f"   • {output_data['summary']['total_changed_airports']} airports changed (matched, but with updated fields)")

        if not differences:
            print("✅ No differences - all countries match!")

    except Exception as e:
        print(f"❌ Error saving differences to file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()