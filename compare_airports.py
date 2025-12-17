#!/usr/bin/env python3
"""
Script to compare Flightradar24 airport counts with our airports.json data
"""

import json
import re
import sys
import time
from collections import Counter
from typing import Dict, List, Tuple, Optional
import urllib.request
import urllib.error
from html.parser import HTMLParser


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


class FlightRadar24Parser(HTMLParser):
    """Custom HTML parser for Flightradar24 airport data"""

    def __init__(self):
        super().__init__()
        self.country_counts = {}
        self.in_table_row = False
        self.current_country = None
        self.current_count = None
        self.in_airport_link = False
        self.in_count_span = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'tr':
            self.in_table_row = True
            self.current_country = None
            self.current_count = None

        elif tag == 'a' and self.in_table_row:
            href = attrs_dict.get('href', '')
            if '/data/airports/' in href and href != '/data/airports':
                self.in_airport_link = True
                # Try to get country from data-country attribute
                self.current_country = attrs_dict.get('data-country')
                if not self.current_country:
                    # Extract from title
                    self.current_country = attrs_dict.get('title')

        elif tag == 'span' and self.in_table_row:
            class_attr = attrs_dict.get('class', '')
            if 'gray' in class_attr:
                self.in_count_span = True

    def handle_data(self, data):
        data = data.strip()

        if self.in_airport_link and not self.current_country and data:
            # Fallback: use the link text as country name
            self.current_country = data

        elif self.in_count_span and data:
            # Look for airport count pattern
            count_match = re.search(r'(\d+)\s+airports?', data)
            if count_match:
                self.current_count = int(count_match.group(1))

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_airport_link = False

        elif tag == 'span':
            self.in_count_span = False

        elif tag == 'tr':
            # End of table row - save data if we have both country and count
            if self.current_country and self.current_count is not None:
                self.country_counts[self.current_country.strip()] = self.current_count
            self.in_table_row = False


def scrape_flightradar24() -> Dict[str, int]:
    """Scrape airport counts from Flightradar24"""
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

        # Parse the HTML
        parser = FlightRadar24Parser()
        parser.feed(html_content)

        return parser.country_counts

    except Exception as e:
        print(f"Error scraping Flightradar24: {e}")
        return {}


class CountryAirportParser(HTMLParser):
    """Parser for individual country airport pages from Flightradar24"""

    def __init__(self):
        super().__init__()
        self.airports = []
        self.in_table_row = False
        self.current_airport = {}
        self.in_airport_link = False
        self.capturing_name = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'tr':
            self.in_table_row = True
            self.current_airport = {}

        elif tag == 'a' and self.in_table_row:
            href = attrs_dict.get('href', '')
            if '/data/airports/' in href and href.count('/') >= 4:  # Individual airport page
                self.in_airport_link = True
                self.capturing_name = True

                # Extract data attributes
                self.current_airport['iata'] = attrs_dict.get('data-iata', '')
                self.current_airport['lat'] = attrs_dict.get('data-lat', '')
                self.current_airport['lon'] = attrs_dict.get('data-lon', '')
                self.current_airport['link'] = f"https://www.flightradar24.com{href}" if href.startswith('/') else href
                self.current_airport['title'] = attrs_dict.get('title', '')

    def handle_data(self, data):
        data = data.strip()

        if self.in_airport_link and self.capturing_name and data:
            # Extract airport name and ICAO from text like "Rotterdam The Hague Airport (RTM/EHRD)"
            if self.current_airport.get('title'):
                self.current_airport['name'] = self.current_airport['title']
            else:
                self.current_airport['name'] = data

            # Try to extract ICAO from parentheses
            icao_match = re.search(r'\(([A-Z]{3,4})/([A-Z]{4})\)', data)
            if icao_match:
                self.current_airport['icao'] = icao_match.group(2)
            else:
                # Try alternative format
                icao_match = re.search(r'\(([A-Z]{4})\)', data)
                if icao_match:
                    self.current_airport['icao'] = icao_match.group(1)
                else:
                    self.current_airport['icao'] = ''

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_airport_link = False
            self.capturing_name = False

        elif tag == 'tr':
            # End of table row - save airport if we have required data
            if (self.current_airport.get('name') and
                self.current_airport.get('iata') and
                self.current_airport.get('lat') and
                self.current_airport.get('lon')):

                # Convert lat/lon to float
                try:
                    self.current_airport['lat'] = float(self.current_airport['lat'])
                    self.current_airport['lon'] = float(self.current_airport['lon'])
                    self.airports.append(self.current_airport.copy())
                except (ValueError, TypeError):
                    pass  # Skip if lat/lon conversion fails

            self.in_table_row = False


