#!/usr/bin/env python3
"""
Script to compare Flightradar24 airport counts with our airports.json data
"""

import json
import sys
import time
from collections import Counter
from typing import Dict, List, Tuple, Optional, Set
import urllib.request
import urllib.error
from html.parser import HTMLParser


# Minimum fraction of a subdivisioned country's airports its state pages must
# cover before we trust them for airport-level detail. FR24 rolls the state
# feature out gradually, so a partially-classified country (e.g. Brazil) can
# have state pages summing to far less than the country total; below this ratio
# we fall back to a count-only diff. Fully-migrated countries (US, CA) sit at
# ~1.0, with small timing skew between the index and country-page fetches.
STATE_COVERAGE_MIN = 0.9

# Airports FR24 lists under the wrong country while Skycards deliberately
# keeps them under the right one. Keyed by IATA code; 'fr24' is the country
# FR24 (wrongly) uses, 'ours' the corrected one. FR24's counts and airport
# lists are remapped to the corrected country so the known misplacement stops
# surfacing as a permanent added/removed pair. Drop an entry once FR24 fixes
# its data — the tell is the patched airport being reported as newly added to
# the corrected country.
FR24_COUNTRY_PATCHES = {
    'RUE': {'fr24': 'CG', 'ours': 'CD'},  # Butembo Rughenda is in DR Congo
}


def _patch_fr24_iso_counts(iso_counts):
    """Move each patched airport's count from FR24's country to the corrected
    one. Skipped when FR24 no longer counts anything under the wrong country,
    so a stale patch can't drive a count negative."""
    for patch in FR24_COUNTRY_PATCHES.values():
        if iso_counts.get(patch['fr24'], 0) > 0:
            iso_counts[patch['fr24']] -= 1
            iso_counts[patch['ours']] = iso_counts.get(patch['ours'], 0) + 1
    return iso_counts


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


class AppDataPageParser(HTMLParser):
    """Extract the Inertia.js `data-page` JSON payload from a FR24 page.

    Flightradar24's /data/airports page is now an Inertia (Vue) app that no
    longer renders a server-side country table. Instead it embeds the full
    page payload as HTML-escaped JSON in `<div id="app" data-page="...">`.
    HTMLParser un-escapes the attribute value for us, leaving plain JSON.
    """

    def __init__(self):
        super().__init__()
        self.data_page = None

    def handle_starttag(self, tag, attrs):
        if tag != 'div' or self.data_page is not None:
            return
        attrs_dict = dict(attrs)
        if attrs_dict.get('id') == 'app' and attrs_dict.get('data-page'):
            self.data_page = attrs_dict['data-page']


def _normalize_country_name(name: str) -> str:
    """Map FR24's UPPERCASE country names onto create_country_mapping() keys.

    The mapping capitalizes each space-separated word and lowercases the rest
    (e.g. "Myanmar (burma)", "Guinea-bissau", "Cocos (keeling) Islands"), so
    str.title() — which also capitalizes after "(" and "-" — would not match.
    """
    return ' '.join(word.capitalize() for word in name.split())


def _extract_data_page(html_content: str) -> Dict:
    """Extract and parse the Inertia `data-page` JSON payload from a FR24 page.

    Raises ValueError if the payload is missing or malformed (e.g. a Cloudflare
    challenge interstitial), so callers can distinguish a failed fetch from a
    genuinely empty result.
    """
    parser = AppDataPageParser()
    parser.feed(html_content)

    if not parser.data_page:
        raise ValueError("could not find Inertia data-page payload")

    try:
        return json.loads(parser.data_page)
    except json.JSONDecodeError as e:
        raise ValueError(f"could not parse data-page JSON: {e}")


