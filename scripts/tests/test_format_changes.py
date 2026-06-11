import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import format_changes as fc  # noqa: E402


class HelpersTest(unittest.TestCase):
    def test_na(self):
        self.assertEqual(fc.na(None), "N/A")
        self.assertEqual(fc.na(0), "N/A")
        self.assertEqual(fc.na(""), "N/A")
        self.assertEqual(fc.na(9), "9")
        self.assertEqual(fc.na(16.3, "m"), "16.3m")

    def test_diff_added_removed_updated(self):
        old = [{"id": "A", "v": 1}, {"id": "B", "v": 2}]
        new = [{"id": "B", "v": 9}, {"id": "C", "v": 3}]
        fields = [("V", lambda r: str(r["v"]))]
        added, updated, removed = fc.diff(old, new, "id", fields)
        self.assertEqual([r["id"] for r in added], ["C"])
        self.assertEqual([r["id"] for r in removed], ["A"])
        self.assertEqual([(o["id"], n["id"]) for o, n in updated], [("B", "B")])

    def test_diff_no_change_not_updated(self):
        old = [{"id": "A", "v": 1}]
        new = [{"id": "A", "v": 1}]
        fields = [("V", lambda r: str(r["v"]))]
        added, updated, removed = fc.diff(old, new, "id", fields)
        self.assertEqual((added, updated, removed), ([], [], []))


class ModelsTest(unittest.TestCase):
    def _row(self, **kw):
        base = {"id": "PC12", "manufacturer": "PILATUS", "name": "PC-12 Eagle",
                "rareness": 322, "xp": 2610, "firstFlight": 1991, "wingspan": 16.3,
                "maxSpeed": 285, "seats": 9, "mtow": 4740}
        base.update(kw)
        return base

    def test_added_full_stat_sheet(self):
        msg, tldr = fc.format_models([], [self._row()], "L")
        self.assertIn("## \U0001F6A8 Airpedia aircraft update", msg)
        self.assertIn("### Added (1)", msg)
        self.assertIn("`PC12` PILATUS PC-12 Eagle", msg)
        self.assertIn("- Rarity: 3.22 (2610 xp)", msg)
        self.assertIn("- Weight: 4.74T", msg)
        self.assertIn("- Speed: 285kts", msg)
        self.assertIn("- Wingspan: 16.3m", msg)
        self.assertIn("For all changes see [commit](<L>)", msg)
        self.assertIn("- Added (1): `PC12`", msg)
        self.assertIn("- Removed (0): none", msg)

    def test_updated_only_changed_stats(self):
        old = self._row(seats=None, wingspan=9.9)
        new = self._row(seats=2, wingspan=9.91)
        msg, tldr = fc.format_models([old], [new], "L")
        self.assertIn("### Updated (1)", msg)
        self.assertIn("- Wingspan: 9.9m " + fc.ARROW + " 9.91m", msg)
        self.assertIn("- Seats: N/A " + fc.ARROW + " 2", msg)
        self.assertNotIn("- Speed:", msg.split("### Updated")[1])

    def test_na_weight_and_rarity(self):
        msg, _ = fc.format_models([], [self._row(mtow=None, rareness=None)], "L")
        self.assertIn("- Weight: N/A", msg)
        self.assertIn("- Rarity: N/A", msg)

    def test_tldr_counts(self):
        _, tldr = fc.format_models([], [self._row()], "L")
        self.assertEqual(tldr, "Aircraft update: 1 added · 0 updated · 0 removed")

    def test_total_footer(self):
        msg, _ = fc.format_models([], [self._row()], "L")
        self.assertIn("Total aircraft: 1", msg)
        self.assertLess(msg.index("Total aircraft: 1"), msg.index("For all changes see [commit](<L>)"))

    def test_misc_only_non_gameplay_change(self):
        old = self._row(logoId="a")
        new = self._row(logoId="b")
        msg, tldr = fc.format_models([old], [new], "L")
        self.assertIn("Some miscellaneous changes were made to aircraft", msg)
        self.assertIn("View them here: [commit](<L>)", msg)
        self.assertEqual(tldr, "Miscellaneous aircraft changes (non-gameplay)")
        self.assertNotIn("### Added", msg)