def fetch_country_airports(country_name: str) -> Tuple[List[Dict], Optional[str]]:
    """Fetch detailed airport data for a specific country from Flightradar24

    Returns:
        Tuple of (airports_list, error_message). If successful, error_message is None.
        If failed after all retries, airports_list is empty and error_message contains the error.
    """
    # Convert country name to URL format (lowercase, replace spaces with dashes)
    country_url = country_name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace("'", '')

    # Handle special cases
    country_url = country_url.replace('&', 'and')

    url = f"https://www.flightradar24.com/data/airports/{country_url}"

    retry_delays = [10, 15, 20]  # Retry delays in seconds
    last_error = None

    for attempt in range(4):  # 1 initial attempt + 3 retries
        try:
            if attempt == 0:
                print(f"  Fetching airports for {country_name} from {url}")
            else:
                delay = retry_delays[attempt - 1]
                print(f"  Retry {attempt}/3 for {country_name} after {delay}s delay...")
                time.sleep(delay)

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                html_content = response.read().decode('utf-8')

            parser = CountryAirportParser()
            parser.feed(html_content)

            print(f"  Found {len(parser.airports)} airports for {country_name}")
            return parser.airports, None

        except Exception as e:
            last_error = str(e)
            print(f"  Error fetching airports for {country_name} (attempt {attempt + 1}/4): {e}")

    # All attempts failed
    error_msg = f"Failed after 4 attempts. Last error: {last_error}"
    print(f"  ❌ {error_msg}")
    return [], error_msg


def get_country_airports_from_our_data(airports_data: Dict, country_code: str) -> List[Dict]:
    """Extract airports for a specific country from our airports.json data"""
    country_airports = []

    for airport in airports_data.get('rows', []):
        place_code = airport.get('placeCode', '')
        if place_code and place_code.split('-')[0] == country_code:
            country_airports.append({
                'name': airport.get('name', ''),
                'iata': airport.get('iata', ''),
                'icao': airport.get('icao', ''),
                'lat': airport.get('lat', 0),
                'lon': airport.get('lon', 0)
            })

    return country_airports


def compare_country_airports(fr24_airports: List[Dict], our_airports: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Compare airport lists and return added/removed airports"""

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

    # Sort both lists by IATA code first, then by name
    cleaned_added_airports.sort(key=lambda airport: (airport.get('iata', ''), airport.get('name', '')))
    removed_airports.sort(key=lambda airport: (airport.get('iata', ''), airport.get('name', '')))

    return cleaned_added_airports, removed_airports


def analyze_country_differences(fr24_counts: Dict[str, int], our_counts: Dict[str, int],
                              country_mapping: Dict[str, str], airports_data: Dict,
                              existing_differences: Optional[Dict] = None) -> Dict:
    """Analyze detailed airport differences for all countries

    Args:
        existing_differences: Optional existing differences data to preserve on fetch failures
    """
    if existing_differences is None:
        existing_differences = {}

    # Build ISO mappings from FR24 data
    fr24_iso_counts = {}
    iso_to_name = {}

    for country_name, count in fr24_counts.items():
        iso_code = country_mapping.get(country_name)
        if iso_code:
            fr24_iso_counts[iso_code] = count
            iso_to_name[iso_code] = country_name

    differences = {}

    # Get ISO codes in the order they appear in the mapping
    mapping_order = list(dict.fromkeys(country_mapping.values()))
    all_iso_codes = set(fr24_iso_counts.keys()) | set(our_counts.keys())

    # Sort by mapping order, then alphabetically for any not in mapping
    all_countries = [iso for iso in mapping_order if iso in all_iso_codes]
    all_countries.extend(sorted(all_iso_codes - set(all_countries)))

    print(f"\nAnalyzing {len(all_countries)} countries...")

    for iso_code in all_countries:
        country_name = iso_to_name.get(iso_code, iso_code)
        fr24_count = fr24_iso_counts.get(iso_code, 0)
        our_count = our_counts.get(iso_code, 0)
        if not country_name or country_name == iso_code:
            print(f"Skipping {iso_code} - no country name mapping")
            continue

        print(f"\nProcessing {country_name} ({iso_code}): FR24={fr24_count}, Ours={our_count}")

        # Fetch FR24 airport data for this country
        fr24_airports, fetch_error = fetch_country_airports(country_name)

        # Get our airport data for this country
        our_airports = get_country_airports_from_our_data(airports_data, iso_code)

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
                continue
        else:
            # Successfully fetched data or no error
            if fr24_airports or our_airports:
                added_airports, removed_airports = compare_country_airports(fr24_airports, our_airports)

                # Only add to differences if there are actual changes
                if added_airports or removed_airports:
                    differences[iso_code] = {
                        'country_name': country_name,
                        'iso_code': iso_code,
                        'fr24_count': fr24_count,
                        'skycards_count': our_count,
                        'difference': fr24_count - our_count,  # Positive means FR24 has more
                        'added_airports': added_airports,  # In FR24 but not in our data
                        'removed_airports': removed_airports,  # In our data but not in FR24
                        'added_count': len(added_airports),
                        'removed_count': len(removed_airports)
                    }

                    print(f"  Added: {len(added_airports)} airports")
                    print(f"  Removed: {len(removed_airports)} airports")
                else:
                    print(f"  No differences")

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

    if differences:
        # Save detailed differences to JSON file

        # Prepare output data with summary and sorted countries
        sorted_countries = dict(sorted(differences.items()))
        output_data = {
            'summary': {
                'total_countries_with_differences': len(differences),
                'total_added_airports': sum(diff['added_count'] for diff in differences.values()),
                'total_removed_airports': sum(diff['removed_count'] for diff in differences.values())
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

        except Exception as e:
            print(f"❌ Error saving differences to file: {e}")
    else:
        print("\n✅ No detailed analysis needed - all countries match!")


if __name__ == "__main__":
    main()