def _airports_from_props(props: Dict, state_code: Optional[str] = None) -> List[Dict]:
    """Build clean airport dicts from a `props.airports` list.

    Keeps only {name, iata, icao} (+ optional state); notably drops `total`,
    a live flight-movement count that would otherwise churn the differences file
    on every run. Skips airports with no IATA/ICAO (can't be matched).
    """
    airports = []
    for entry in props.get('airports', []):
        iata = (entry.get('iata') or '').strip()
        icao = (entry.get('icao') or '').strip()
        if not iata and not icao:
            continue
        airport = {'name': entry.get('name', ''), 'iata': iata, 'icao': icao}
        if state_code:
            airport['state'] = state_code
        airports.append(airport)
    return airports


def parse_airports_by_country(html_content: str) -> Dict[str, int]:
    """Parse country -> airport count from the FR24 /data/airports page HTML.

    Returns an empty dict when the payload is missing or malformed (e.g. a
    Cloudflare challenge interstitial), so callers can treat it as a failure
    rather than emitting false "everything removed" differences.
    """
    try:
        payload = _extract_data_page(html_content)
    except ValueError as e:
        print(f"Error reading Flightradar24 airports page: {e}")
        return {}

    by_country = payload.get('props', {}).get('airportsByCountry', [])
    country_counts = {}
    for entry in by_country:
        name = entry.get('name')
        total = entry.get('total')
        if not name or total is None:
            continue
        try:
            country_counts[_normalize_country_name(name)] = int(total)
        except (ValueError, TypeError):
            continue

    return country_counts


def scrape_flightradar24() -> Dict[str, int]:
    """Scrape airport counts per country from Flightradar24"""
    url = "https://www.flightradar24.com/data/airports"

    try:
        # Create request with headers
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )

        # Fetch the page
        with urllib.request.urlopen(req, timeout=30) as response:
            html_content = response.read().decode('utf-8')

        return parse_airports_by_country(html_content)

    except Exception as e:
        print(f"Error scraping Flightradar24: {e}")
        return {}


def parse_country_airports(html_content: str) -> List[Dict]:
    """Parse the flat airport list from a FR24 /data/airports/<country> page.

    Like the airports index, per-country pages are now an Inertia app
    (component "Data/AirportsByCountry" / "Data/AirportsByState"); the airport
    list lives in `props.airports` inside the `data-page` JSON, not an HTML
    table. Raises ValueError if the payload is missing/malformed or has no
    `airports` list (e.g. a Cloudflare challenge, or a country that is split
    into states — see parse_states), so callers treat it as a failed fetch
    instead of an empty "all airports removed" list.
    """
    payload = _extract_data_page(html_content)
    props = payload.get('props', {})
    if 'airports' not in props:
        raise ValueError("country page payload has no 'airports' list")
    return _airports_from_props(props)


def parse_states(html_content: str) -> List[Dict]:
    """Return the subdivision pages for a country, or [] if it isn't split.

    Large countries (US, Canada, Australia, China, ...) no longer list airports
    directly; the country page carries `props.states`, each a
    {code, name, total, url} pointing at a per-state airport page. The `code`
    (e.g. "AL", "AB") matches our placeCode subdivision suffix ("US-AL").
    """
    payload = _extract_data_page(html_content)
    states = []
    for entry in payload.get('props', {}).get('states', []):
        url = entry.get('url')
        if url:
            try:
                total = int(entry.get('total', 0))
            except (ValueError, TypeError):
                total = 0
            states.append({
                'code': entry.get('code', ''),
                'name': entry.get('name', ''),
                'total': total,
                'url': url,
            })
    return states