class AirportsTest(unittest.TestCase):
    def _ap(self, **kw):
        base = {"id": 1, "iata": "AMS", "icao": "EHAM",
                "name": "Amsterdam Schiphol Airport", "city": "Amsterdam",
                "placeCode": "NL"}
        base.update(kw)
        return base

    def test_added_grouped_with_link(self):
        new = [self._ap()]
        msg, tldr = fc.format_airports([], new, "L")
        self.assertIn("## \U0001F6A8 Airpedia airports update", msg)
        self.assertIn("**EUROPE**", msg)
        self.assertIn("\U0001F1F3\U0001F1F1 Netherlands", msg)
        self.assertIn(
            "  + [Amsterdam Schiphol Airport]"
            "(<https://www.flightradar24.com/data/airports/AMS>) (`AMS`/`EHAM`)",
            msg,
        )
        self.assertIn("- Added (1): `AMS`", msg)

    def test_region_subgrouping_and_no_iata(self):
        jfk = self._ap(id=2, iata="JFK", icao="KJFK",
                       name="John F Kennedy", city="Queens", placeCode="US-NY")
        noiata = self._ap(id=3, iata=None, icao="KXYZ", name="Tiny", placeCode="US-NE")
        msg, _ = fc.format_airports([], [jfk, noiata], "L")
        self.assertIn("**NORTH AMERICA**", msg)
        self.assertIn("  New York", msg)
        self.assertIn(
            "    + [John F Kennedy]"
            "(<https://www.flightradar24.com/data/airports/JFK>) (`JFK`/`KJFK`)",
            msg,
        )
        # Airports without an IATA are not real airports -> dropped entirely.
        self.assertNotIn("Tiny", msg)
        self.assertIn("- Added (1): `JFK`", msg)

    def test_updated_shows_field_changes(self):
        old = self._ap(id=2, iata="JFK", icao="KJFK", name="John F Kennedy",
                       city="Queens", placeCode="US-NY")
        new = self._ap(id=2, iata="JFK", icao="KJFK", name="John F Kennedy",
                       city="New York", placeCode="US-NJ")
        msg, _ = fc.format_airports([old], [new], "L")
        self.assertIn("### Updated (1)", msg)
        self.assertIn("    ~ [John F Kennedy]"
                      "(<https://www.flightradar24.com/data/airports/JFK>) (`JFK`/`KJFK`)", msg)
        self.assertIn("      \\- City: Queens " + fc.ARROW + " New York", msg)
        self.assertIn("      \\- Region: New York " + fc.ARROW + " New Jersey", msg)

    def test_losing_iata_counts_as_removed(self):
        # Upstream never deletes airports; it nulls iata/icao but keeps the id
        # row. Such an airport is effectively removed, not a silent update.
        old = self._ap(id=9, iata="ZAJ", icao="OAZJ", name="Zaranj Airport",
                       placeCode="AF")
        new = self._ap(id=9, iata=None, icao=None, name="Zaranj Airport",
                       placeCode="AF")
        msg, tldr = fc.format_airports([old], [new], "L")
        self.assertIn("### Removed (1)", msg)
        self.assertIn(
            "Zaranj Airport]"
            "(<https://www.flightradar24.com/data/airports/ZAJ>) (`ZAJ`/`OAZJ`)",
            msg,
        )
        self.assertIn("- Removed (1): `ZAJ`", msg)
        self.assertEqual(tldr, "Airports update: 0 added · 0 updated · 1 removed")

    def test_became_major_listed_below_total(self):
        old = self._ap(id=2, iata="AAR", size=100)
        new = self._ap(id=2, iata="AAR", size=fc.AIRPORT_MAJOR_SIZE + 1)
        msg, _ = fc.format_airports([old], [new], "L")
        self.assertIn("### Unlockable airports changes", msg)
        self.assertIn("Became major: `AAR`", msg)
        self.assertNotIn("Became minor:", msg)
        # The section sits below the TOTAL block.
        self.assertLess(msg.index("### TOTAL"),
                        msg.index("### Unlockable airports changes"))

    def test_became_minor_listed(self):
        old = self._ap(id=2, iata="ASW", size=fc.AIRPORT_MAJOR_SIZE + 1)
        new = self._ap(id=2, iata="ASW", size=100)
        msg, _ = fc.format_airports([old], [new], "L")
        self.assertIn("Became minor: `ASW`", msg)
        self.assertNotIn("Became major:", msg)

    def test_threshold_is_major_inclusive(self):
        # size == threshold counts as major.
        old = self._ap(id=2, iata="AAR", size=fc.AIRPORT_MAJOR_SIZE - 1)
        new = self._ap(id=2, iata="AAR", size=fc.AIRPORT_MAJOR_SIZE)
        msg, _ = fc.format_airports([old], [new], "L")
        self.assertIn("Became major: `AAR`", msg)

    def test_size_transition_alone_is_not_misc(self):
        # A category change with no other tracked field change still produces a
        # real message, not the "miscellaneous" notice.
        old = self._ap(id=2, iata="AAR", size=100)
        new = self._ap(id=2, iata="AAR", size=fc.AIRPORT_MAJOR_SIZE + 1)
        msg, tldr = fc.format_airports([old], [new], "L")
        self.assertNotIn("miscellaneous", msg)
        self.assertIn("Became major: `AAR`", msg)

    def test_no_section_when_no_transition(self):
        old = self._ap(id=2, iata="AAR", size=100, name="Old")
        new = self._ap(id=2, iata="AAR", size=200, name="New")
        msg, _ = fc.format_airports([old], [new], "L")
        self.assertNotIn("Unlockable airports changes", msg)

    def test_refilled_iata_counts_as_added(self):
        # An airport that regains an IATA (was null) is treated as newly added.
        old = self._ap(id=2, iata=None, icao="KXYZ", name="Reborn", placeCode="US-NY")
        new = self._ap(id=2, iata="RBN", icao="KXYZ", name="Reborn", placeCode="US-NY")
        msg, tldr = fc.format_airports([old], [new], "L")
        self.assertIn("### Added (1)", msg)
        self.assertIn("- Added (1): `RBN`", msg)
        self.assertEqual(tldr, "Airports update: 1 added · 0 updated · 0 removed")

    def test_total_footer(self):
        msg, _ = fc.format_airports([], [self._ap()], "L")
        self.assertIn("Total airports: 1", msg)

    def test_misc_only_non_gameplay_change(self):
        old = self._ap(distance=10)
        new = self._ap(distance=20)
        msg, tldr = fc.format_airports([old], [new], "L")
        self.assertIn("Some miscellaneous changes were made to airports", msg)
        self.assertEqual(tldr, "Miscellaneous airports changes (non-gameplay)")
        self.assertNotIn("### Added", msg)

    def test_caption_lists_iata_codes_per_category(self):
        # The Discord file-attachment caption breaks the one-line tldr into a
        # per-category code list (commit body keeps the terse tldr).
        old = self._ap(id=1, iata="AMS", icao="EHAM")
        jfk = self._ap(id=2, iata="JFK", icao="KJFK", name="JFK", placeCode="US-NY")
        caption = fc.airports_caption([old], [old, jfk])
        self.assertEqual(
            caption,
            "- Added (1): `JFK`\n- Updated (0): none\n- Removed (0): none",
        )


