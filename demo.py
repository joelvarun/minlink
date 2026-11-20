"""Smallest end to end demo: one real coastline, three simplifiers, one proof.

    python demo.py

Downloads the Natural Earth 1:10m coastline on first run and caches it in data/.
"""

from __future__ import annotations

import time

import numpy as np

from minlink import (
    douglas_peucker_indices,
    max_error,
    min_vertex_indices,
    simplify_to_budget,
    verify_optimality,
    visvalingam_indices,
    zoom_tolerance,
)
from minlink.data import load_polylines


def main() -> None:
    polys = load_polylines("coastline10m")
    polys.sort(key=len, reverse=True)
    # A mid sized real coastline keeps the demo to a few seconds. The full
    # corpus, including the 16538 vertex polyline, is what scripts/benchmark.py
    # measures.
    P = next(p for p in polys if len(p) <= 1200)
    print("coastline polyline: %d vertices (longest in the layer is %d)" % (len(P), len(polys[0])))

    for z in (4, 6, 8):
        eps = zoom_tolerance(z)
        dp = douglas_peucker_indices(P, eps)
        vw = visvalingam_indices(P, eps)
        t0 = time.perf_counter()
        ml, label = min_vertex_indices(P, eps)
        secs = time.perf_counter() - t0
        print("\nzoom %d, tolerance %.5f degrees (one screen pixel)" % (z, eps))
        print("  Douglas-Peucker    %6d vertices, realized error %.6f" % (len(dp), max_error(P, dp)))
        print("  Visvalingam-Whyatt %6d vertices, realized error %.6f" % (len(vw), max_error(P, vw)))
        print("  minlink (exact)    %6d vertices, realized error %.6f, %.1fs"
              % (len(ml), max_error(P, ml), secs))
        print("  minlink keeps %.1f%% fewer vertices than Douglas-Peucker at the same bound"
              % (100.0 * (len(dp) - len(ml)) / len(dp)))

    eps = zoom_tolerance(6)
    small = next(p for p in polys if 150 <= len(p) <= 260)
    idx, label = min_vertex_indices(small, eps)
    print("\noptimality certificate on a %d vertex polyline: %s"
          % (len(small), "verified" if verify_optimality(small, eps, label) else "FAILED"))
    print("  no simplification with fewer than %d vertices meets the %.5f degree bound"
          % (len(idx), eps))

    out, eps_found = simplify_to_budget(P, 200, rounds=16)
    print("\nvertex budget inversion: 200 vertex budget met at tolerance %.6f degrees (%d vertices)"
          % (eps_found, len(out)))
    print("  that is %.1f%% of the original %d vertices" % (100.0 * len(out) / len(P), len(P)))


if __name__ == "__main__":
    main()
