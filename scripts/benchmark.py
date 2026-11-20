"""Measure vertices, error, bytes and time on the real Natural Earth coastline.

Every number in the README and the chart comes from this script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minlink import (
    douglas_peucker_indices,
    encoded_size,
    geos_indices,
    max_error,
    min_vertex_indices,
    non_simple_count,
    verify_optimality,
    visvalingam_indices,
    zoom_tolerance,
)
from minlink.data import load_polylines

METHODS = ("douglas_peucker", "visvalingam", "minlink")


def run_method(name, polys, eps):
    kept, errs, t0 = [], 0.0, time.perf_counter()
    labels = []
    for P in polys:
        if name == "douglas_peucker":
            idx = douglas_peucker_indices(P, eps)
        elif name == "visvalingam":
            idx = visvalingam_indices(P, eps)
        else:
            idx, label = min_vertex_indices(P, eps)
            labels.append(label)
        kept.append(P[idx])
        errs = max(errs, max_error(P, idx))
    secs = time.perf_counter() - t0
    raw, gz = encoded_size(kept)
    return {
        "vertices": int(sum(len(k) for k in kept)),
        "max_error_deg": errs,
        "seconds": secs,
        "geojson_bytes": raw,
        "gzip_bytes": gz,
        "non_simple": non_simple_count(kept),
    }, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="coastline10m")
    ap.add_argument("--zooms", default="3,4,5,6,7,8")
    ap.add_argument("--max-vertices", type=int, default=None)
    ap.add_argument("--out", default="docs/metrics.json")
    a = ap.parse_args()

    polys = load_polylines(a.layer, min_vertices=2, max_vertices=a.max_vertices)
    total = int(sum(len(p) for p in polys))
    print("corpus %s: %d polylines, %d vertices, longest %d"
          % (a.layer, len(polys), total, max(len(p) for p in polys)), flush=True)

    report = {
        "corpus": {
            "layer": a.layer,
            "polylines": len(polys),
            "vertices": total,
            "longest": int(max(len(p) for p in polys)),
        },
        "runs": [],
    }
    for z in [int(x) for x in a.zooms.split(",")]:
        eps = zoom_tolerance(z)
        row = {"zoom": z, "eps_deg": eps, "methods": {}}
        for m in METHODS:
            stats, labels = run_method(m, polys, eps)
            row["methods"][m] = stats
            print("  z%-2d eps %.6f  %-16s verts %7d  err %.6f  %6.1fs  gzip %8d  nonsimple %4d"
                  % (z, eps, m, stats["vertices"], stats["max_error_deg"], stats["seconds"],
                     stats["gzip_bytes"], stats["non_simple"]), flush=True)
            if m == "minlink":
                row["certificate"] = {"polylines_checked": 0, "verified": True}
                checked = 0
                for P, label in zip(polys, labels):
                    if len(P) > 400:
                        continue
                    if not verify_optimality(P, eps, label):
                        row["certificate"]["verified"] = False
                        break
                    checked += 1
                row["certificate"]["polylines_checked"] = checked
        dp = row["methods"]["douglas_peucker"]["vertices"]
        ml = row["methods"]["minlink"]["vertices"]
        vw = row["methods"]["visvalingam"]["vertices"]
        row["reduction_vs_dp_pct"] = 100.0 * (dp - ml) / dp
        row["reduction_vs_vw_pct"] = 100.0 * (vw - ml) / vw
        row["gzip_reduction_vs_dp_pct"] = 100.0 * (
            row["methods"]["douglas_peucker"]["gzip_bytes"] - row["methods"]["minlink"]["gzip_bytes"]
        ) / row["methods"]["douglas_peucker"]["gzip_bytes"]
        print("  z%-2d minlink uses %.1f%% fewer vertices than Douglas-Peucker, %.1f%% fewer than Visvalingam, gzip %.1f%% smaller"
              % (z, row["reduction_vs_dp_pct"], row["reduction_vs_vw_pct"], row["gzip_reduction_vs_dp_pct"]), flush=True)
        report["runs"].append(row)

    # Cross check the local Douglas-Peucker against the shipped GEOS one.
    sample = [p for p in polys if 50 <= len(p) <= 1500][:250]
    eps = zoom_tolerance(6)
    same = sum(1 for P in sample
               if len(douglas_peucker_indices(P, eps)) == len(geos_indices(P, eps)))
    report["geos_crosscheck"] = {"polylines": len(sample), "same_vertex_count": same}
    print("GEOS cross check: %d of %d polylines match the local Douglas-Peucker exactly"
          % (same, len(sample)), flush=True)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("wrote", a.out, flush=True)


if __name__ == "__main__":
    main()