class FleetsTest(unittest.TestCase):
    def _al(self, **kw):
        base = {"id": 1, "iata": "LH", "icao": "DLH", "name": "Lufthansa",
                "placeCode": "DE", "fleet": list(range(320))}
        base.update(kw)
        return base

    def test_added_link_and_aircraft(self):
        msg, tldr = fc.format_fleets([], [self._al()], "L")
        self.assertIn("## \U0001F6A8 Airpedia fleets update", msg)
        self.assertIn("\U0001F1E9\U0001F1EA Germany", msg)
        self.assertIn(
            "  + [Lufthansa]"
            "(<https://www.flightradar24.com/data/airlines/lh-dlh/fleet>) (`LH`/`DLH`)",
            msg,
        )
        self.assertIn("    \\- Aircraft: 320", msg)
        self.assertIn("- Added (1): `DLH`", msg)

    def test_null_iata_uses_icao_link(self):
        al = self._al(id=2, iata=None, icao="NAX", name="Norwegian", placeCode="NO",
                      fleet=[1, 2])
        msg, _ = fc.format_fleets([], [al], "L")
        self.assertIn(
            "  + [Norwegian]"
            "(<https://www.flightradar24.com/data/airlines/nax/fleet>) (`NAX`)",
            msg,
        )

    def test_updated_fleet_count(self):
        old = self._al(fleet=list(range(250)))
        new = self._al(fleet=list(range(255)))
        msg, _ = fc.format_fleets([old], [new], "L")
        self.assertIn("### Updated (1)", msg)
        self.assertIn("    \\- Aircraft: 250 " + fc.ARROW + " 255", msg)

    def test_emptied_fleet_counts_as_removed(self):
        # A fleet dropping to 0 aircraft is effectively gone, not an update.
        old = self._al(fleet=list(range(3)))
        new = self._al(fleet=[])
        msg, tldr = fc.format_fleets([old], [new], "L")
        self.assertIn("### Removed (1)", msg)
        self.assertIn("- Removed (1): `DLH`", msg)
        self.assertNotIn("### Updated (1)", msg)
        self.assertEqual(tldr, "Fleets update: 0 added · 0 updated · 1 removed")

    def test_refilled_fleet_counts_as_added(self):
        # A fleet climbing back to >=1 aircraft is treated as newly added.
        old = self._al(fleet=[])
        new = self._al(fleet=list(range(2)))
        msg, tldr = fc.format_fleets([old], [new], "L")
        self.assertIn("### Added (1)", msg)
        self.assertIn("- Added (1): `DLH`", msg)
        self.assertEqual(tldr, "Fleets update: 1 added · 0 updated · 0 removed")

    def test_always_empty_fleet_ignored(self):
        old = self._al(fleet=[])
        new = self._al(fleet=[], name="Renamed")
        msg, tldr = fc.format_fleets([old], [new], "L")
        self.assertIn("Some miscellaneous changes were made to fleets", msg)

    def test_total_footer(self):
        msg, _ = fc.format_fleets([], [self._al()], "L")
        self.assertIn("Total fleets: 1", msg)

    def test_misc_only_non_gameplay_change(self):
        old = self._al(logoId="a")
        new = self._al(logoId="b")
        msg, tldr = fc.format_fleets([old], [new], "L")
        self.assertIn("Some miscellaneous changes were made to fleets", msg)
        self.assertEqual(tldr, "Miscellaneous fleets changes (non-gameplay)")
        self.assertNotIn("### Added", msg)


