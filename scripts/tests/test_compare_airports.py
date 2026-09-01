import json
import os
import sys
import tempfile
import unittest
from html import escape
from unittest import mock

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
    """Exercise flat/subdivisioned analysis with _fetch_text mocked."""

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

        orig_fetch, orig_sleep = ca._fetch_text, ca.time.sleep
        ca._fetch_text = fake_fetch
        ca.time.sleep = lambda *a, **k: None
        try:
            rec, err = ca._diff_one_country(iso, country_name, fr24_count, our_count, airports_data)
            return rec, err, calls
        finally:
            ca._fetch_text = orig_fetch
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

    def test_incomplete_state_coverage_is_count_only(self):
        # FR24 freshly split Brazil: 2 states summing to 3 airports, but the
        # country total is 283 (most airports not yet assigned to a state).
        # Must NOT fetch state pages or report the ~280 unreachable ones as
        # removed — emit a count-only record instead.
        pages = {
            "/data/airports/brazil": _states_page_html([
                {"code": "AC", "name": "Acre", "total": 2, "url": "/data/airports/brazil/ac"},
                {"code": "AL", "name": "Alagoas", "total": 1, "url": "/data/airports/brazil/al"},
            ]),
        }
        our = _rows(*[{"name": f"A{i}", "iata": f"A{i:02d}", "placeCode": "BR"}
                      for i in range(282)])
        rec, err, calls = self._run("Brazil", "BR", 283, 282, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])
        self.assertEqual(rec["changed_airports"], [])
        self.assertEqual(rec["difference"], 1)  # 283 - 282, count only
        # Coverage recorded as "covered/total (pct%)": 3 of 283 == 1%.
        self.assertEqual(rec.get("state_coverage"), "3/283 (1%)")
        # Only the country page was fetched — no state pages.
        self.assertEqual(len(calls), 1)

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

    def test_fr24_adds_states_but_our_data_is_flat_falls_back(self):
        # FR24 newly splits Germany into states; our data still uses bare "DE".
        # Must compare at country level, not flag every airport as added.
        pages = {
            "/data/airports/germany": _states_page_html([
                {"code": "BY", "name": "Bavaria", "total": 2, "url": "/data/airports/germany/by"},
                {"code": "BE", "name": "Berlin", "total": 1, "url": "/data/airports/germany/be"},
            ]),
            "/germany/by": _country_page_html([
                {"name": "Munich", "iata": "MUC", "icao": "EDDM"},
                {"name": "Nuremberg", "iata": "NUE", "icao": "EDDN"},
            ]),
            "/germany/be": _country_page_html([
                {"name": "Berlin Brandenburg", "iata": "BER", "icao": "EDDB"},
            ]),
        }
        # Our data: MUC + BER already present under bare "DE"; NUE is genuinely new.
        our = _rows(
            {"name": "Munich", "iata": "MUC", "placeCode": "DE"},
            {"name": "Berlin Brandenburg", "iata": "BER", "placeCode": "DE"},
        )
        rec, err, calls = self._run("Germany", "DE", 3, 2, pages, our)
        self.assertIsNone(err)
        # Only NUE is added — MUC/BER matched, not falsely re-added.
        self.assertEqual([a["iata"] for a in rec["added_airports"]], ["NUE"])
        self.assertEqual(rec["removed_airports"], [])
        # Added airport still carries its state placeCode for nesting.
        self.assertEqual(rec["added_airports"][0]["placeCode"], "DE-BY")

    def test_fr24_drops_states_but_our_data_subdivided(self):
        # FR24 flattens Canada (country page lists airports); our data keeps CA-XX.
        pages = {"/canada": _country_page_html([
            {"name": "Toronto", "iata": "YYZ", "icao": "CYYZ"},
            {"name": "Vancouver", "iata": "YVR", "icao": "CYVR"},
        ])}
        our = _rows(
            {"name": "Toronto", "iata": "YYZ", "placeCode": "CA-ON"},
            {"name": "Old Field", "iata": "YOL", "placeCode": "CA-AB"},  # gone from FR24
        )
        rec, err, calls = self._run("Canada", "CA", 2, 2, pages, our)
        self.assertIsNone(err)
        self.assertEqual([a["iata"] for a in rec["added_airports"]], ["YVR"])
        # Our subdivided airport is correctly matched/removed by country prefix.
        self.assertEqual([a["iata"] for a in rec["removed_airports"]], ["YOL"])
        self.assertEqual(len(calls), 1)  # flat: single country page


    def test_flat_country_suppresses_patched_airport_on_fr24_side(self):
        # FR24 wrongly lists RUE under Congo; our data deliberately keeps it
        # under CD. It must not surface as "added" to Congo.
        pages = {"/congo": _country_page_html([
            {"name": "Maya-Maya", "iata": "BZV", "icao": "FCBB"},
            {"name": "Pointe Noire", "iata": "PNR", "icao": "FCPP"},
            {"name": "Butembo Rughenda", "iata": "RUE", "icao": "FZMB"},
        ])}
        our = _rows({"name": "Maya-Maya", "iata": "BZV", "placeCode": "CG"},
                    {"name": "Pointe Noire", "iata": "PNR", "placeCode": "CG"})
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES",
                               {"RUE": {"fr24": "CG", "ours": "CD"}}):
            rec, err, _ = self._run("Congo", "CG", 3, 2, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])

    def test_flat_country_suppresses_patched_airport_on_our_side(self):
        # The corrected country's FR24 page doesn't list the airport; our copy
        # of it must not surface as "removed".
        pages = {"/democratic-republic-of-the-congo": _country_page_html([
            {"name": "Ndjili", "iata": "FIH", "icao": "FZAA"},
        ])}
        our = _rows({"name": "Ndjili", "iata": "FIH", "placeCode": "CD"},
                    {"name": "Butembo Rughenda", "iata": "RUE", "placeCode": "CD"})
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES",
                               {"RUE": {"fr24": "CG", "ours": "CD"}}):
            rec, err, _ = self._run("Democratic Republic Of The Congo", "CD", 2, 2, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])

    def test_flat_country_new_airport_surfaces_despite_patch(self):
        # FR24 adds a genuinely new airport to the corrected country. The
        # patched count (+1 for RUE) keeps this fetch from being masked, and
        # the detail must report the new airport while still suppressing RUE.
        pages = {"/democratic-republic-of-the-congo": _country_page_html([
            {"name": "Ndjili", "iata": "FIH", "icao": "FZAA"},
            {"name": "Bangoka", "iata": "FKI", "icao": "FZIC"},
        ])}
        our = _rows({"name": "Ndjili", "iata": "FIH", "placeCode": "CD"},
                    {"name": "Butembo Rughenda", "iata": "RUE", "placeCode": "CD"})
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES",
                               {"RUE": {"fr24": "CG", "ours": "CD"}}):
            rec, err, _ = self._run("Democratic Republic Of The Congo", "CD", 3, 2, pages, our)
        self.assertIsNone(err)
        self.assertEqual([a["iata"] for a in rec["added_airports"]], ["FKI"])
        self.assertEqual(rec["removed_airports"], [])

    def test_flat_country_reports_name_change_on_matched_airport(self):
        pages = {"/netherlands": _country_page_html([
            {"name": "Amsterdam Schiphol Airport", "iata": "AMS", "icao": "EHAM"},
        ])}
        our = _rows({"name": "Schiphol", "iata": "AMS", "icao": "EHAM", "placeCode": "NL"})
        rec, err, _ = self._run("Netherlands", "NL", 1, 1, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])
        self.assertEqual(rec["changed_count"], 1)
        self.assertEqual(rec["changed_airports"][0]["placeCode"], "NL")
        self.assertEqual(rec["changed_airports"][0]["changes"],
                         {"name": {"old": "Schiphol", "new": "Amsterdam Schiphol Airport"}})

    def test_flat_country_reports_iata_rename_as_changed(self):
        # Same airport, new IATA (QQT -> DTX), ICAO KTKI unchanged: one changed
        # record instead of an added+removed pair.
        pages = {"/united-states": _country_page_html([
            {"name": "McKinney National Airport", "iata": "DTX", "icao": "KTKI"},
        ])}
        our = _rows({"name": "McKinney National Airport", "iata": "QQT", "icao": "KTKI",
                     "placeCode": "US"})
        rec, err, _ = self._run("United States", "US", 1, 1, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])
        self.assertEqual(rec["added_count"], 0)
        self.assertEqual(rec["removed_count"], 0)
        self.assertEqual(rec["changed_count"], 1)
        change = rec["changed_airports"][0]
        self.assertEqual(change["iata"], "DTX")
        self.assertEqual(change["placeCode"], "US")
        self.assertEqual(change["changes"], {"iata": {"old": "QQT", "new": "DTX"}})

    def test_subdivisioned_state_move_reported_as_changed(self):
        # IAD reassigned from Virginia to DC on FR24. The per-state diffs see a
        # removal in VA and an addition in DC; country-level pairing must fold
        # them into one changed record and scrub both state breakdowns.
        pages = {
            "/data/airports/united-states": _states_page_html([
                {"code": "DC", "name": "Washington DC", "total": 1,
                 "url": "/data/airports/united-states/dc"},
                {"code": "VA", "name": "Virginia", "total": 1,
                 "url": "/data/airports/united-states/va"},
            ]),
            "/united-states/dc": _country_page_html([
                {"name": "Washington Dulles International Airport", "iata": "IAD",
                 "icao": "KIAD"},
            ]),
            "/united-states/va": _country_page_html([
                {"name": "Richmond International Airport", "iata": "RIC", "icao": "KRIC"},
            ]),
        }
        our = _rows(
            {"name": "Washington Dulles International Airport", "iata": "IAD",
             "icao": "KIAD", "placeCode": "US-VA"},
            {"name": "Richmond International Airport", "iata": "RIC", "icao": "KRIC",
             "placeCode": "US-VA"},
        )
        rec, err, _ = self._run("United States", "US", 2, 2, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])
        self.assertEqual(rec["changed_count"], 1)
        change = rec["changed_airports"][0]
        self.assertEqual(change["iata"], "IAD")
        self.assertEqual(change["placeCode"], "US-DC")
        self.assertEqual(change["changes"],
                         {"placeCode": {"old": "US-VA", "new": "US-DC"}})
        # The paired airport is gone from both state breakdowns, counts adjusted;
        # breakdown entries carry no changed lists of their own.
        self.assertEqual(rec["states"]["DC"]["added_airports"], [])
        self.assertEqual(rec["states"]["DC"]["added_count"], 0)
        self.assertEqual(rec["states"]["VA"]["removed_airports"], [])
        self.assertEqual(rec["states"]["VA"]["removed_count"], 0)
        self.assertNotIn("changed_airports", rec["states"]["DC"])

    def test_states_as_flat_rename_has_no_placecode_pseudo_change(self):
        # FR24 splits Germany into states while our data is flat: a rename
        # pairing across the granularity gap must not report DE -> DE-BY as a
        # move.
        pages = {
            "/data/airports/germany": _states_page_html([
                {"code": "BY", "name": "Bavaria", "total": 1,
                 "url": "/data/airports/germany/by"},
            ]),
            "/germany/by": _country_page_html([
                {"name": "Munich Airport", "iata": "MUX", "icao": "EDDM"},
            ]),
        }
        our = _rows({"name": "Munich Airport", "iata": "MUC", "icao": "EDDM",
                     "placeCode": "DE"})
        rec, err, _ = self._run("Germany", "DE", 1, 1, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])
        self.assertEqual(rec["changed_airports"][0]["changes"],
                         {"iata": {"old": "MUC", "new": "MUX"}})
        # The record keeps the state-qualified side (FR24's, here).
        self.assertEqual(rec["changed_airports"][0]["placeCode"], "DE-BY")

    def test_flat_fallback_rename_has_no_placecode_pseudo_change(self):
        # FR24 flattened Canada while our data keeps CA-AB: the pairing must
        # not suggest stripping the subdivision (CA-AB -> CA).
        pages = {"/canada": _country_page_html([
            {"name": "Old Field", "iata": "YNW", "icao": "CYOL"},
        ])}
        our = _rows({"name": "Old Field", "iata": "YOL", "icao": "CYOL",
                     "placeCode": "CA-AB"})
        rec, err, _ = self._run("Canada", "CA", 1, 1, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["added_airports"], [])
        self.assertEqual(rec["removed_airports"], [])
        self.assertEqual(rec["changed_airports"][0]["changes"],
                         {"iata": {"old": "YOL", "new": "YNW"}})
        # The record keeps the state-qualified side (ours, here).
        self.assertEqual(rec["changed_airports"][0]["placeCode"], "CA-AB")

    def test_flat_fallback_stage_a_change_keeps_our_subdivision(self):
        # FR24 flattened Canada but our data still knows CA-ON; the changed
        # record should point at where the airport lives in our data, not the
        # bare country FR24 offers.
        pages = {"/canada": _country_page_html([
            {"name": "Toronto Pearson International Airport", "iata": "YYZ",
             "icao": "CYYZ"},
        ])}
        our = _rows({"name": "Toronto Pearson", "iata": "YYZ", "icao": "CYYZ",
                     "placeCode": "CA-ON"})
        rec, err, _ = self._run("Canada", "CA", 1, 1, pages, our)
        self.assertIsNone(err)
        self.assertEqual(rec["changed_airports"][0]["placeCode"], "CA-ON")
        self.assertEqual(rec["changed_airports"][0]["changes"],
                         {"name": {"old": "Toronto Pearson",
                                   "new": "Toronto Pearson International Airport"}})



