import json
import os
import sys
import unittest
from html import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import compare_airports as ca


def _page_html(props):
    """Wrap an Inertia props payload the way FR24 serves it: a JSON blob
    HTML-escaped into the `data-page` attribute of `<div id="app">`."""
    payload = {"component": "Data/Airports", "props": props, "url": "/data/airports"}
    attr = escape(json.dumps(payload), quote=True)
    return f'<!doctype html><html><body><div id="app" data-page="{attr}"></div></body></html>'


class ParseAirportsByCountryTest(unittest.TestCase):
    def test_parses_counts_from_data_page(self):
        html = _page_html({
            "airportsByCountry": [
                {"id": "163", "name": "NETHERLANDS", "total": "17"},
                {"id": "236", "name": "UNITED STATES", "total": "1500"},
            ]
        })
        counts = ca.parse_airports_by_country(html)
        self.assertEqual(counts["Netherlands"], 17)
        self.assertEqual(counts["United States"], 1500)

    def test_normalizes_names_to_mapping_keys(self):
        # FR24 serves UPPERCASE names; every normalized name must resolve to an
        # ISO code via create_country_mapping(), including parenthesised/hyphenated
        # edge cases that plain str.title() would mis-case.
        mapping = ca.create_country_mapping()
        html = _page_html({
            "airportsByCountry": [
                {"name": "MYANMAR (BURMA)", "total": "5"},
                {"name": "GUINEA-BISSAU", "total": "1"},
                {"name": "COCOS (KEELING) ISLANDS", "total": "1"},
                {"name": "FALKLAND ISLANDS (MALVINAS)", "total": "2"},
                {"name": "TIMOR-LESTE (EAST TIMOR)", "total": "3"},
            ]
        })
        counts = ca.parse_airports_by_country(html)
        for name in counts:
            self.assertIn(name, mapping, f"{name!r} not in country mapping")

    def test_returns_empty_on_cloudflare_challenge(self):
        # A Cloudflare "Just a moment..." interstitial has no data-page payload;
        # an empty result lets main() abort instead of emitting false diffs.
        html = "<html><head><title>Just a moment...</title></head><body></body></html>"
        self.assertEqual(ca.parse_airports_by_country(html), {})

    def test_returns_empty_on_malformed_payload(self):
        html = '<div id="app" data-page="not json"></div>'
        self.assertEqual(ca.parse_airports_by_country(html), {})

    def test_skips_entries_without_name_or_total(self):
        html = _page_html({
            "airportsByCountry": [
                {"name": "FRANCE", "total": "50"},
                {"name": "", "total": "9"},
                {"id": "1"},
            ]
        })
        counts = ca.parse_airports_by_country(html)
        self.assertEqual(counts, {"France": 50})


def _country_page_html(airports):
    """Wrap a per-country Inertia payload the way FR24 serves it now."""
    payload = {
        "component": "Data/AirportsByCountry",
        "props": {"country": {"name": "Netherlands", "slug": "netherlands"},
                  "airports": airports},
        "url": "/data/airports/netherlands",
    }
    attr = escape(json.dumps(payload), quote=True)
    return f'<!doctype html><html><body><div id="app" data-page="{attr}"></div></body></html>'


class ParseCountryAirportsTest(unittest.TestCase):
    def test_parses_airport_list_from_data_page(self):
        html = _country_page_html([
            {"id": 141, "name": "Amsterdam Schiphol Airport", "city": "Amsterdam",
             "iata": "AMS", "icao": "EHAM", "total": 11464},
            {"id": 142, "name": "Rotterdam The Hague Airport", "city": "Rotterdam",
             "iata": "RTM", "icao": "EHRD", "total": 321},
        ])
        airports = ca.parse_country_airports(html)
        self.assertEqual(len(airports), 2)
        self.assertEqual(airports[0]["iata"], "AMS")
        self.assertEqual(airports[0]["icao"], "EHAM")
        self.assertEqual(airports[0]["name"], "Amsterdam Schiphol Airport")

    def test_excludes_volatile_total_field(self):
        # `total` is a live flight-movement count that changes every scrape;
        # storing it would churn airport_differences.json and spam false diffs.
        html = _country_page_html([
            {"name": "Amsterdam Schiphol Airport", "iata": "AMS", "icao": "EHAM",
             "total": 11464},
        ])
        airports = ca.parse_country_airports(html)
        self.assertNotIn("total", airports[0])

    def test_keeps_airport_when_iata_missing_but_icao_present(self):
        html = _country_page_html([
            {"name": "Some Airfield", "iata": "", "icao": "EHXX"},
        ])
        airports = ca.parse_country_airports(html)
        self.assertEqual(len(airports), 1)
        self.assertEqual(airports[0]["icao"], "EHXX")

    def test_skips_airport_without_any_identifier(self):
        html = _country_page_html([
            {"name": "No Codes Field", "iata": "", "icao": ""},
            {"name": "Good", "iata": "AMS", "icao": "EHAM"},
        ])
        airports = ca.parse_country_airports(html)
        self.assertEqual([a["iata"] for a in airports], ["AMS"])

    def test_raises_on_cloudflare_challenge(self):
        # No data-page payload -> raise so fetch_country_airports treats it as a
        # failed fetch (retry / preserve existing data) instead of "0 airports".
        html = "<html><head><title>Just a moment...</title></head><body></body></html>"
        with self.assertRaises(ValueError):
            ca.parse_country_airports(html)

    def test_raises_on_malformed_payload(self):
        with self.assertRaises(ValueError):
            ca.parse_country_airports('<div id="app" data-page="not json"></div>')

    def test_flat_country_has_no_states(self):
        html = _country_page_html([{"name": "X", "iata": "AMS", "icao": "EHAM"}])
        self.assertEqual(ca.parse_states(html), [])