class ComparisonTest(unittest.TestCase):
    def _country(self, name, iso, added=None, removed=None, fr24=0, sky=0):
        return {iso: {"country_name": name, "iso_code": iso,
                      "fr24_count": fr24, "skycards_count": sky,
                      "added_airports": added or [], "removed_airports": removed or []}}

    def _ap(self, name, iata, icao):
        return {"name": name, "iata": iata, "icao": icao,
                "link": f"https://www.flightradar24.com/data/airports/{(iata or icao).lower()}"}

    def test_new_to_be_added_listed(self):
        old = {"countries": {}}
        new = {"countries": self._country("Netherlands", "NL",
                                          added=[self._ap("Schiphol", "AMS", "EHAM")])}
        msg, tldr = fc.format_comparison(old, new, set(), set(), "L")
        self.assertIn("## \U0001F6A8 Airpedia airport comparison update", msg)
        self.assertIn("**To be added** (new)", msg)
        self.assertIn("  + [Schiphol]", msg)
        self.assertIn("**OVERALL**", msg)
        self.assertIn("To be added: 1 · To be removed: 0 · 1 countries", msg)
        self.assertIn("1 to add", tldr)

    def test_new_to_be_removed_listed(self):
        old = {"countries": {}}
        new = {"countries": self._country("Australia", "AU",
                                          removed=[self._ap("Old Field", "OLD", "YOLD")])}
        msg, _ = fc.format_comparison(old, new, {"OLD"}, {"OLD"}, "L")
        self.assertIn("**To be removed** (new)", msg)
        self.assertIn("  \\- [Old Field]", msg)

    def test_skycards_caught_up_is_resolved_not_listed(self):
        old = {"countries": self._country("Netherlands", "NL",
                                          added=[self._ap("Schiphol", "AMS", "EHAM")])}
        new = {"countries": {}}
        msg, _ = fc.format_comparison(old, new, set(), {"AMS"}, "L")
        self.assertIn("✓ 1 resolved this update (see the airports update)", msg)
        self.assertNotIn("Schiphol", msg)

    def test_still_to_be_added_on_skycards_update(self):
        old = {"countries": self._country("Netherlands", "NL",
                                          added=[self._ap("Schiphol", "AMS", "EHAM")])}
        new = {"countries": self._country("Brazil", "BR",
                                          added=[self._ap("Novo", "NVO", "SBNV")])}
        msg, _ = fc.format_comparison(old, new, set(), {"AMS"}, "L")
        self.assertIn("**Still to be added**", msg)
        self.assertIn("  + [Novo]", msg)

    def test_still_to_be_added_omitted_when_empty(self):
        # Skycards-driven cycle (AMS now present) but nothing left to add.
        old = {"countries": self._country("Netherlands", "NL",
                                          added=[self._ap("Schiphol", "AMS", "EHAM")])}
        new = {"countries": {}}
        msg, _ = fc.format_comparison(old, new, set(), {"AMS"}, "L")
        self.assertIn("✓ 1 resolved this update", msg)
        self.assertNotIn("**Still to be added**", msg)

    def test_count_only_change_section(self):
        old = {"countries": self._country("United States", "US", fr24=10, sky=5)}
        new = {"countries": self._country("United States", "US", fr24=19, sky=5)}
        msg, tldr = fc.format_comparison(old, new, set(), set(), "L")
        self.assertIn("**Count changes** (not yet detailed)", msg)
        self.assertIn("United States of America +9", msg)
        self.assertNotIn("**Still to be added**", msg)
        self.assertIn("1 count", tldr)

    def test_suppress_when_nothing_changed(self):
        same = {"countries": self._country("Netherlands", "NL",
                                           added=[self._ap("Schiphol", "AMS", "EHAM")],
                                           fr24=1, sky=0)}
        msg, tldr = fc.format_comparison(same, same, set(), set(), "L")
        self.assertEqual(msg, "")
        self.assertEqual(tldr, "")

    def test_first_run_baseline(self):
        new = {"countries": self._country("Netherlands", "NL",
                                          added=[self._ap("Schiphol", "AMS", "EHAM")])}
        msg, tldr = fc.format_comparison(None, new, set(), set(), "L")
        self.assertIn("airport comparison baseline", msg)
        self.assertIn("To be added: 1 · To be removed: 0 · 1 countries", msg)
        self.assertNotIn("**To be added** (new)", msg)


