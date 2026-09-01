import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import state_lookup as sl

# Two unit squares side by side acting as "states" of country XX, one with a
# hole, plus one square for country YY at the same coordinates as XX-B.
FIXTURE = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "properties": {"iso_a2": "XX", "iso_3166_2": "XX-A", "name": "Alpha"},
         "geometry": {"type": "Polygon", "coordinates": [
             [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
             [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]],
         ]}},
        {"type": "Feature",
         "properties": {"iso_a2": "XX", "iso_3166_2": "XX-B", "name": "Beta"},
         "geometry": {"type": "MultiPolygon", "coordinates": [
             [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
         ]}},
        {"type": "Feature",
         "properties": {"iso_a2": "YY", "iso_3166_2": "YY-Z", "name": "Zeta"},
         "geometry": {"type": "Polygon", "coordinates": [
             [[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]],
         ]}},
    ],
}


class StateLookupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lookup = sl.StateLookup(FIXTURE)

    def test_point_inside_polygon(self):
        self.assertEqual(self.lookup.lookup(0.2, 0.2, "XX"), "XX-A")

    def test_point_inside_multipolygon(self):
        self.assertEqual(self.lookup.lookup(1.5, 0.5, "XX"), "XX-B")

    def test_point_in_hole_snaps_to_nearest_boundary(self):
        # Center of XX-A's hole: not inside any ring, but the hole's edge is
        # ~0.1 deg away, well under the snap cap.
        self.assertEqual(self.lookup.lookup(0.5, 0.5, "XX"), "XX-A")

    def test_country_filter_excludes_other_countries(self):
        # Same coordinates resolve per requested country.
        self.assertEqual(self.lookup.lookup(1.5, 0.5, "YY"), "YY-Z")

    def test_point_just_offshore_snaps_to_nearest(self):
        self.assertEqual(self.lookup.lookup(-0.05, 0.5, "XX"), "XX-A")

    def test_point_far_from_country_returns_none(self):
        # ~10 degrees away: beyond MAX_SNAP_KM.
        self.assertIsNone(self.lookup.lookup(10.0, 10.0, "XX"))

    def test_unknown_country_returns_none(self):
        self.assertIsNone(self.lookup.lookup(0.5, 0.5, "ZZ"))

    def test_state_name(self):
        self.assertEqual(self.lookup.state_name("XX-A"), "Alpha")
        self.assertEqual(self.lookup.state_name("QQ-QQ"), "QQ-QQ")


class RealDataTest(unittest.TestCase):
    """Spot checks against the committed boundaries file."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "data", "ne_50m_admin_1_states.geojson")
        cls.lookup = sl.load_state_lookup(path)

    def test_jfk_is_new_york(self):
        self.assertEqual(self.lookup.lookup(-73.7781, 40.6413, "US"), "US-NY")

    def test_sydney_is_new_south_wales(self):
        self.assertEqual(self.lookup.lookup(151.1753, -33.9399, "AU"), "AU-NSW")

    def test_beijing_capital_is_beijing(self):
        self.assertEqual(self.lookup.lookup(116.5846, 40.0801, "CN"), "CN-BJ")

    def test_coastal_boston_logan_snaps_to_massachusetts(self):
        # Sits on landfill outside the simplified 50m coastline; exercises the
        # nearest-boundary fallback.
        self.assertEqual(self.lookup.lookup(-71.0064, 42.3630, "US"), "US-MA")

    def test_norfolk_island_returns_none(self):
        # Remote AU territory absent from NE admin-1; beyond the snap cap.
        self.assertIsNone(self.lookup.lookup(167.9386, -29.0408, "AU"))


if __name__ == "__main__":
    unittest.main()