def _states_page_html(states):
    """Subdivisioned country page: props.states instead of props.airports."""
    payload = {
        "component": "Data/AirportsByCountry",
        "props": {"country": {"name": "United States", "slug": "united-states"},
                  "states": states},
        "url": "/data/airports/united-states",
    }
    attr = escape(json.dumps(payload), quote=True)
    return f'<!doctype html><html><body><div id="app" data-page="{attr}"></div></body></html>'


class ParseStatesTest(unittest.TestCase):
    def test_parses_state_list(self):
        html = _states_page_html([
            {"code": "AL", "name": "Alabama", "total": 29, "url": "/data/airports/united-states/al"},
            {"code": "AK", "name": "Alaska", "total": 185, "url": "/data/airports/united-states/ak"},
        ])
        states = ca.parse_states(html)
        self.assertEqual(len(states), 2)
        self.assertEqual(states[0]["code"], "AL")
        self.assertEqual(states[0]["url"], "/data/airports/united-states/al")

    def test_skips_states_without_url(self):
        html = _states_page_html([
            {"code": "AL", "name": "Alabama", "url": "/data/airports/united-states/al"},
            {"code": "XX", "name": "Broken"},
        ])
        self.assertEqual([s["code"] for s in ca.parse_states(html)], ["AL"])


class FetchCountryAirportsTest(unittest.TestCase):
    """Exercise the flat/subdivisioned orchestration with _fetch_html mocked."""

    def _run_with_pages(self, pages):
        """pages: dict of url-substring -> html. Patches _fetch_html + sleep."""
        calls = []

        def fake_fetch(url, label):
            calls.append(url)
            # Suffix match: the country key is a *prefix* of the state URLs, so
            # a plain substring test would shadow them. Path suffixes are unique.
            for key, html in pages.items():
                if url.endswith(key):
                    return html, None
            return None, f"no stub for {url}"

        orig_fetch, orig_sleep = ca._fetch_html, ca.time.sleep
        ca._fetch_html = fake_fetch
        ca.time.sleep = lambda *a, **k: None
        try:
            return ca.fetch_country_airports("United States"), calls
        finally:
            ca._fetch_html = orig_fetch
            ca.time.sleep = orig_sleep

    def test_flat_country_returns_airports(self):
        pages = {"/united-states": _country_page_html([
            {"name": "A", "iata": "AAA", "icao": "KAAA"},
        ])}
        (airports, error), _ = self._run_with_pages(pages)
        self.assertIsNone(error)
        self.assertEqual(airports[0]["iata"], "AAA")

    def test_subdivisioned_country_aggregates_and_tags_state(self):
        pages = {
            # country page lists states (no airports) -> fetch each state
            "/data/airports/united-states": _states_page_html([
                {"code": "AL", "name": "Alabama", "url": "/data/airports/united-states/al"},
                {"code": "AK", "name": "Alaska", "url": "/data/airports/united-states/ak"},
            ]),
            "/united-states/al": _country_page_html([
                {"name": "Alexander City", "iata": "ALX", "icao": "KALX"},
            ]),
            "/united-states/ak": _country_page_html([
                {"name": "Anchorage", "iata": "ANC", "icao": "PANC"},
                {"name": "Fairbanks", "iata": "FAI", "icao": "PAFA"},
            ]),
        }
        (airports, error), calls = self._run_with_pages(pages)
        self.assertIsNone(error)
        self.assertEqual(len(airports), 3)
        by_iata = {a["iata"]: a for a in airports}
        self.assertEqual(by_iata["ALX"]["state"], "AL")
        self.assertEqual(by_iata["ANC"]["state"], "AK")
        # country page + 2 state pages
        self.assertEqual(len(calls), 3)

    def test_state_fetch_failure_aborts_whole_country(self):
        pages = {
            "/data/airports/united-states": _states_page_html([
                {"code": "AL", "name": "Alabama", "url": "/data/airports/united-states/al"},
                {"code": "AK", "name": "Alaska", "url": "/data/airports/united-states/ak"},
            ]),
            "/united-states/al": _country_page_html([
                {"name": "Alexander City", "iata": "ALX", "icao": "KALX"},
            ]),
            # no stub for /ak -> fetch fails -> whole country aborts
        }
        (airports, error), _ = self._run_with_pages(pages)
        self.assertEqual(airports, [])
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