def _fetch_html(url: str, label: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch a FR24 page with retries. Returns (html, error_message)."""
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


def _country_url(country_name: str) -> str:
    """Build the FR24 /data/airports/<country> URL from a country name."""
    slug = country_name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace("'", '')
    slug = slug.replace('&', 'and')  # handle special cases
    return f"https://www.flightradar24.com/data/airports/{slug}"


def _our_airport_record(airport: Dict) -> Dict:
    """Project one airports.json row to the fields the comparison needs."""
    return {
        'name': airport.get('name', ''),
        'iata': airport.get('iata'),
        'icao': airport.get('icao', ''),
        'placeCode': airport.get('placeCode', ''),
    }


def get_country_airports_from_our_data(airports_data: Dict, country_code: str) -> List[Dict]:
    """Extract airports for a specific country from our airports.json data.

    Keeps the full placeCode (e.g. "US-PA") so downstream rendering can nest
    airports by state/region.
    """
    country_airports = []
    for airport in airports_data.get('rows', []):
        place_code = airport.get('placeCode', '')
        if place_code and place_code.split('-')[0] == country_code:
            iata = airport.get('iata')
            if iata is None or iata == '':
                continue
            country_airports.append(_our_airport_record(airport))
    return country_airports


def get_state_airports_from_our_data(airports_data: Dict, country_code: str,
                                     state_code: str) -> List[Dict]:
    """Extract our airports for one subdivision (placeCode == "US-PA")."""
    target = f"{country_code}-{state_code}"
    state_airports = []
    for airport in airports_data.get('rows', []):
        if airport.get('placeCode', '') != target:
            continue
        iata = airport.get('iata')
        if iata is None or iata == '':
            continue
        state_airports.append(_our_airport_record(airport))
    return state_airports


def get_our_state_counts(airports_data: Dict, country_code: str) -> Dict[str, int]:
    """Our airport counts per subdivision for a country, keyed by state code.

    Mirrors the country-level counting (IATA-less airports excluded) so the
    per-state totals line up with FR24's state totals.
    """
    counts: Dict[str, int] = {}
    prefix = f"{country_code}-"
    for airport in airports_data.get('rows', []):
        place_code = airport.get('placeCode', '')
        if not place_code.startswith(prefix):
            continue
        iata = airport.get('iata')
        if iata is None or iata == '':
            continue
        state_code = place_code.split('-', 1)[1]
        counts[state_code] = counts.get(state_code, 0) + 1
    return counts


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


def _unique_by_code(airports: List[Dict], field: str) -> Dict[str, Dict]:
    """Map each non-empty `field` code to its airport, dropping codes that
    appear more than once (ambiguous: pairing on them could mismatch)."""
    counts = Counter()
    by_code = {}
    for airport in airports:
        code = airport.get(field) or ''
        if code:
            counts[code] += 1
            by_code[code] = airport
    return {code: airport for code, airport in by_code.items() if counts[code] == 1}


def _place_code_change(old: Optional[str], new: Optional[str]) -> Optional[Dict]:
    """placeCode `changes` entry for a Stage-B pair, or None when nothing
    really moved. A bare country on one side with a subdivision of that same
    country on the other is a granularity mismatch between FR24 and our data
    (the flat-fallback comparison paths), not a move."""
    if (old or '') == (new or ''):
        return None
    same_country = (old or '').split('-')[0] == (new or '').split('-')[0]
    if same_country and not ('-' in (old or '') and '-' in (new or '')):
        return None
    return {'old': old, 'new': new}


def _pair_changed(added: List[Dict], removed: List[Dict]) -> Tuple[List[Dict], Set[int]]:
    """Pair added records with removed records that share an ICAO (then, among
    the leftovers, an IATA): an IATA rename or a state move otherwise surfaces
    as an unrelated added+removed pair. Each record pairs at most once. Returns
    (changed_records, paired_ids) where paired_ids holds the id()s of the
    consumed dicts so callers can filter every list (country aggregate and
    per-state breakdown) holding the same objects."""
    changed = []
    paired_ids: Set[int] = set()
    for field in ('icao', 'iata'):
        added_by_code = _unique_by_code(
            [ap for ap in added if id(ap) not in paired_ids], field)
        removed_by_code = _unique_by_code(
            [ap for ap in removed if id(ap) not in paired_ids], field)
        for code in added_by_code.keys() & removed_by_code.keys():
            add, rem = added_by_code[code], removed_by_code[code]
            airport = add.copy()
            airport.pop('title', None)
            airport['changes'] = _airport_field_changes(
                rem, add, ('name', 'iata', 'icao'))
            place_change = _place_code_change(rem.get('placeCode'), add.get('placeCode'))
            if place_change:
                airport['changes']['placeCode'] = place_change
            changed.append(airport)
            paired_ids.update((id(add), id(rem)))
    return changed, paired_ids


def _merge_changed(added: List[Dict], removed: List[Dict],
                   changed: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict], Set[int]]:
    """Fold Stage-B pairs into a country's changed list, dropping the paired
    records from added/removed. Returns the filtered lists, the merged+sorted
    changed list, and the paired id()s (for scrubbing per-state breakdowns)."""
    paired, paired_ids = _pair_changed(added, removed)
    added = [ap for ap in added if id(ap) not in paired_ids]
    removed = [ap for ap in removed if id(ap) not in paired_ids]
    changed = sorted(changed + paired,
                     key=lambda airport: (airport.get('iata', ''), airport.get('name', '')))
    return added, removed, changed, paired_ids


def compare_country_airports(fr24_airports: List[Dict], our_airports: List[Dict],
                             iso_code: Optional[str] = None) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Compare airport lists and return added/removed/changed airports.

    Changed airports are matched by identifier but differ in name/iata/icao
    (Stage A); renames and moves that show up as an added+removed pair are
    handled at the country level by _pair_changed (Stage B).

    With a country context (iso_code, possibly state-qualified like "US-CA"),
    airports in FR24_COUNTRY_PATCHES are dropped from the side whose placement
    in this country is the known-wrong / deliberately-corrected one.
    """
    if iso_code:
        country = iso_code.split('-')[0]
        fr24_airports = [ap for ap in fr24_airports
                         if FR24_COUNTRY_PATCHES.get(ap.get('iata'), {}).get('fr24') != country]
        our_airports = [ap for ap in our_airports
                        if FR24_COUNTRY_PATCHES.get(ap.get('iata'), {}).get('ours') != country]

    # Create sets of airport identifiers for comparison
    # Use IATA as primary identifier, fallback to ICAO if IATA missing
    fr24_identifiers = set()
    our_identifiers = set()

    fr24_by_id = {}
    our_by_id = {}

    # Track airports without identifiers for debugging
    fr24_without_id = 0
    our_without_id = 0

    for airport in fr24_airports:
        identifier = airport.get('iata') or airport.get('icao')
        if identifier:
            fr24_identifiers.add(identifier)
            fr24_by_id[identifier] = airport
        else:
            fr24_without_id += 1

    for airport in our_airports:
        identifier = airport.get('iata') or airport.get('icao')
        if identifier:
            our_identifiers.add(identifier)
            our_by_id[identifier] = airport
        else:
            our_without_id += 1

    # Debug output if there are airports without identifiers
    if fr24_without_id > 0:
        print(f"    Warning: {fr24_without_id} FR24 airports without IATA/ICAO identifiers")
    if our_without_id > 0:
        print(f"    Warning: {our_without_id} Skycards airports without IATA/ICAO identifiers")

    # Find added (in FR24 but not in our data) and removed (in our data but not in FR24)
    added_ids = fr24_identifiers - our_identifiers
    removed_ids = our_identifiers - fr24_identifiers

    # Clean up added airports (remove title field, keep only needed fields)
    cleaned_added_airports = []
    for aid in added_ids:
        if aid in fr24_by_id:
            airport = fr24_by_id[aid].copy()
            # Remove title field if it exists
            airport.pop('title', None)
            cleaned_added_airports.append(airport)

    # Removed airports are already clean (only have needed fields)
    removed_airports = [our_by_id[rid] for rid in removed_ids if rid in our_by_id]

    # Add airports without identifiers to removed list (they can't be matched with FR24)
    for airport in our_airports:
        identifier = airport.get('iata') or airport.get('icao')
        if not identifier:
            # This airport has no identifier, so it's effectively "removed" since we can't match it
            removed_airports.append(airport)

    # Stage A: airports matched by identifier can still differ in the fields
    # we track; surface those as changed records instead of dropping the pair.
    changed_airports = []
    for identifier in fr24_identifiers & our_identifiers:
        changes = _airport_field_changes(our_by_id[identifier], fr24_by_id[identifier],
                                         ('name', 'iata', 'icao'))
        if changes:
            airport = fr24_by_id[identifier].copy()
            airport.pop('title', None)
            # Our record knows the real subdivision even when FR24's side of
            # this comparison is flat; the caller's setdefault won't override.
            if our_by_id[identifier].get('placeCode'):
                airport['placeCode'] = our_by_id[identifier]['placeCode']
            airport['changes'] = changes
            changed_airports.append(airport)

    # Sort all lists by IATA code first, then by name
    cleaned_added_airports.sort(key=lambda airport: (airport.get('iata', ''), airport.get('name', '')))
    removed_airports.sort(key=lambda airport: (airport.get('iata', ''), airport.get('name', '')))
    changed_airports.sort(key=lambda airport: (airport.get('iata', ''), airport.get('name', '')))

    return cleaned_added_airports, removed_airports, changed_airports


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


def _diff_flat_country(iso_code: str, country_name: str, fr24_count: int,
                       our_count: int, html: str, airports_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """Compare a flat country (airports listed directly on its page)."""
    try:
        fr24_airports = parse_country_airports(html)
    except ValueError as e:
        return None, str(e)
    our_airports = get_country_airports_from_our_data(airports_data, iso_code)
    added, removed, changed = compare_country_airports(fr24_airports, our_airports, iso_code)
    for ap in added + changed:  # tag FR24 records with the country placeCode
        ap.setdefault('placeCode', iso_code)
    added, removed, changed, _ = _merge_changed(added, removed, changed)
    print(f"  Added: {len(added)}, Removed: {len(removed)}, Changed: {len(changed)}")
    return _country_record(country_name, iso_code, fr24_count, our_count,
                           added, removed, changed), None


def _fetch_all_state_airports(country_name: str, states: List[Dict]) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """Fetch and aggregate airports from every state page (state-tagged)."""
    airports = []
    for state in states:
        state_url = f"https://www.flightradar24.com{state['url']}"
        state_html, error = _fetch_html(state_url, f"{country_name} / {state['name']} ({state['code']})")
        if error:
            return None, f"state {state['code']} fetch failed: {error}"
        try:
            airports.extend(_airports_from_props(
                _extract_data_page(state_html).get('props', {}), state_code=state['code']))
        except ValueError as e:
            return None, f"state {state['code']} parse failed: {e}"
        time.sleep(2)  # be polite between state fetches
    return airports, None


def _diff_states_as_flat(iso_code: str, country_name: str, fr24_count: int,
                         our_count: int, states: List[Dict],
                         airports_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """Fallback when FR24 splits a country into states but our data doesn't.

    We can't gate per state (our data has no per-state counts to compare), so
    fetch every state page, aggregate, and compare at the country level — where
    placeCodes line up. FR24-added airports still carry their state placeCode so
    the message nests them; our (un-subdivided) airports compare by country.
    """
    fr24_airports, error = _fetch_all_state_airports(country_name, states)
    if error:
        return None, error
    our_airports = get_country_airports_from_our_data(airports_data, iso_code)
    added, removed, changed = compare_country_airports(fr24_airports, our_airports, iso_code)
    for ap in added + changed:
        ap.setdefault('placeCode', f"{iso_code}-{ap['state']}" if ap.get('state') else iso_code)
    added, removed, changed, _ = _merge_changed(added, removed, changed)
    print(f"  (our data not subdivided) Added: {len(added)}, Removed: {len(removed)}, "
          f"Changed: {len(changed)}")
    return _country_record(country_name, iso_code, fr24_count, our_count,
                           added, removed, changed), None


def _diff_subdivisioned_country(iso_code: str, country_name: str, fr24_count: int,
                                our_count: int, states: List[Dict],
                                airports_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """Compare a subdivisioned country (US, Canada, ...) state by state.

    FR24's country page already carries each state's total, and our data has
    per-state counts (placeCode "US-PA"), so we only fetch the state pages
    whose counts actually differ — mirroring the country-level count gate.
    """
    # FR24 rolls the state feature out gradually, so a freshly-split country can
    # have many airports not yet assigned to any state — the state pages then
    # enumerate only a fraction of the country total and every unreachable
    # airport would look "removed". If coverage is well short of the country
    # total, skip airport-level detail and emit a count-only record instead.
    state_total = sum(int(s.get('total', 0)) for s in states)
    if fr24_count and state_total < fr24_count * STATE_COVERAGE_MIN:
        pct = round(state_total / fr24_count * 100)
        coverage = f"{state_total}/{fr24_count} ({pct}%)"
        print(f"  ⚠️  Incomplete state coverage for {country_name}: {coverage}; "
              f"count-only (no detail)")
        record = _country_record(country_name, iso_code, fr24_count, our_count, [], [], [])
        record['state_coverage'] = coverage
        return record, None

    our_state_counts = get_our_state_counts(airports_data, iso_code)
    if not our_state_counts:
        # FR24 subdivides this country but our data doesn't yet (or we have no
        # airports there). Per-state matching would falsely flag everything as
        # added, so fall back to a country-level comparison.
        return _diff_states_as_flat(iso_code, country_name, fr24_count,
                                    our_count, states, airports_data)

    fr24_by_code = {s['code']: s for s in states}

    diff_states = [code for code in sorted(set(fr24_by_code) | set(our_state_counts))
                   if int(fr24_by_code.get(code, {}).get('total', 0)) != our_state_counts.get(code, 0)]
    print(f"  {len(states)} states, {len(diff_states)} with count differences: {', '.join(diff_states) or '—'}")

    all_added, all_removed, all_changed = [], [], []
    states_breakdown = {}
    for code in diff_states:
        state = fr24_by_code.get(code)
        if state:  # state present on FR24 -> fetch its airports
            state_url = f"https://www.flightradar24.com{state['url']}"
            state_html, state_error = _fetch_html(state_url, f"{country_name} / {state['name']} ({code})")
            if state_error:
                # Abort the whole country on any state failure — a partial list
                # would look like a mass removal downstream.
                return None, f"state {code} fetch failed: {state_error}"
            try:
                fr24_state_airports = _airports_from_props(
                    _extract_data_page(state_html).get('props', {}), state_code=code)
            except ValueError as e:
                return None, f"state {code} parse failed: {e}"
            time.sleep(2)  # be polite between state fetches
        else:  # state gone from FR24 -> everything we have there is "removed"
            fr24_state_airports = []

        our_state_airports = get_state_airports_from_our_data(airports_data, iso_code, code)
        added, removed, state_changed = compare_country_airports(
            fr24_state_airports, our_state_airports, iso_code)
        for ap in added + state_changed:
            ap.setdefault('placeCode', f"{iso_code}-{code}")
        all_added.extend(added)
        all_removed.extend(removed)
        all_changed.extend(state_changed)

        fr24_state_count = int(state['total']) if state else 0
        states_breakdown[code] = {
            'state_name': state['name'] if state else code,
            'fr24_count': fr24_state_count,
            'skycards_count': our_state_counts.get(code, 0),
            'difference': fr24_state_count - our_state_counts.get(code, 0),
            'added_airports': added,
            'removed_airports': removed,
            'added_count': len(added),
            'removed_count': len(removed),
        }

    # Stage B runs on the country aggregate: a state move is a removal in one
    # state plus an addition in another, invisible to the per-state diffs.
    all_added, all_removed, all_changed, paired_ids = _merge_changed(
        all_added, all_removed, all_changed)
    if paired_ids:  # scrub paired records out of the per-state breakdown too
        for entry in states_breakdown.values():
            entry['added_airports'] = [ap for ap in entry['added_airports']
                                       if id(ap) not in paired_ids]
            entry['removed_airports'] = [ap for ap in entry['removed_airports']
                                         if id(ap) not in paired_ids]
            entry['added_count'] = len(entry['added_airports'])
            entry['removed_count'] = len(entry['removed_airports'])

    record = _country_record(country_name, iso_code, fr24_count, our_count,
                             all_added, all_removed, all_changed)
    record['states'] = states_breakdown
    print(f"  Added: {len(all_added)}, Removed: {len(all_removed)}, "
          f"Changed: {len(all_changed)} across {len(diff_states)} states")
    return record, None


def _diff_one_country(iso_code: str, country_name: str, fr24_count: int,
                      our_count: int, airports_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """Fetch a country's page and compare it, handling flat and state splits."""
    html, error = _fetch_html(_country_url(country_name), country_name)
    if error:
        return None, error
    try:
        states = parse_states(html)
    except ValueError as e:
        return None, str(e)
    if states:
        return _diff_subdivisioned_country(iso_code, country_name, fr24_count,
                                           our_count, states, airports_data)
    return _diff_flat_country(iso_code, country_name, fr24_count, our_count, html, airports_data)


def analyze_country_differences(fr24_counts: Dict[str, int], our_counts: Dict[str, int],
                              country_mapping: Dict[str, str], airports_data: Dict,
                              existing_differences: Optional[Dict] = None) -> Dict:
    """Analyze detailed differences for countries with mismatched airport counts

    Args:
        existing_differences: Optional existing differences data to preserve on fetch failures
    """
    if existing_differences is None:
        existing_differences = {}

    # Find countries with differences
    fr24_iso_counts = {}
    iso_to_name = {}

    for country_name, count in fr24_counts.items():
        iso_code = country_mapping.get(country_name)
        if iso_code:
            fr24_iso_counts[iso_code] = count
            iso_to_name[iso_code] = country_name

    _patch_fr24_iso_counts(fr24_iso_counts)

    differences = {}
    countries_with_diffs = []

    # Find countries that have different counts
    for iso_code in set(fr24_iso_counts.keys()) | set(our_counts.keys()):
        fr24_count = fr24_iso_counts.get(iso_code, 0)
        our_count = our_counts.get(iso_code, 0)

        if fr24_count != our_count:
            countries_with_diffs.append((iso_code, iso_to_name.get(iso_code, iso_code), fr24_count, our_count))

    print(f"\nAnalyzing detailed differences for {len(countries_with_diffs)} countries...")

    for iso_code, country_name, fr24_count, our_count in countries_with_diffs:
        if not country_name or country_name == iso_code:
            print(f"Skipping {iso_code} - no country name mapping")
            continue

        print(f"\nProcessing {country_name} ({iso_code}): FR24={fr24_count}, Ours={our_count}")

        record, fetch_error = _diff_one_country(iso_code, country_name, fr24_count,
                                                our_count, airports_data)

        if fetch_error:
            # Failed to fetch new data
            if iso_code in existing_differences:
                # Preserve existing data - straight copy
                print(f"  ⚠️  Fetch failed, preserving existing data for {country_name}")
                differences[iso_code] = existing_differences[iso_code].copy()
                differences[iso_code]['fetch_error'] = fetch_error
            else:
                # No existing data and failed to fetch - skip this country
                print(f"  ⚠️  Fetch failed and no existing data - skipping {country_name}")
        elif record is not None:
            differences[iso_code] = record

        # Add delay to be respectful to the server and avoid 429 errors
        time.sleep(5)

    return differences


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


def count_airports_by_country(airports_file: str) -> Dict[str, int]:
    """Count airports by country in our airports.json file - backward compatibility"""
    counts, _ = load_airports_data(airports_file)
    return counts


def compare_counts(fr24_counts: Dict[str, int], our_counts: Dict[str, int], country_mapping: Dict[str, str]) -> None:
    """Compare airport counts between Flightradar24 and our data"""

    print("=== AIRPORT COUNT COMPARISON ===\n")

    # Convert FR24 country names to ISO codes for comparison
    fr24_iso_counts = {}
    for country_name, count in fr24_counts.items():
        iso_code = country_mapping.get(country_name)
        if iso_code:
            fr24_iso_counts[iso_code] = count
        else:
            print(f"⚠️  Unknown country mapping: '{country_name}' -> Need to add to mapping")

    _patch_fr24_iso_counts(fr24_iso_counts)

    # Find all unique countries
    all_countries = set(fr24_iso_counts.keys()) | set(our_counts.keys())

    matches = 0
    differences = 0

    for country in sorted(all_countries):
        fr24_count = fr24_iso_counts.get(country, 0)
        our_count = our_counts.get(country, 0)

        if fr24_count == our_count:
            if fr24_count > 0:  # Only show countries with airports
                print(f"✅ {country}: {our_count} airports (match)")
                matches += 1
        else:
            print(f"❌ {country}: FR24={fr24_count}, Ours={our_count} (diff: {fr24_count - our_count:+d})")
            differences += 1

    print(f"\n=== SUMMARY ===")
    print(f"Countries with matching counts: {matches}")
    print(f"Countries with different counts: {differences}")
    print(f"Total countries compared: {len(all_countries)}")

    # Show countries only in one dataset
    only_fr24 = set(fr24_iso_counts.keys()) - set(our_counts.keys())
    only_ours = set(our_counts.keys()) - set(fr24_iso_counts.keys())

    if only_fr24:
        print(f"\nCountries only in Flightradar24: {', '.join(sorted(only_fr24))}")

    if only_ours:
        print(f"Countries only in our data: {', '.join(sorted(only_ours))}")


def main():
    """Main function"""
    print("Starting airport comparison...")

    # Get country mapping
    country_mapping = create_country_mapping()

    # Scrape Flightradar24 data
    print("Scraping Flightradar24...")
    fr24_counts = scrape_flightradar24()

    if not fr24_counts:
        print("Failed to scrape Flightradar24 data")
        sys.exit(1)

    print(f"Found {len(fr24_counts)} countries on Flightradar24")

    # Load our airports data
    print("Loading our airports data...")
    our_counts, airports_data = load_airports_data('airports.json')

    if not our_counts:
        print("Failed to read our airports data")
        sys.exit(1)

    print(f"Found {len(our_counts)} countries in our data")

    # Compare counts
    compare_counts(fr24_counts, our_counts, country_mapping)

    # Analyze detailed differences
    print("\n" + "="*50)
    print("DETAILED ANALYSIS")
    print("="*50)

    # Load existing differences data if it exists
    existing_differences = {}
    output_file = 'airport_differences.json'
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_differences = existing_data.get('countries', {})
        print(f"Loaded existing differences data for {len(existing_differences)} countries")
    except FileNotFoundError:
        print("No existing differences file found - starting fresh")
    except Exception as e:
        print(f"Warning: Could not load existing differences file: {e}")

    differences = analyze_country_differences(fr24_counts, our_counts, country_mapping, airports_data, existing_differences)

    # Save differences output even when there are no mismatches so downstream
    # consumers always get a consistent JSON structure.
    sorted_countries = dict(sorted(differences.items()))
    output_data = {
        'summary': {
            'total_countries_with_differences': len(differences),
            'total_added_airports': sum(diff['added_count'] for diff in differences.values()),
            'total_removed_airports': sum(diff['removed_count'] for diff in differences.values()),
            # .get(): records preserved from an older differences file on fetch
            # failure may predate changed_count.
            'total_changed_airports': sum(diff.get('changed_count', 0) for diff in differences.values())
        },
        'countries': sorted_countries
    }

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
            print("✅ No detailed analysis needed - all countries match!")

    except Exception as e:
        print(f"❌ Error saving differences to file: {e}")


if __name__ == "__main__":
    main()