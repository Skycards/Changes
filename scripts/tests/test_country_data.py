import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import country_data as cd  # noqa: E402


class CountryDataTest(unittest.TestCase):
    def test_flag_two_letter(self):
        self.assertEqual(cd.flag("DE"), "\U0001F1E9\U0001F1EA")
        self.assertEqual(cd.flag("nl"), "\U0001F1F3\U0001F1F1")

    def test_flag_invalid(self):
        self.assertEqual(cd.flag("ZZZ"), "")
        self.assertEqual(cd.flag(""), "")

    def test_country_name_and_continent(self):
        self.assertEqual(cd.country_name("NL"), "Netherlands")
        self.assertEqual(cd.continent("NL"), "Europe")
        self.assertEqual(cd.continent("US"), "North America")
        self.assertEqual(cd.continent("BR"), "South America")
        self.assertEqual(cd.continent("AU"), "Oceania")
        self.assertEqual(cd.continent("AO"), "Africa")
        self.assertEqual(cd.continent("CN"), "Asia")

    def test_unknown_country(self):
        self.assertEqual(cd.country_name("ZZ"), "Unknown (ZZ)")
        self.assertEqual(cd.continent("ZZ"), "Unknown")

    def test_parse_place_code_plain(self):
        self.assertEqual(cd.parse_place_code("DE"), ("DE", None))

    def test_parse_place_code_region(self):
        self.assertEqual(cd.parse_place_code("US-NY"), ("US", "New York"))
        self.assertEqual(cd.parse_place_code("CA-ON"), ("CA", "Ontario"))

    def test_parse_place_code_unknown_region(self):
        # Unknown subdivision falls back to the raw region code.
        self.assertEqual(cd.parse_place_code("US-ZZ"), ("US", "ZZ"))

    def test_parse_place_code_empty(self):
        self.assertEqual(cd.parse_place_code(None), ("ZZ", None))

    def test_every_data_country_is_known(self):
        # Every country code present in the shipped data files must resolve.
        import json
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        codes = set()
        with open(os.path.join(root, "airports.json")) as fh:
            for row in json.load(fh)["rows"]:
                codes.add(cd.parse_place_code(row["placeCode"])[0])
        with open(os.path.join(root, "airlines.json")) as fh:
            for row in json.load(fh):
                codes.add(cd.parse_place_code(row["placeCode"])[0])
        missing = sorted(c for c in codes if c not in cd.COUNTRIES and c != "ZZ")
        self.assertEqual(missing, [], f"Unmapped country codes: {missing}")


if __name__ == "__main__":
    unittest.main()
