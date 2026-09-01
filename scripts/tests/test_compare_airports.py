import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import compare_airports as ca


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

    def test_rejects_string_typed_ids(self):
        # FR24's website endpoint types ids as strings; if the mobile payload
        # ever drifts the same way, that must read as a failed fetch, not as
        # every airport being removed and re-added.
        rows = [_mobile_row(id=str(i)) for i in range(ca.MIN_MOBILE_ROWS)]
        payload = json.dumps({"version": "1", "rows": rows})
        with self.assertRaisesRegex(ValueError, "usable airport ids"):
            ca.parse_mobile_payload(payload)


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


def _our_row(**over):
    row = {"id": 3, "iata": "AAH", "icao": "EDKA",
           "name": "Aachen Merzbruck Airport", "placeCode": "DE"}
    row.update(over)
    return row


class FakeLookup:
    """Test double for state_lookup.StateLookup."""

    def __init__(self, answers=None):
        self.answers = answers or {}

    def lookup(self, lon, lat, country):
        return self.answers.get((lon, lat, country))

    def state_name(self, code):
        return code


class CompareMobileAirportsTest(unittest.TestCase):
    def compare(self, mobile, ours, lookup=None):
        airports_data = {"rows": ours}
        return ca.compare_mobile_airports(
            mobile, airports_data, ca.create_country_mapping(),
            lookup or FakeLookup())

    def test_identical_data_no_differences(self):
        diffs, unmapped = self.compare([_mobile_row()], [_our_row()])
        self.assertEqual(diffs, {})
        self.assertEqual(unmapped, [])

    def test_added_airport_groups_by_fr24_label(self):
        diffs, _ = self.compare(
            [_mobile_row(), _mobile_row(id=99, iata="XYZ", icao="EDXY",
                                        name="New Airport")],
            [_our_row()])
        self.assertEqual(list(diffs), ["DE"])
        record = diffs["DE"]
        self.assertEqual(record["fr24_count"], 2)
        self.assertEqual(record["skycards_count"], 1)
        self.assertEqual(record["difference"], 1)
        self.assertEqual(record["added_count"], 1)
        added = record["added_airports"][0]
        self.assertEqual(added["iata"], "XYZ")
        self.assertEqual(added["placeCode"], "DE")
        self.assertNotIn("timezone", added)
        self.assertNotIn("size", added)

    def test_removed_airport_groups_by_our_placecode(self):
        # RUE-class insurance: even when FR24 mislabels a country, a removed
        # airport is grouped by OUR placeCode, so no mapping is involved.
        diffs, _ = self.compare(
            [], [_our_row(id=50, iata="RUE", icao="FZMB",
                          name="Butembo Rughenda Airport", placeCode="CD")])
        record = diffs["CD"]
        self.assertEqual(record["removed_count"], 1)
        self.assertEqual(record["fr24_count"], 0)
        self.assertEqual(record["skycards_count"], 1)
        self.assertEqual(record["removed_airports"][0]["iata"], "RUE")

    def test_matched_airport_ignores_country_label_mismatch(self):
        # SMZ-class: FR24 files it under Suriname, we under French Guiana.
        # Matched by id -> no diff at all, in either country.
        diffs, _ = self.compare(
            [_mobile_row(id=7, iata="SMZ", icao="SMST",
                         name="Stoelmanseiland Airport", country="Suriname")],
            [_our_row(id=7, iata="SMZ", icao="SMST",
                      name="Stoelmanseiland Airport", placeCode="GF")])
        self.assertEqual(diffs, {})

    def test_changed_airport_buckets_by_our_placecode_not_fr24_label(self):
        # KIA/SMZ-class airport with a real field change must land in OUR
        # country bucket, never FR24's label.
        diffs, _ = self.compare(
            [_mobile_row(id=7, iata="SMZ", icao="SMST",
                         name="Stoelmanseiland Airfield", country="Suriname")],
            [_our_row(id=7, iata="SMZ", icao="SMST",
                      name="Stoelmanseiland Airport", placeCode="GF")])
        self.assertEqual(list(diffs), ["GF"])
        self.assertEqual(diffs["GF"]["changed_count"], 1)

    def test_field_change_reported_with_our_placecode(self):
        diffs, _ = self.compare(
            [_mobile_row(iata="AAX")],
            [_our_row(placeCode="DE")])
        record = diffs["DE"]
        self.assertEqual(record["added_count"], 0)
        self.assertEqual(record["removed_count"], 0)
        self.assertEqual(record["changed_count"], 1)
        changed = record["changed_airports"][0]
        self.assertEqual(changed["iata"], "AAX")
        self.assertEqual(changed["placeCode"], "DE")
        self.assertEqual(changed["changes"],
                         {"iata": {"old": "AAH", "new": "AAX"}})
        # counts balance: a change is not a count difference
        self.assertEqual(record["difference"], 0)

    def test_name_change_whitespace_insensitive(self):
        diffs, _ = self.compare(
            [_mobile_row(name="Aachen  Merzbruck Airport")],
            [_our_row()])
        self.assertEqual(diffs, {})

    def test_empty_vs_set_icao_is_a_change(self):
        # Ports the behavior pinned by the old CompareChangedAirportsTest
        # (deleted in Task 6): ''/None vs a real value counts as a change.
        diffs, _ = self.compare(
            [_mobile_row(icao="EDKA")],
            [_our_row(icao="")])
        changed = diffs["DE"]["changed_airports"][0]
        self.assertEqual(changed["changes"],
                         {"icao": {"old": "", "new": "EDKA"}})

    def test_codeless_our_row_excluded_entirely(self):
        # Codeless remnants of FR24-deleted airports must not surface as
        # removed, and their FR24 twin (if any) counts as added.
        diffs, _ = self.compare(
            [_mobile_row(id=4028, iata="YMJ", icao="CYMJ",
                         name="Moose Jaw Municipal Airport", country="Canada")],
            [_our_row(id=4028, iata=None, icao=None,
                      name="Moose Jaw Municipal Airport", placeCode="CA-SK")])
        record = diffs["CA"]
        self.assertEqual(record["removed_count"], 0)
        self.assertEqual(record["added_count"], 1)
        self.assertEqual(record["skycards_count"], 0)

    def test_added_in_subdivided_country_gets_geo_state(self):
        lookup = FakeLookup({(6.1848, 50.8219, "US"): "US-NY"})
        diffs, _ = self.compare(
            [_mobile_row(id=99, iata="XYZ", icao="KXYZ",
                         name="New Airport", country="United States")],
            [_our_row(placeCode="US-CA")], lookup)
        # Ours: 1 airport under US-CA; FR24 adds one geo-attributed to US-NY.
        added = diffs["US"]["added_airports"][0]
        self.assertEqual(added["placeCode"], "US-NY")

    def test_added_geo_failure_falls_back_to_bare_country(self):
        diffs, _ = self.compare(
            [_mobile_row(id=99, iata="XYZ", icao="KXYZ",
                         name="New Airport", country="United States")],
            [_our_row(placeCode="US-CA")], FakeLookup())
        added = diffs["US"]["added_airports"][0]
        self.assertEqual(added["placeCode"], "US")

    def test_added_in_flat_country_skips_geo_lookup(self):
        # Germany is not subdivided in our data -> no lookup call, bare ISO.
        lookup = FakeLookup({(6.1848, 50.8219, "DE"): "DE-NW"})
        diffs, _ = self.compare(
            [_mobile_row(), _mobile_row(id=99, iata="XYZ", icao="EDXY",
                                        name="New Airport")],
            [_our_row()], lookup)
        self.assertEqual(diffs["DE"]["added_airports"][0]["placeCode"], "DE")

    def test_removed_in_subdivided_country_keys_by_country(self):
        diffs, _ = self.compare(
            [], [_our_row(id=60, iata="ANC", icao="PANC",
                          name="Anchorage", placeCode="US-AK")])
        self.assertEqual(list(diffs), ["US"])
        self.assertEqual(diffs["US"]["removed_airports"][0]["placeCode"], "US-AK")

    def test_changed_record_keeps_state_qualified_placecode(self):
        diffs, _ = self.compare(
            [_mobile_row(id=60, iata="ANX", icao="PANC",
                         name="Anchorage", country="United States")],
            [_our_row(id=60, iata="ANC", icao="PANC",
                      name="Anchorage", placeCode="US-AK")])
        self.assertEqual(diffs["US"]["changed_airports"][0]["placeCode"], "US-AK")

    def test_unmapped_country_label_goes_to_bucket(self):
        diffs, unmapped = self.compare(
            [_mobile_row(id=99, iata="XYZ", icao="ZZZZ",
                         name="Mystery Airport", country="Atlantis")],
            [])
        self.assertEqual(diffs, {})
        self.assertEqual(len(unmapped), 1)
        self.assertEqual(unmapped[0]["country"], "Atlantis")
        self.assertEqual(unmapped[0]["iata"], "XYZ")

    def test_lists_sorted_by_iata_then_name(self):
        diffs, _ = self.compare(
            [_mobile_row(),
             _mobile_row(id=98, iata="BBB", icao="EDBB", name="A Airport"),
             _mobile_row(id=99, iata="AAA", icao="EDAA", name="Z Airport")],
            [_our_row(),
             _our_row(id=50, iata="DDD", icao="EDDD", name="A Gone", placeCode="DE"),
             _our_row(id=51, iata="CCC", icao="EDCC", name="Z Gone", placeCode="DE")])
        record = diffs["DE"]
        self.assertEqual([a["iata"] for a in record["added_airports"]],
                         ["AAA", "BBB"])
        self.assertEqual([a["iata"] for a in record["removed_airports"]],
                         ["CCC", "DDD"])

    def test_country_display_name(self):
        mapping = ca.create_country_mapping()
        self.assertEqual(ca._country_display_name("US", mapping),
                         "United States")
        self.assertEqual(ca._country_display_name("ZZ", mapping), "ZZ")