class Fr24CountryPatchTest(unittest.TestCase):
    """FR24 places some airports under the wrong country (e.g. RUE under Congo
    instead of DR Congo) and Skycards deliberately deviates. The patch table
    remaps FR24's counts and airport lists to the corrected country so the
    known mismatch stops surfacing as a permanent added/removed pair."""

    PATCHES = {"RUE": {"fr24": "CG", "ours": "CD"}}

    def test_count_patch_moves_airport_between_countries(self):
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES):
            counts = ca._patch_fr24_iso_counts({"CG": 3, "CD": 26})
        self.assertEqual(counts, {"CG": 2, "CD": 27})

    def test_count_patch_skips_missing_source_country(self):
        # FR24 lists nothing under the source country (data likely fixed on
        # their side): moving a count would fabricate a negative — leave it.
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES):
            counts = ca._patch_fr24_iso_counts({"CD": 26})
        self.assertEqual(counts, {"CD": 26})

    def test_compare_drops_patched_airport_from_fr24_list(self):
        fr24 = [{"iata": "BZV", "icao": "FCBB", "name": "Maya-Maya"},
                {"iata": "RUE", "icao": "FZMB", "name": "Butembo Rughenda"}]
        our = [{"iata": "BZV", "icao": "FCBB", "name": "Maya-Maya", "placeCode": "CG"}]
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES):
            added, removed, _ = ca.compare_country_airports(fr24, our, "CG")
        self.assertEqual(added, [])
        self.assertEqual(removed, [])

    def test_compare_drops_patched_airport_from_our_list(self):
        fr24 = [{"iata": "FIH", "icao": "FZAA", "name": "Ndjili"}]
        our = [{"iata": "FIH", "icao": "FZAA", "name": "Ndjili", "placeCode": "CD"},
               {"iata": "RUE", "icao": "FZMB", "name": "Butembo Rughenda", "placeCode": "CD"}]
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES):
            added, removed, _ = ca.compare_country_airports(fr24, our, "CD")
        self.assertEqual(added, [])
        self.assertEqual(removed, [])

    def test_compare_matches_by_country_prefix_of_state_codes(self):
        # State-level comparisons pass "CG"-prefixed context too; the patch
        # keys on the country part.
        fr24 = [{"iata": "RUE", "icao": "FZMB", "name": "Butembo Rughenda"}]
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES):
            added, removed, _ = ca.compare_country_airports(fr24, [], "CG-XX")
        self.assertEqual(added, [])
        self.assertEqual(removed, [])

    def test_compare_without_country_context_is_unpatched(self):
        fr24 = [{"iata": "RUE", "icao": "FZMB", "name": "Butembo Rughenda"}]
        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES):
            added, removed, _ = ca.compare_country_airports(fr24, [])
        self.assertEqual([a["iata"] for a in added], ["RUE"])

    def test_analyze_fetches_nothing_once_counts_agree(self):
        # Steady state: FR24 keeps counting RUE under Congo (CG raw 3 vs our
        # 2, forever) and our CD holds every airport FR24 has plus RUE. After
        # patching both sides agree, so no country page is fetched at all.
        calls = []

        def fake_diff(iso, name, fr24_count, our_count, airports_data):
            calls.append(iso)
            return {"iso_code": iso, "added_count": 0, "removed_count": 0}, None

        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES), \
             mock.patch.object(ca, "_diff_one_country", fake_diff), \
             mock.patch.object(ca.time, "sleep", lambda *a, **k: None):
            diffs = ca.analyze_country_differences(
                {"Congo": 3, "Democratic Republic Of The Congo": 26},
                {"CG": 2, "CD": 27},
                ca.create_country_mapping(), {"rows": []})
        self.assertEqual(calls, [])
        self.assertEqual(diffs, {})

    def test_analyze_respects_count_patch(self):
        # After patching, CG matches (2 == 2) and must not be analyzed; CD
        # carries the moved count (27 vs 26) and must be.
        calls = []

        def fake_diff(iso, name, fr24_count, our_count, airports_data):
            calls.append((iso, fr24_count, our_count))
            return {"iso_code": iso, "added_count": 0, "removed_count": 0}, None

        with mock.patch.object(ca, "FR24_COUNTRY_PATCHES", self.PATCHES), \
             mock.patch.object(ca, "_diff_one_country", fake_diff), \
             mock.patch.object(ca.time, "sleep", lambda *a, **k: None):
            diffs = ca.analyze_country_differences(
                {"Congo": 3, "Democratic Republic Of The Congo": 26},
                {"CG": 2, "CD": 26},
                ca.create_country_mapping(), {"rows": []})
        self.assertEqual([c[0] for c in calls], ["CD"])
        self.assertEqual(calls[0][1], 27)
        self.assertNotIn("CG", diffs)
        self.assertIn("CD", diffs)



