#!/usr/bin/env python3
"""Point-in-polygon state lookup against Natural Earth admin-1 boundaries.

Used to attribute a state/province placeCode (e.g. "US-AK") to airports that
exist in FR24's data but not yet in ours, from their FR24 coordinates. Matched
airports never need this — their placeCode comes from our own data.

Accuracy measured against all 2,879 state-qualified airports in airports.json:
US 99.94%, CA 99.72%, AU 99.37%, CN 100%. Points outside every polygon (the
50m coastline is simplified, so coastal airports often are) snap to the
nearest boundary vertex of the requested country, capped at MAX_SNAP_KM so a
remote island (Norfolk, Christmas Island) degrades to None — callers then fall
back to the bare country placeCode.
"""
import json
import math
from typing import Dict, List, Optional, Tuple

# A point farther than this from every polygon of its country gets no state.
# Measured legitimate snaps (coastal airports) top out at ~83 km.
MAX_SNAP_KM = 100.0

_KM_PER_DEG = 111.0


def _ring_contains(lon: float, lat: float, ring: List[List[float]]) -> bool:
    """Ray-casting point-in-ring test."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and \
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class StateLookup:
    def __init__(self, geojson: Dict):
        # Per country: list of (iso_3166_2, bbox, outer_ring, hole_rings).
        self._by_country: Dict[str, List[Tuple]] = {}
        self._names: Dict[str, str] = {}
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            country = props.get("iso_a2")
            code = props.get("iso_3166_2")
            geometry = feature.get("geometry") or {}
            if not country or not code or not geometry:
                continue
            if props.get("name"):
                self._names[code] = props["name"]
            if geometry["type"] == "Polygon":
                polygons = [geometry["coordinates"]]
            elif geometry["type"] == "MultiPolygon":
                polygons = geometry["coordinates"]
            else:
                continue
            entries = self._by_country.setdefault(country, [])
            for rings in polygons:
                outer = rings[0]
                xs = [p[0] for p in outer]
                ys = [p[1] for p in outer]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                entries.append((code, bbox, outer, rings[1:]))

    def lookup(self, lon: float, lat: float, country: str) -> Optional[str]:
        """iso_3166_2 code (e.g. "US-NY") for a coordinate, or None."""
        entries = self._by_country.get(country)
        if not entries:
            return None
        for code, (x0, y0, x1, y1), outer, holes in entries:
            if x0 <= lon <= x1 and y0 <= lat <= y1 \
                    and _ring_contains(lon, lat, outer) \
                    and not any(_ring_contains(lon, lat, h) for h in holes):
                return code
        return self._nearest(lon, lat, entries)

    def _nearest(self, lon: float, lat: float, entries: List[Tuple]) -> Optional[str]:
        """Nearest boundary vertex within MAX_SNAP_KM, else None."""
        best_code, best_d2 = None, (MAX_SNAP_KM / _KM_PER_DEG) ** 2
        cos_lat = math.cos(math.radians(lat))
        for code, (x0, y0, x1, y1), outer, _holes in entries:
            margin = MAX_SNAP_KM / _KM_PER_DEG
            if not (x0 - margin <= lon <= x1 + margin
                    and y0 - margin <= lat <= y1 + margin):
                continue
            for x, y in outer:
                d2 = (y - lat) ** 2 + ((x - lon) * cos_lat) ** 2
                if d2 < best_d2:
                    best_d2, best_code = d2, code
        return best_code

    def state_name(self, code: str) -> str:
        return self._names.get(code, code)


def load_state_lookup(path: str) -> StateLookup:
    with open(path, "r", encoding="utf-8") as fh:
        return StateLookup(json.load(fh))
