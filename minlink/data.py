"""Real coastline geometry, cached locally.

Natural Earth is the standard public basemap vector set and the usual benchmark
for line simplification. The 1:10m coastline layer is 4133 polylines and about
411 thousand vertices, which is a real tile workload rather than a toy.
"""

from __future__ import annotations

import json
import os
import urllib.request

import numpy as np

SOURCES = {
    "coastline10m": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson",
    "coastline50m": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_coastline.geojson",
    "rivers10m": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_rivers_lake_centerlines.geojson",
}

CACHE_DIR = os.environ.get("MINLINK_CACHE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))


def cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name + ".geojson")


def fetch(name: str = "coastline10m", timeout: float = 180.0) -> str:
    """Download a layer once and reuse the cached copy afterwards."""
    if name not in SOURCES:
        raise KeyError("unknown layer %r, choose from %s" % (name, sorted(SOURCES)))
    path = cache_path(name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    with urllib.request.urlopen(SOURCES[name], timeout=timeout) as r:
        blob = r.read()
    with open(path, "wb") as f:
        f.write(blob)
    return path


def load_polylines(name: str = "coastline10m", min_vertices: int = 2,
                   max_vertices: int | None = None) -> list[np.ndarray]:
    """Every LineString of a layer as an (n, 2) array of lon, lat degrees."""
    with open(fetch(name), "rb") as f:
        doc = json.load(f)
    out = []
    for feat in doc["features"]:
        geom = feat.get("geometry") or {}
        parts = []
        if geom.get("type") == "LineString":
            parts = [geom["coordinates"]]
        elif geom.get("type") == "MultiLineString":
            parts = geom["coordinates"]
        for part in parts:
            a = np.asarray(part, dtype=float)
            if a.ndim != 2 or len(a) < min_vertices:
                continue
            if max_vertices is not None and len(a) > max_vertices:
                continue
            out.append(np.ascontiguousarray(a[:, :2]))
    return out