class ComparisonHelpersTest(unittest.TestCase):
    def _diffs(self, added=None, removed=None, fr24=0, sky=0):
        return {"countries": {"NL": {
            "country_name": "Netherlands", "iso_code": "NL",
            "fr24_count": fr24, "skycards_count": sky,
            "added_airports": added or [], "removed_airports": removed or []}}}

    def test_airport_idents_union_iata_icao(self):
        data = {"rows": [{"iata": "AMS", "icao": "EHAM"}, {"iata": None, "icao": "EHRD"}]}
        self.assertEqual(fc._airport_idents(data), {"AMS", "EHAM", "EHRD"})
        self.assertEqual(fc._airport_idents(None), set())

    def test_cmp_index_keys_by_identity(self):
        diffs = self._diffs(added=[{"name": "A", "iata": "AMS", "icao": "EHAM"},
                                   {"name": "B", "iata": None, "icao": "EHRD"}])
        idx = fc._cmp_index(diffs, "added_airports")
        self.assertEqual(set(idx), {"AMS", "EHRD"})

    def test_classify_fr24_added_is_new_item(self):
        old = {}
        new = {"AMS": {"name": "Schiphol", "iata": "AMS", "icao": "EHAM",
                       "placeCode": "NL", "link": None}}
        new_recs, resolved, sky = fc._classify_side(old, new, set(), set())
        self.assertEqual([r["iata"] for r in new_recs], ["AMS"])
        self.assertEqual((resolved, sky), (0, 0))

    def test_classify_skycards_caught_up_is_resolved(self):
        old = {"AMS": {"name": "Schiphol", "iata": "AMS", "icao": "EHAM",
                       "placeCode": "NL", "link": None}}
        new = {}
        new_recs, resolved, sky = fc._classify_side(old, new, set(), {"AMS"})
        self.assertEqual(new_recs, [])
        self.assertEqual((resolved, sky), (1, 1))

    def test_classify_fr24_dropped_is_resolved_not_skycards(self):
        old = {"AMS": {"name": "X", "iata": "AMS", "icao": "EHAM",
                       "placeCode": "NL", "link": None}}
        new = {}
        new_recs, resolved, sky = fc._classify_side(old, new, set(), set())
        self.assertEqual((resolved, sky), (1, 0))

    def test_count_only_reports_net_delta(self):
        old = self._diffs(fr24=10, sky=5)
        new = self._diffs(fr24=14, sky=5)
        self.assertEqual(fc._count_only(old, new), [("NL", 4)])

    def test_count_only_skips_when_list_changed(self):
        old = self._diffs(added=[{"iata": "AMS", "icao": "EHAM"}], fr24=10, sky=5)
        new = self._diffs(added=[], fr24=14, sky=5)
        self.assertEqual(fc._count_only(old, new), [])

    def test_overall_counts(self):
        diffs = {"countries": {
            "NL": {"added_airports": [{"iata": "AMS"}], "removed_airports": []},
            "AU": {"added_airports": [], "removed_airports": [{"iata": "OLD"}]},
            "DE": {"added_airports": [{"iata": "BER"}, {"iata": "MUC"}],
                   "removed_airports": []}}}
        self.assertEqual(fc._overall(diffs), (3, 1, 3))