class CompareChangedAirportsTest(unittest.TestCase):
    """Stage A: field diffs on airports matched by identifier."""

    def test_name_change_on_matched_airport(self):
        fr24 = [{"name": "Amsterdam Schiphol Airport", "iata": "AMS", "icao": "EHAM"}]
        our = [{"name": "Schiphol", "iata": "AMS", "icao": "EHAM", "placeCode": "NL"}]
        added, removed, changed = ca.compare_country_airports(fr24, our, "NL")
        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        self.assertEqual(len(changed), 1)
        # Top level carries the current FR24 values; changes holds only the diff.
        self.assertEqual(changed[0]["name"], "Amsterdam Schiphol Airport")
        self.assertEqual(changed[0]["changes"],
                         {"name": {"old": "Schiphol", "new": "Amsterdam Schiphol Airport"}})

    def test_icao_change_on_matched_airport(self):
        fr24 = [{"name": "A", "iata": "AMS", "icao": "EHAM"}]
        our = [{"name": "A", "iata": "AMS", "icao": "EHXX", "placeCode": "NL"}]
        added, removed, changed = ca.compare_country_airports(fr24, our, "NL")
        self.assertEqual(changed[0]["changes"], {"icao": {"old": "EHXX", "new": "EHAM"}})

    def test_empty_vs_set_icao_is_a_change(self):
        # Our data often lacks the ICAO; FR24 knowing it counts as a change.
        fr24 = [{"name": "A", "iata": "AMS", "icao": "EHAM"}]
        our = [{"name": "A", "iata": "AMS", "icao": "", "placeCode": "NL"}]
        added, removed, changed = ca.compare_country_airports(fr24, our, "NL")
        self.assertEqual(changed[0]["changes"], {"icao": {"old": "", "new": "EHAM"}})

    def test_whitespace_only_name_difference_is_not_a_change(self):
        fr24 = [{"name": "Rotterdam  The Hague  Airport", "iata": "RTM", "icao": "EHRD"}]
        our = [{"name": "Rotterdam The Hague Airport", "iata": "RTM", "icao": "EHRD",
                "placeCode": "NL"}]
        added, removed, changed = ca.compare_country_airports(fr24, our, "NL")
        self.assertEqual(changed, [])

    def test_changed_records_sorted_by_iata_then_name(self):
        fr24 = [{"name": "Bravo", "iata": "BBB", "icao": "EHBB"},
                {"name": "Alpha", "iata": "AAA", "icao": "EHAA"}]
        our = [{"name": "Bravo Old", "iata": "BBB", "icao": "EHBB", "placeCode": "NL"},
               {"name": "Alpha Old", "iata": "AAA", "icao": "EHAA", "placeCode": "NL"}]
        added, removed, changed = ca.compare_country_airports(fr24, our, "NL")
        self.assertEqual([c["iata"] for c in changed], ["AAA", "BBB"])

    def test_changed_record_drops_title_field(self):
        fr24 = [{"name": "A", "iata": "AMS", "icao": "EHAM", "title": "leftover"}]
        our = [{"name": "B", "iata": "AMS", "icao": "EHAM", "placeCode": "NL"}]
        added, removed, changed = ca.compare_country_airports(fr24, our, "NL")
        self.assertNotIn("title", changed[0])


