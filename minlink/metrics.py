"""Measurements that decide whether a simplification is actually cheaper."""

from __future__ import annotations

import gzip
import json

import numpy as np

TILE_PIXELS = 256


def zoom_tolerance(z: int, pixels: float = 1.0) -> float:
    """Degrees of longitude spanned by `pixels` screen pixels at web zoom z.

    Slippy map tiles put the whole 360 degree world in 256 pixels at z0, so a
    one pixel tolerance at zoom z is 360 / (256 * 2**z) degrees. Simplifying
    below that is paying for detail the screen cannot show.
    """
    return pixels * 360.0 / (TILE_PIXELS * (2 ** z))


def encoded_size(features, ndigits: int = 6) -> tuple[int, int]:
    """GeoJSON bytes on disk and after gzip, the way a tile server ships them.

    Reported because a byte win that vanishes under transport compression is
    not a byte win. Dropping vertices removes coordinates outright rather than
    removing redundancy, so most of it survives, but the number is measured
    rather than assumed.
    """
    doc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": np.round(np.asarray(f, dtype=float), ndigits).tolist(),
                },
            }
            for f in features
        ],
    }
    raw = json.dumps(doc, separators=(",", ":")).encode()
    return len(raw), len(gzip.compress(raw, 9))


def non_simple_count(features) -> int:
    """How many output polylines cross themselves.

    Neither Douglas-Peucker nor the exact solver preserves topology, so this is
    tracked for both instead of being claimed away.
    """
    from shapely.geometry import LineString

    bad = 0
    for f in features:
        a = np.asarray(f, dtype=float)
        if len(a) >= 2 and not LineString(a).is_simple:
            bad += 1
    return bad