class StatesBreakdownTest(unittest.TestCase):
    def test_breakdown_groups_by_state_and_computes_counts(self):
        ours = [
            _our_row(id=1, iata="ONE", icao="KONE", placeCode="US-NY"),
            _our_row(id=2, iata="TWO", icao="KTWO", placeCode="US-NY"),
            _our_row(id=3, iata="TRE", icao="KTRE", placeCode="US-CA"),
        ]
        added = [{"name": "New NY", "iata": "NEW", "icao": "KNEW",
                  "placeCode": "US-NY"}]
        removed = [{"name": "Old CA", "iata": "TRE", "icao": "KTRE",
                    "placeCode": "US-CA"}]
        breakdown = ca._states_breakdown("US", added, removed, ours,
                                         FakeLookup())
        self.assertEqual(list(breakdown), ["CA", "NY"])
        ny = breakdown["NY"]
        self.assertEqual(ny["fr24_count"], 3)       # 2 ours + 1 added
        self.assertEqual(ny["skycards_count"], 2)
        self.assertEqual(ny["difference"], 1)
        self.assertEqual(ny["added_count"], 1)
        self.assertEqual(ny["removed_count"], 0)
        camp = breakdown["CA"]
        self.assertEqual(camp["fr24_count"], 0)
        self.assertEqual(camp["skycards_count"], 1)
        self.assertEqual(camp["removed_count"], 1)

    def test_states_without_differences_are_omitted(self):
        ours = [_our_row(id=1, iata="ONE", icao="KONE", placeCode="US-NY")]
        breakdown = ca._states_breakdown("US", [], [], ours, FakeLookup())
        self.assertEqual(breakdown, {})

    def test_bare_country_added_airport_not_in_breakdown(self):
        # A geo-lookup failure leaves placeCode == "US"; it belongs to the
        # country aggregate only, never a fabricated state bucket.
        added = [{"name": "Floater", "iata": "FLO", "icao": "KFLO",
                  "placeCode": "US"}]
        breakdown = ca._states_breakdown("US", added, [], [], FakeLookup())
        self.assertEqual(breakdown, {})

    def test_other_country_rows_do_not_leak_into_counts(self):
        # our_rows spans all countries; a colliding state suffix in another
        # country (CN-SD vs US-SD exist in real data) must not count here.
        ours = [
            _our_row(id=1, iata="ONE", icao="KONE", placeCode="US-SD"),
            _our_row(id=2, iata="TWO", icao="KTWO", placeCode="CN-SD"),
            _our_row(id=3, iata="TRE", icao="KTRE", placeCode="DE"),
        ]
        added = [{"name": "New SD", "iata": "NEW", "icao": "KNEW",
                  "placeCode": "US-SD"}]
        breakdown = ca._states_breakdown("US", added, [], ours, FakeLookup())
        self.assertEqual(set(breakdown), {"SD"})
        self.assertEqual(breakdown["SD"]["skycards_count"], 1)

    def test_state_names_come_from_lookup(self):
        class NamedLookup(FakeLookup):
            def state_name(self, code):
                return {"US-NY": "New York"}.get(code, code)

        added = [{"name": "New NY", "iata": "NEW", "icao": "KNEW",
                  "placeCode": "US-NY"}]
        breakdown = ca._states_breakdown("US", added, [], [], NamedLookup())
        self.assertEqual(breakdown["NY"]["state_name"], "New York")