class PairChangedTest(unittest.TestCase):
    """Stage B: pair country-level added/removed records that are really the
    same airport under a new identifier or subdivision."""

    def test_pairs_iata_rename_by_shared_icao(self):
        # QQT -> DTX rename at McKinney National (ICAO KTKI stayed put).
        added = [{"name": "McKinney National Airport", "iata": "DTX", "icao": "KTKI",
                  "state": "TX", "placeCode": "US-TX"}]
        removed = [{"name": "McKinney National Airport", "iata": "QQT", "icao": "KTKI",
                    "placeCode": "US-TX"}]
        changed, paired_ids = ca._pair_changed(added, removed)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["iata"], "DTX")
        self.assertEqual(changed[0]["changes"], {"iata": {"old": "QQT", "new": "DTX"}})
        self.assertEqual(paired_ids, {id(added[0]), id(removed[0])})

    def test_pairs_pure_state_move(self):
        # IAD reassigned US-VA -> US-DC; identifiers unchanged.
        added = [{"name": "Washington Dulles International Airport", "iata": "IAD",
                  "icao": "KIAD", "state": "DC", "placeCode": "US-DC"}]
        removed = [{"name": "Washington Dulles International Airport", "iata": "IAD",
                    "icao": "KIAD", "placeCode": "US-VA"}]
        changed, _ = ca._pair_changed(added, removed)
        self.assertEqual(changed[0]["changes"],
                         {"placeCode": {"old": "US-VA", "new": "US-DC"}})

    def test_rename_and_move_is_one_record_with_both_changes(self):
        added = [{"name": "Columbia Regional Airport", "iata": "COU", "icao": "KCOA",
                  "state": "MO", "placeCode": "US-MO"}]
        removed = [{"name": "Columbia Regional Airport", "iata": "COA", "icao": "KCOA",
                    "placeCode": "US-CA"}]
        changed, _ = ca._pair_changed(added, removed)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["changes"],
                         {"iata": {"old": "COA", "new": "COU"},
                          "placeCode": {"old": "US-CA", "new": "US-MO"}})

    def test_ambiguous_duplicate_icao_not_paired(self):
        added = [{"name": "A1", "iata": "AAA", "icao": "KDUP", "placeCode": "US-TX"},
                 {"name": "A2", "iata": "BBB", "icao": "KDUP", "placeCode": "US-TX"}]
        removed = [{"name": "R", "iata": "CCC", "icao": "KDUP", "placeCode": "US-OK"}]
        changed, paired_ids = ca._pair_changed(added, removed)
        self.assertEqual(changed, [])
        self.assertEqual(paired_ids, set())

    def test_ambiguous_duplicate_icao_on_removed_side_not_paired(self):
        added = [{"name": "A", "iata": "AAA", "icao": "KDUP", "placeCode": "US-TX"}]
        removed = [{"name": "R1", "iata": "BBB", "icao": "KDUP", "placeCode": "US-TX"},
                   {"name": "R2", "iata": "CCC", "icao": "KDUP", "placeCode": "US-OK"}]
        changed, paired_ids = ca._pair_changed(added, removed)
        self.assertEqual(changed, [])
        self.assertEqual(paired_ids, set())

    def test_records_without_codes_never_pair(self):
        added = [{"name": "New Field", "iata": "", "icao": "", "placeCode": "US-TX"}]
        removed = [{"name": "Old Field", "iata": None, "icao": "", "placeCode": "US-TX"}]
        changed, paired_ids = ca._pair_changed(added, removed)
        self.assertEqual(changed, [])
        self.assertEqual(paired_ids, set())

    def test_suppressed_placecode_prefers_state_qualified_side(self):
        added = [{"name": "Old Field", "iata": "YNW", "icao": "CYOL", "placeCode": "CA"}]
        removed = [{"name": "Old Field", "iata": "YOL", "icao": "CYOL",
                    "placeCode": "CA-AB"}]
        changed, _ = ca._pair_changed(added, removed)
        self.assertEqual(changed[0]["placeCode"], "CA-AB")
        self.assertEqual(changed[0]["changes"], {"iata": {"old": "YOL", "new": "YNW"}})

    def test_iata_pass_pairs_leftovers_after_icao_pass(self):
        # ICAO pass consumes the KAAA pair; the leftover then pairs by IATA
        # even though its counterpart has no ICAO.
        added = [
            {"name": "Alpha", "iata": "AAB", "icao": "KAAA", "placeCode": "US-TX"},
            {"name": "Beta", "iata": "BBB", "icao": "KBBB", "placeCode": "US-TX"},
        ]
        removed = [
            {"name": "Alpha", "iata": "AAA", "icao": "KAAA", "placeCode": "US-TX"},
            {"name": "Beta", "iata": "BBB", "icao": "", "placeCode": "US-OK"},
        ]
        changed, paired_ids = ca._pair_changed(added, removed)
        self.assertEqual(len(changed), 2)
        by_iata = {c["iata"]: c for c in changed}
        self.assertEqual(by_iata["AAB"]["changes"], {"iata": {"old": "AAA", "new": "AAB"}})
        self.assertEqual(by_iata["BBB"]["changes"],
                         {"icao": {"old": "", "new": "KBBB"},
                          "placeCode": {"old": "US-OK", "new": "US-TX"}})
        self.assertEqual(len(paired_ids), 4)

    def test_icao_pairing_wins_and_each_record_pairs_once(self):
        added = [{"name": "X", "iata": "QQQ", "icao": "K01", "placeCode": "US-TX"}]
        removed = [{"name": "X", "iata": "ZZZ", "icao": "K01", "placeCode": "US-TX"},
                   {"name": "Y", "iata": "QQQ", "icao": "K02", "placeCode": "US-TX"}]
        changed, paired_ids = ca._pair_changed(added, removed)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["changes"], {"iata": {"old": "ZZZ", "new": "QQQ"}})
        self.assertNotIn(id(removed[1]), paired_ids)


