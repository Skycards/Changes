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


if __name__ == "__main__":
    unittest.main()