class StatesIntegrationTest(unittest.TestCase):
    """The breakdown wired through compare_mobile_airports."""

    def compare(self, mobile, ours, lookup=None):
        return ca.compare_mobile_airports(
            mobile, {"rows": ours}, ca.create_country_mapping(),
            lookup or FakeLookup())

    def test_subdivided_country_gets_states_key(self):
        lookup = FakeLookup({(6.1848, 50.8219, "US"): "US-NY"})
        diffs, _ = self.compare(
            [_mobile_row(country="United States"),
             _mobile_row(id=99, iata="XYZ", icao="KXYZ",
                         name="New Airport", country="United States")],
            [_our_row(placeCode="US-CA")], lookup)
        self.assertIn("states", diffs["US"])
        self.assertEqual(set(diffs["US"]["states"]), {"NY"})
        self.assertEqual(diffs["US"]["states"]["NY"]["added_count"], 1)

    def test_codeless_rows_do_not_inflate_state_counts(self):
        # A codeless remnant in US-NY must not count toward NY's
        # skycards_count — the breakdown gets the same code-filtered rows
        # as the country-level counts.
        lookup = FakeLookup({(6.1848, 50.8219, "US"): "US-NY"})
        diffs, _ = self.compare(
            [_mobile_row(country="United States"),
             _mobile_row(id=99, iata="XYZ", icao="KXYZ",
                         name="New Airport", country="United States")],
            [_our_row(placeCode="US-CA"),
             _our_row(id=77, iata=None, icao=None, name="Ghost",
                      placeCode="US-NY")], lookup)
        self.assertEqual(diffs["US"]["states"]["NY"]["skycards_count"], 0)
        self.assertEqual(diffs["US"]["states"]["NY"]["fr24_count"], 1)

    def test_changed_only_subdivided_country_has_no_states_key(self):
        diffs, _ = self.compare(
            [_mobile_row(id=60, iata="ANX", icao="PANC",
                         name="Anchorage", country="United States")],
            [_our_row(id=60, iata="ANC", icao="PANC",
                      name="Anchorage", placeCode="US-AK")])
        self.assertEqual(diffs["US"]["changed_count"], 1)
        self.assertNotIn("states", diffs["US"])

    def test_flat_country_never_gets_states_key(self):
        diffs, _ = self.compare(
            [_mobile_row(), _mobile_row(id=99, iata="XYZ", icao="EDXY",
                                        name="New Airport")],
            [_our_row()])
        self.assertNotIn("states", diffs["DE"])

    def test_malformed_mobile_rows_are_skipped(self):
        diffs, _ = self.compare(
            [_mobile_row(id=99, iata="XYZ", icao="EDXY", name="New"),
             {"name": "broken"}, "garbage"],
            [_our_row()])
        self.assertEqual(diffs["DE"]["added_count"], 1)