class MainSummaryTest(unittest.TestCase):
    def test_summary_totals_include_changed_airports(self):
        # Records carried over from an existing differences file may predate
        # changed_count; the summary must tolerate its absence.
        differences = {
            "NL": {"iso_code": "NL", "added_count": 1, "removed_count": 0,
                   "changed_count": 2},
            "US": {"iso_code": "US", "added_count": 0, "removed_count": 1},
        }
        cwd = os.getcwd()
        with mock.patch.object(ca, "scrape_flightradar24", lambda: {"Netherlands": 1}), \
             mock.patch.object(ca, "load_airports_data",
                               lambda path: ({"NL": 2}, {"rows": []})), \
             mock.patch.object(ca, "analyze_country_differences",
                               lambda *a, **k: differences), \
             tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                ca.main()
                with open("airport_differences.json", encoding="utf-8") as f:
                    output = json.load(f)
            finally:
                os.chdir(cwd)
        self.assertEqual(output["summary"]["total_added_airports"], 1)
        self.assertEqual(output["summary"]["total_removed_airports"], 1)
        self.assertEqual(output["summary"]["total_changed_airports"], 2)


def _mobile_row(**over):
    row = {
        "id": 3, "name": "Aachen Merzbruck Airport", "iata": "AAH",
        "icao": "EDKA", "city": "Aachen", "lat": 50.8219, "lon": 6.1848,
        "country": "Germany", "alt": 626, "size": 1279,
        "timezone": {"name": "Europe/Berlin"}, "countryId": 83,
        "videoStream": None,
    }
    row.update(over)
    return row


