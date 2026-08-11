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
        # No data-page payload -> raise so the caller treats it as a failed
        # fetch (retry / preserve existing data) instead of "0 airports".
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


def _rows(*airports):
    return {"rows": list(airports)}


class OurDataHelpersTest(unittest.TestCase):
    def test_country_airports_keep_placecode_skip_iataless(self):
        data = _rows(
            {"name": "A", "iata": "AAA", "icao": "KAAA", "placeCode": "US-CA"},
            {"name": "No IATA", "iata": "", "icao": "KZZZ", "placeCode": "US-CA"},
            {"name": "Other", "iata": "BBB", "icao": "KBBB", "placeCode": "GB"},
        )
        got = ca.get_country_airports_from_our_data(data, "US")
        self.assertEqual([a["iata"] for a in got], ["AAA"])
        self.assertEqual(got[0]["placeCode"], "US-CA")

    def test_state_airports_filter_exact_placecode(self):
        data = _rows(
            {"name": "A", "iata": "AAA", "placeCode": "US-CA"},
            {"name": "B", "iata": "BBB", "placeCode": "US-TX"},
        )
        got = ca.get_state_airports_from_our_data(data, "US", "CA")
        self.assertEqual([a["iata"] for a in got], ["AAA"])

    def test_our_state_counts_group_by_subdivision(self):
        data = _rows(
            {"iata": "AAA", "placeCode": "US-CA"},
            {"iata": "BBB", "placeCode": "US-CA"},
            {"iata": "CCC", "placeCode": "US-TX"},
            {"iata": "", "placeCode": "US-TX"},   # iata-less: excluded
            {"iata": "DDD", "placeCode": "CA-ON"},  # other country
        )
        self.assertEqual(ca.get_our_state_counts(data, "US"), {"CA": 2, "TX": 1})


class DiffOneCountryTest(unittest.TestCase):
    """Exercise flat/subdivisioned analysis with _fetch_html mocked."""

    def _run(self, country_name, iso, fr24_count, our_count, pages, airports_data):
        calls = []

        def fake_fetch(url, label):
            calls.append(url)
            # Suffix match: the country key is a prefix of the state URLs, so a
            # plain substring test would shadow them. Path suffixes are unique.
            for key, html in pages.items():
                if url.endswith(key):
                    return html, None
            return None, f"no stub for {url}"

        orig_fetch, orig_sleep = ca._fetch_html, ca.time.sleep
        ca._fetch_html = fake_fetch
        ca.time.sleep = lambda *a, **k: None
        try:
            rec, err = ca._diff_one_country(iso, country_name, fr24_count, our_count, airports_data)
            return rec, err, calls
        finally:
            ca._fetch_html = orig_fetch
            ca.time.sleep = orig_sleep

    def test_flat_country_tags_country_placecode(self):
        pages = {"/netherlands": _country_page_html([
            {"name": "New", "iata": "NEW", "icao": "EHNW"},
        ])}
        our = _rows({"name": "Old", "iata": "OLD", "icao": "EHOL", "placeCode": "NL"})
        rec, err, calls = self._run("Netherlands", "NL", 1, 1, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"][0]["placeCode"], "NL")
        self.assertEqual(rec["removed_airports"][0]["iata"], "OLD")
        self.assertNotIn("states", rec)
        self.assertEqual(len(calls), 1)  # flat: only the country page

    def test_subdivisioned_only_fetches_changed_states(self):
        pages = {
            "/data/airports/united-states": _states_page_html([
                {"code": "CA", "name": "California", "total": 3, "url": "/data/airports/united-states/ca"},
                {"code": "TX", "name": "Texas", "total": 2, "url": "/data/airports/united-states/tx"},
            ]),
            # Only CA differs (FR24 3 vs our 2); TX matches (2 == 2) -> not fetched
            "/united-states/ca": _country_page_html([
                {"name": "LA", "iata": "LAX", "icao": "KLAX"},
                {"name": "SF", "iata": "SFO", "icao": "KSFO"},
                {"name": "San Diego", "iata": "SAN", "icao": "KSAN"},
            ]),
        }
        our = _rows(
            {"name": "LA", "iata": "LAX", "placeCode": "US-CA"},
            {"name": "SF", "iata": "SFO", "placeCode": "US-CA"},
            {"name": "Dallas", "iata": "DFW", "placeCode": "US-TX"},
            {"name": "Houston", "iata": "IAH", "placeCode": "US-TX"},
        )
        rec, err, calls = self._run("United States", "US", 5, 4, pages, our)
        self.assertIsNone(err)
        # Only SAN is new; tagged with the state placeCode
        self.assertEqual([a["iata"] for a in rec["added_airports"]], ["SAN"])
        self.assertEqual(rec["added_airports"][0]["placeCode"], "US-CA")
        self.assertEqual(rec["removed_airports"], [])
        # states breakdown present, only for the changed state
        self.assertEqual(set(rec["states"]), {"CA"})
        self.assertEqual(rec["states"]["CA"]["added_count"], 1)
        # country page + only the CA state page (TX skipped)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(c.endswith("/tx") for c in calls))

    def test_state_present_in_our_data_but_absent_on_fr24(self):
        # A subdivision FR24 dropped entirely: no page to fetch, everything ours
        # there becomes "removed".
        pages = {
            "/data/airports/united-states": _states_page_html([
                {"code": "CA", "name": "California", "total": 1, "url": "/data/airports/united-states/ca"},
            ]),
            "/united-states/ca": _country_page_html([
                {"name": "LA", "iata": "LAX", "icao": "KLAX"},
            ]),
        }
        our = _rows(
            {"name": "LA", "iata": "LAX", "placeCode": "US-CA"},
            {"name": "Honolulu", "iata": "HNL", "placeCode": "US-HI"},  # HI not on FR24
        )
        rec, err, calls = self._run("United States", "US", 1, 2, pages, our)
        self.assertIsNone(err)
        self.assertEqual([a["iata"] for a in rec["removed_airports"]], ["HNL"])
        self.assertIn("HI", rec["states"])
        # HI has no FR24 page, so it is never fetched
        self.assertFalse(any(c.endswith("/hi") for c in calls))

    def test_state_fetch_failure_aborts_whole_country(self):
        pages = {
            "/data/airports/united-states": _states_page_html([
                {"code": "CA", "name": "California", "total": 9, "url": "/data/airports/united-states/ca"},
            ]),
            # no stub for /ca -> fetch fails -> whole country aborts
        }
        our = _rows({"name": "LA", "iata": "LAX", "placeCode": "US-CA"})
        rec, err, _ = self._run("United States", "US", 9, 1, pages, our)
        self.assertIsNone(rec)
        self.assertIsNotNone(err)


if __name__ == "__main__":
    unittest.main()
