#!/usr/bin/env python3
"""Regenerate data/ne_50m_admin_1_states.geojson from Natural Earth.

Downloads the 50m admin-1 states/provinces GeoJSON (public domain) and strips
it to the three properties the state lookup needs. Run from the repo root:

    python3 scripts/build_state_boundaries.py

Natural Earth 50m admin-1 covers subdivisions for US, CA, AU, CN (all four
countries Skycards currently subdivides) plus BR, IN, ID, RU, ZA for future
use. Re-run only when Natural Earth ships boundary fixes.
"""
import json
import urllib.request

SOURCE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          "master/geojson/ne_50m_admin_1_states_provinces.geojson")
DEST = "data/ne_50m_admin_1_states.geojson"
KEEP = ("iso_a2", "iso_3166_2", "name")


def main():
    with urllib.request.urlopen(SOURCE, timeout=120) as resp:
        data = json.load(resp)
    features = []
    for feature in data["features"]:
        props = feature["properties"]
        features.append({
            "type": "Feature",
            "properties": {k: props.get(k) for k in KEEP},
            "geometry": feature["geometry"],
        })
    stripped = {"type": "FeatureCollection", "features": features}
    with open(DEST, "w", encoding="utf-8") as fh:
        json.dump(stripped, fh, separators=(",", ":"))
    print(f"wrote {DEST}: {len(features)} features")


if __name__ == "__main__":
    main()