class ParseMobilePayloadTest(unittest.TestCase):
    def test_parses_rows(self):
        rows = [_mobile_row(id=i) for i in range(ca.MIN_MOBILE_ROWS)]
        payload = json.dumps({"version": "1788190045", "rows": rows})
        rows_out = ca.parse_mobile_payload(payload)
        self.assertEqual(len(rows_out), ca.MIN_MOBILE_ROWS)
        self.assertEqual(rows_out[0]["iata"], "AAH")

    def test_rejects_non_json(self):
        # e.g. a Cloudflare challenge page instead of the JSON payload
        with self.assertRaisesRegex(ValueError, "not JSON"):
            ca.parse_mobile_payload("<html>Just a moment...</html>")

    def test_rejects_missing_rows(self):
        with self.assertRaisesRegex(ValueError, "no 'rows' list"):
            ca.parse_mobile_payload(json.dumps({"version": "1"}))

    def test_rejects_suspiciously_few_rows(self):
        # A truncated or partial payload must read as a failed fetch, never as
        # thousands of removed airports.
        payload = json.dumps({"version": "1", "rows": [_mobile_row()]})
        with self.assertRaisesRegex(ValueError, "usable airport ids"):
            ca.parse_mobile_payload(payload)

    def test_rejects_duplicate_ids(self):
        rows = [_mobile_row() for _ in range(ca.MIN_MOBILE_ROWS + 100)]
        payload = json.dumps({"version": "1", "rows": rows})
        with self.assertRaisesRegex(ValueError, "usable airport ids"):
            ca.parse_mobile_payload(payload)

    def test_rejects_top_level_array(self):
        with self.assertRaisesRegex(ValueError, "no 'rows' list"):
            ca.parse_mobile_payload("[]")

    def test_rejects_rows_not_a_list(self):
        with self.assertRaisesRegex(ValueError, "no 'rows' list"):
            ca.parse_mobile_payload(json.dumps({"rows": {}}))


class FetchMobileAirportsTest(unittest.TestCase):
    def test_returns_rows_on_success(self):
        rows = [_mobile_row(id=i) for i in range(ca.MIN_MOBILE_ROWS)]
        body = json.dumps({"version": "1", "rows": rows})
        with mock.patch.object(ca, "_fetch_text", return_value=(body, None)) as fetch:
            self.assertEqual(len(ca.fetch_mobile_airports()), ca.MIN_MOBILE_ROWS)
            fetch.assert_called_once_with(ca.MOBILE_AIRPORTS_URL, mock.ANY)

    def test_returns_none_on_fetch_error(self):
        with mock.patch.object(ca, "_fetch_text", return_value=(None, "boom")):
            self.assertIsNone(ca.fetch_mobile_airports())

    def test_returns_none_on_invalid_payload(self):
        with mock.patch.object(ca, "_fetch_text", return_value=("<html>", None)):
            self.assertIsNone(ca.fetch_mobile_airports())


if __name__ == "__main__":
    unittest.main()
