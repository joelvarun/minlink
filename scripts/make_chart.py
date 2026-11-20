"""Render docs/before_after.png from the measured numbers in docs/metrics.json."""

from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SERIES = {
    "douglas_peucker": (BLUE, "Douglas-Peucker (GEOS, PostGIS, turf)"),
    "visvalingam": (ORANGE, "Visvalingam-Whyatt (mapshaper, d3)"),
    "minlink": (AQUA, "minlink (exact minimum)"),
}
ORDER = ["douglas_peucker", "visvalingam", "minlink"]


def style(ax, yaxis_only=True):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y" if yaxis_only else "both", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=MUTED, labelsize=9, length=3)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_color(INK2)


def zoom_ticks(ax, runs, with_eps=True):
    x = np.arange(len(runs), dtype=float)
    ax.set_xticks(x)
    if with_eps:
        ax.set_xticklabels(["z%d\n%.3f" % (r["zoom"], r["eps_deg"]) for r in runs])
    else:
        ax.set_xticklabels(["z%d" % r["zoom"] for r in runs])
    return x


def panel_vertices(ax, runs):
    x = zoom_ticks(ax, runs)
    width = 0.27
    tops = np.zeros(len(runs))
    for i, m in enumerate(ORDER):
        vals = np.array([r["methods"][m]["vertices"] for r in runs], float) / 1000.0
        tops = np.maximum(tops, vals)
        ax.bar(x + (i - 1) * (width + 0.012), vals, width, color=SERIES[m][0],
               edgecolor=SURFACE, linewidth=2.0, zorder=3)
    for xi, r, top in zip(x, runs, tops):
        ml = r["methods"]["minlink"]["vertices"] / 1000.0
        dp = r["methods"]["douglas_peucker"]["vertices"] / 1000.0
        ax.annotate("%.0fk" % dp, (xi - (width + 0.012), dp), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7.5, color=INK2, zorder=4)
        ax.annotate("%.0fk" % ml, (xi + (width + 0.012), ml), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7.5,
                    color=AQUA, weight="bold", zorder=4)
    ax.set_title("Vertices kept at each tolerance", color=INK, fontsize=11.5,
                 loc="left", pad=8, weight="bold")
    ax.set_ylabel("thousands of vertices", color=INK2, fontsize=9)
    ax.set_xlabel("zoom level and tolerance in degrees", color=MUTED, fontsize=8.5)
    style(ax)
    ax.margins(y=0.16)


def panel_savings(ax, runs):
    x = zoom_ticks(ax, runs, with_eps=False)
    width = 0.34
    verts = np.array([r["reduction_vs_dp_pct"] for r in runs])
    gz = np.array([r["gzip_reduction_vs_dp_pct"] for r in runs])
    ax.bar(x - width / 2 - 0.01, verts, width, color=AQUA, edgecolor=SURFACE,
           linewidth=2.0, zorder=3, label="vertices")
    ax.bar(x + width / 2 + 0.01, gz, width, color=SURFACE, edgecolor=AQUA, hatch="////",
           linewidth=1.6, zorder=3, label="gzipped GeoJSON bytes")
    for xi, v in zip(x - width / 2 - 0.01, verts):
        ax.annotate("%.0f%%" % v, (xi, v), xytext=(-2, 4), textcoords="offset points",
                    ha="right", fontsize=8, color=AQUA, weight="bold", zorder=4)
    for xi, v in zip(x + width / 2 + 0.01, gz):
        ax.annotate("%.0f%%" % v, (xi, v), xytext=(2, 4), textcoords="offset points",
                    ha="left", fontsize=8, color=INK2, zorder=4)
    ax.set_title("Saved against Douglas-Peucker", color=INK, fontsize=11.5,
                 loc="left", pad=8, weight="bold")
    ax.set_ylabel("percent smaller at the same error bound", color=INK2, fontsize=9)
    ax.set_xlabel("web map zoom level", color=MUTED, fontsize=8.5)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="upper right")
    style(ax)
    ax.margins(y=0.20)


def panel_error(ax, runs):
    x = zoom_ticks(ax, runs, with_eps=False)
    eps = np.array([r["eps_deg"] for r in runs])
    ax.plot(x, eps, color=MUTED, linewidth=3.0, zorder=2, label="tolerance (the bound)")
    # All three land on the bound, so draw them as nested markers rather than
    # three identical lines that hide each other.
    for m, size in zip(ORDER, (15.0, 9.5, 4.5)):
        vals = np.array([r["methods"][m]["max_error_deg"] for r in runs])
        ax.plot(x, vals, marker="o", markersize=size, linestyle="none",
                color=SERIES[m][0], zorder=3 + ORDER.index(m))
    ax.set_yscale("log")
    ax.set_title("Realized error, all on the same bound", color=INK, fontsize=11.5,
                 loc="left", pad=8, weight="bold")
    ax.set_ylabel("worst dropped vertex, degrees", color=INK2, fontsize=9)
    ax.set_xlabel("web map zoom level", color=MUTED, fontsize=8.5)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="lower left")
    style(ax, yaxis_only=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="docs/metrics.json")
    ap.add_argument("--out", default="docs/before_after.png")
    a = ap.parse_args()
    rep = json.load(open(a.metrics, encoding="utf-8"))
    runs, c = rep["runs"], rep["corpus"]

    fig = plt.figure(figsize=(14.4, 5.9), dpi=150, facecolor=SURFACE)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.3, 1.0, 0.92], wspace=0.30,
                          left=0.052, right=0.988, top=0.775, bottom=0.165)
    panel_vertices(fig.add_subplot(gs[0, 0]), runs)
    panel_savings(fig.add_subplot(gs[0, 1]), runs)
    panel_error(fig.add_subplot(gs[0, 2]), runs)

    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[m][0]) for m in ORDER]
    fig.legend(handles, [SERIES[m][1] for m in ORDER], frameon=False, ncol=3,
               loc="upper left", bbox_to_anchor=(0.052, 0.945), fontsize=9.5,
               labelcolor=INK2, handlelength=1.1, handleheight=1.1, columnspacing=1.8)
    fig.suptitle("Same error bound, fewer vertices: the exact minimum against the shipped heuristics",
                 x=0.052, y=0.972, ha="left", fontsize=13.5, color=INK, weight="bold")
    fig.text(0.052, 0.052,
             "Natural Earth 1:10m coastline, %s polylines and %s vertices. Tolerance is one screen pixel at each web map zoom level."
             % (format(c["polylines"], ","), format(c["vertices"], ",")),
             fontsize=8.5, color=MUTED, ha="left")
    fig.text(0.052, 0.018,
             "All three methods are held to the identical point-to-segment bound. minlink is proved minimal by a shortest path certificate, so no method can do better at this bound.",
             fontsize=8.5, color=MUTED, ha="left")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fig.savefig(a.out, facecolor=SURFACE)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