import io
import json
import tempfile
from contextlib import redirect_stdout


class CliTest(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = fc.main(argv)
        return rc, out.getvalue().strip()

    def test_models_cli_writes_message_and_prints_tldr(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.json")
            new = os.path.join(d, "new.json")
            out = os.path.join(d, "msg.md")
            row = {"id": "PC12", "manufacturer": "PILATUS", "name": "PC-12 Eagle",
                   "rareness": 322, "xp": 2610, "mtow": 4740, "maxSpeed": 285,
                   "wingspan": 16.3, "seats": 9, "firstFlight": 1991}
            json.dump({"rows": []}, open(old, "w"))
            json.dump({"rows": [row]}, open(new, "w"))
            rc, tldr = self._run(["--type", "models", "--old", old, "--new", new,
                                  "--link", "L", "--out", out])
            self.assertEqual(rc, 0)
            self.assertEqual(tldr, "Aircraft update: 1 added · 0 updated · 0 removed")
            self.assertIn("`PC12` PILATUS PC-12 Eagle", open(out).read())

    def test_first_run_empty_old_simple_message(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.json")
            new = os.path.join(d, "new.json")
            out = os.path.join(d, "msg.md")
            open(old, "w").write("")  # empty -> first run
            json.dump([{"id": 1, "icao": "DLH", "name": "LH", "placeCode": "DE",
                        "fleet": []}], open(new, "w"))
            rc, tldr = self._run(["--type", "airlines", "--old", old, "--new", new,
                                  "--link", "L", "--out", out])
            self.assertEqual(rc, 0)
            self.assertEqual(tldr, "Fleets data published")
            self.assertIn("Airpedia fleets data published", open(out).read())

    def test_comparison_cli_old_new_airports(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old_diff.json")
            new = os.path.join(d, "new_diff.json")
            old_ap = os.path.join(d, "old_ap.json")
            new_ap = os.path.join(d, "new_ap.json")
            out = os.path.join(d, "msg.md")
            country = {"countries": {"NL": {
                "country_name": "Netherlands", "iso_code": "NL",
                "fr24_count": 1, "skycards_count": 0,
                "added_airports": [{"name": "Schiphol", "iata": "AMS", "icao": "EHAM",
                                    "link": "https://www.flightradar24.com/data/airports/ams"}],
                "removed_airports": []}}}
            json.dump({"countries": {}}, open(old, "w"))
            json.dump(country, open(new, "w"))
            json.dump({"rows": []}, open(old_ap, "w"))
            json.dump({"rows": []}, open(new_ap, "w"))
            rc, tldr = self._run(["--type", "comparison", "--old", old, "--new", new,
                                  "--old-airports", old_ap, "--airports", new_ap,
                                  "--link", "L", "--out", out])
            self.assertEqual(rc, 0)
            self.assertIn("1 to add", tldr)
            self.assertIn("**To be added** (new)", open(out).read())

    def test_meta_out_flags_misc_true(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.json")
            new = os.path.join(d, "new.json")
            out = os.path.join(d, "msg.md")
            meta = os.path.join(d, "meta.txt")
            row = {"id": "PC12", "name": "PC-12", "logoId": 1}
            json.dump({"rows": [row]}, open(old, "w"))
            json.dump({"rows": [dict(row, logoId=2)]}, open(new, "w"))
            self._run(["--type", "models", "--old", old, "--new", new,
                       "--link", "L", "--out", out, "--meta-out", meta])
            self.assertEqual(open(meta).read(), "true")

    def test_meta_out_flags_misc_false_for_real_change(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.json")
            new = os.path.join(d, "new.json")
            out = os.path.join(d, "msg.md")
            meta = os.path.join(d, "meta.txt")
            row = {"id": "PC12", "name": "PC-12", "seats": 9}
            json.dump({"rows": [row]}, open(old, "w"))
            json.dump({"rows": [dict(row, seats=10)]}, open(new, "w"))
            self._run(["--type", "models", "--old", old, "--new", new,
                       "--link", "L", "--out", out, "--meta-out", meta])
            self.assertEqual(open(meta).read(), "false")

    def _ap_doc(self, **kw):
        base = {"id": 1, "iata": "AMS", "icao": "EHAM", "name": "AMS",
                "placeCode": "NL"}
        base.update(kw)
        return base

    def test_caption_out_writes_code_breakdown_for_airports(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.json")
            new = os.path.join(d, "new.json")
            out = os.path.join(d, "msg.md")
            cap = os.path.join(d, "cap.txt")
            json.dump({"rows": [self._ap_doc()]}, open(old, "w"))
            json.dump({"rows": [self._ap_doc(),
                                self._ap_doc(id=2, iata="JFK", icao="KJFK",
                                             name="JFK", placeCode="US-NY")]},
                      open(new, "w"))
            rc, tldr = self._run(["--type", "airports", "--old", old, "--new", new,
                                  "--link", "L", "--out", out, "--caption-out", cap])
            self.assertEqual(rc, 0)
            self.assertEqual(tldr, "Airports update: 1 added · 0 updated · 0 removed")
            self.assertEqual(
                open(cap).read().strip(),
                "- Added (1): `JFK`\n- Updated (0): none\n- Removed (0): none",
            )

    def test_caption_out_falls_back_to_tldr_for_models(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.json")
            new = os.path.join(d, "new.json")
            out = os.path.join(d, "msg.md")
            cap = os.path.join(d, "cap.txt")
            row = {"id": "PC12", "name": "PC-12", "seats": 9}
            json.dump({"rows": [row]}, open(old, "w"))
            json.dump({"rows": [dict(row, seats=10)]}, open(new, "w"))
            rc, tldr = self._run(["--type", "models", "--old", old, "--new", new,
                                  "--link", "L", "--out", out, "--caption-out", cap])
            self.assertEqual(rc, 0)
            self.assertEqual(open(cap).read().strip(), tldr)


if __name__ == "__main__":
    unittest.main()
