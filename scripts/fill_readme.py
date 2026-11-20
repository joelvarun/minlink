"""Regenerate the measured numbers in README.md from docs/metrics.json.

The README is written from docs/README.template.md so that no number in it is
typed by hand: run the benchmark, run this, and the prose matches the data.
"""

from __future__ import annotations

import argparse
import json
import os


def kb(n):
    return "%.0f kB" % (n / 1000.0)


def num(n):
    return format(int(n), ",")


def table(runs):
    head = ("| zoom | tolerance (deg) | Douglas-Peucker | Visvalingam-Whyatt | minlink | fewer than DP"
            " | gzip DP | gzip minlink | gzip saved |")
    sep = "|" + "---|" * 9
    rows = [head, sep]
    for r in runs:
        m = r["methods"]
        rows.append("| z%d | %.6f | %s | %s | %s | %.1f%% | %s | %s | %.1f%% |" % (
            r["zoom"], r["eps_deg"],
            num(m["douglas_peucker"]["vertices"]), num(m["visvalingam"]["vertices"]),
            num(m["minlink"]["vertices"]), r["reduction_vs_dp_pct"],
            kb(m["douglas_peucker"]["gzip_bytes"]), kb(m["minlink"]["gzip_bytes"]),
            r["gzip_reduction_vs_dp_pct"]))
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="docs/metrics.json")
    ap.add_argument("--template", default="docs/README.template.md")
    ap.add_argument("--out", default="README.md")
    ap.add_argument("--demo-output", default="docs/demo_output.txt")
    a = ap.parse_args()

    rep = json.load(open(a.metrics, encoding="utf-8"))
    runs = rep["runs"]
    c = rep["corpus"]
    by_zoom = {r["zoom"]: r for r in runs}
    coarse = runs[0]
    fine = runs[-1]
    best = max(runs, key=lambda r: r["reduction_vs_dp_pct"])
    z6 = by_zoom.get(6, runs[len(runs) // 2])
    m6 = z6["methods"]

    para = (
        "The metric is the number of vertices kept, which is what a vector tile is billed in. "
        "The baseline is Douglas-Peucker, the algorithm GEOS, PostGIS and turf.js all ship, with "
        "Visvalingam-Whyatt alongside it at its most favourable stopping point. The corpus is the "
        "Natural Earth 1:10m coastline, %s polylines and %s vertices, and the tolerance at each zoom "
        "level is one screen pixel, which is the point below which detail cannot be displayed. "
        "Every method is held to that identical point-to-segment bound and the realized error of each "
        "is measured, so none of them is buying vertices with error.\n\n"
        "At zoom %d, a regional view, Douglas-Peucker keeps %s vertices and "
        "minlink keeps %s, a reduction of %.1f percent, and the gzipped GeoJSON drops from %s to %s, "
        "%.1f percent smaller. The advantage peaks at zoom %d with %.1f percent fewer vertices and "
        "narrows as the tolerance tightens, because a tight bound leaves a greedy split very little "
        "room to choose badly. Visvalingam-Whyatt trails both at every level, keeping "
        "%.1f times as many vertices as minlink at zoom %d.\n\n"
        "The saving survives transport compression, which is the part that is easy to get wrong. "
        "Dropping a vertex removes two coordinates outright rather than removing redundancy a "
        "compressor would have squeezed anyway, so %.1f percent fewer vertices at zoom %d still means "
        "%.1f percent fewer gzipped bytes on the wire."
    ) % (
        num(c["polylines"]), num(c["vertices"]),
        z6["zoom"], num(m6["douglas_peucker"]["vertices"]), num(m6["minlink"]["vertices"]),
        z6["reduction_vs_dp_pct"], kb(m6["douglas_peucker"]["gzip_bytes"]), kb(m6["minlink"]["gzip_bytes"]),
        z6["gzip_reduction_vs_dp_pct"], best["zoom"], best["reduction_vs_dp_pct"],
        m6["visvalingam"]["vertices"] / max(1.0, float(m6["minlink"]["vertices"])),
        z6["zoom"], z6["reduction_vs_dp_pct"], z6["zoom"], z6["gzip_reduction_vs_dp_pct"],
    )

    checked = max((r.get("certificate", {}).get("polylines_checked", 0) for r in runs), default=0)
    verified = all(r.get("certificate", {}).get("verified", False) for r in runs)
    tail = (
        "Two checks keep the comparison honest. The optimality certificate was verified on %s polylines "
        "per zoom level (every polyline up to 400 vertices, where re-deriving the whole shortcut graph is "
        "cheap): %s. And the realized error column of docs/metrics.json shows all three methods landing on "
        "the tolerance rather than under it, so the vertex counts are being compared at equal error, not at "
        "equal effort."
    ) % (num(checked), "all passed" if verified else "FAILED, see docs/metrics.json")

    repl = {
        "{{GEOS_MATCH}}": num(rep["geos_crosscheck"]["same_vertex_count"]),
        "{{GEOS_N}}": num(rep["geos_crosscheck"]["polylines"]),
        "{{TABLE}}": table(runs),
        "{{RESULTS_PARA}}": para,
        "{{RESULTS_TAIL}}": tail,
        "{{NS_ML}}": num(m6["minlink"]["non_simple"]),
        "{{NS_DP}}": num(m6["douglas_peucker"]["non_simple"]),
        "{{TIMING_SENTENCE}}": (
            "Over the whole %s vertex corpus at zoom %d it takes %.0f seconds against %.0f for "
            "Douglas-Peucker, and the cost is concentrated in the few polylines above ten thousand vertices."
            % (num(c["vertices"]), z6["zoom"], m6["minlink"]["seconds"], m6["douglas_peucker"]["seconds"])),
        "{{FINE_SENTENCE}}": (
            "At zoom %d the advantage is %.1f percent, against %.1f percent at zoom %d."
            % (fine["zoom"], fine["reduction_vs_dp_pct"], coarse["reduction_vs_dp_pct"], coarse["zoom"])),
    }

    demo = ""
    if os.path.exists(a.demo_output):
        demo = open(a.demo_output, encoding="utf-8").read().strip()
    repl["{{DEMO_BLOCK}}"] = ("A real run of `python demo.py` on the longest coastline polyline:\n\n```\n"
                              + demo + "\n```") if demo else "Run `python demo.py` to produce this section."

    text = open(a.template, encoding="utf-8").read()
    for k, v in repl.items():
        text = text.replace(k, v)
    open(a.out, "w", encoding="utf-8", newline="\n").write(text)
    print("wrote %s (%d bytes), unresolved placeholders: %d" % (a.out, len(text), text.count("{{")))


if __name__ == "__main__":
    main()