class MainSummaryTest(unittest.TestCase):
    def test_summary_totals_and_unmapped_key(self):
        mobile = [
            _mobile_row(),
            _mobile_row(id=99, iata="XYZ", icao="EDXY", name="New Airport"),
            _mobile_row(id=98, iata="QQQ", icao="ZZZZ", name="Mystery",
                        country="Atlantis"),
        ]
        ours = {"rows": [_our_row(),
                         _our_row(id=50, iata="GON", icao="EDGO",
                                  name="Gone Airport", placeCode="DE")]}

        class BareLookup:
            def lookup(self, lon, lat, country):
                return None

            def state_name(self, code):
                return code

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(ca, "fetch_mobile_airports",
                                  return_value=mobile), \
                mock.patch.object(ca, "load_airports_data",
                                  return_value=({"DE": 2}, ours)), \
                mock.patch.object(ca.state_lookup, "load_state_lookup",
                                  return_value=BareLookup()):
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                ca.main()
                out = json.load(open("airport_differences.json"))
            finally:
                os.chdir(cwd)

        self.assertEqual(out["summary"], {
            "total_countries_with_differences": 1,
            "total_added_airports": 1,
            "total_removed_airports": 1,
            "total_changed_airports": 0,
        })
        self.assertEqual(len(out["unmapped"]), 1)
        self.assertEqual(out["unmapped"][0]["country"], "Atlantis")

    def test_main_exits_nonzero_on_failed_fetch(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(ca, "fetch_mobile_airports",
                                  return_value=None):
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with self.assertRaises(SystemExit) as ctx:
                    ca.main()
                self.assertEqual(os.listdir(tmp), [])
            finally:
                os.chdir(cwd)
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
