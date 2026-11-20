"""Draw one real coastline three ways: original, Douglas-Peucker, exact minimum.

Produces docs/geometry.png. The point of the figure is that the two
simplifications are held to the same error bound and look the same, and one of
them is spending noticeably fewer vertices to do it.
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minlink import douglas_peucker_indices, max_error, min_vertex_indices, zoom_tolerance
from minlink.data import load_polylines

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
BLUE, AQUA = "#2a78d6", "#1baf7a"


def draw(ax, P, idx, color, title, subtitle, show_dots):
    ax.plot(P[:, 0], P[:, 1], color="#d9d8d1", linewidth=2.6, zorder=1,
            solid_capstyle="round")
    if idx is not None:
        Q = P[idx]
        ax.plot(Q[:, 0], Q[:, 1], color=color, linewidth=1.6, zorder=2,
                solid_capstyle="round")
        if show_dots:
            ax.plot(Q[:, 0], Q[:, 1], linestyle="none", marker="o", markersize=3.6,
                    color=color, markeredgecolor=SURFACE, markeredgewidth=0.6, zorder=3)
    ax.set_title(title, color=INK, fontsize=12, loc="left", pad=8, weight="bold")
    ax.set_xlabel(subtitle, color=INK2, fontsize=9.5, labelpad=8)
    ax.set_aspect("equal")
    ax.set_facecolor(SURFACE)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=5)
    ap.add_argument("--max-vertices", type=int, default=3000)
    ap.add_argument("--out", default="docs/geometry.png")
    a = ap.parse_args()

    polys = load_polylines("coastline10m")
    # Pick a detailed polyline whose bounding box is roughly square, so the
    # three panels are filled by coastline rather than by empty margin.
    cand = [p for p in polys if 600 <= len(p) <= a.max_vertices]

    def squareness(p):
        w, h = p.max(axis=0) - p.min(axis=0)
        if w <= 0 or h <= 0:
            return 1e9
        return abs(np.log(w / h))

    cand.sort(key=lambda p: (squareness(p), -len(p)))
    P = cand[0]
    eps = zoom_tolerance(a.zoom)
    dp = douglas_peucker_indices(P, eps)
    ml, _ = min_vertex_indices(P, eps)

    fig = plt.figure(figsize=(13.2, 5.0), dpi=150, facecolor=SURFACE)
    axes = fig.subplots(1, 3)
    draw(axes[0], P, None, MUTED, "Original coastline",
         "%s vertices" % format(len(P), ","), False)
    draw(axes[1], P, dp, BLUE, "Douglas-Peucker",
         "%s vertices, error %.5f deg" % (format(len(dp), ","), max_error(P, dp)), True)
    draw(axes[2], P, ml, AQUA, "minlink (exact minimum)",
         "%s vertices, error %.5f deg" % (format(len(ml), ","), max_error(P, ml)), True)
    fig.suptitle("One real coastline at a zoom %d tolerance: the same bound, %.0f percent fewer vertices"
                 % (a.zoom, 100.0 * (len(dp) - len(ml)) / len(dp)),
                 x=0.03, y=0.965, ha="left", fontsize=13.5, color=INK, weight="bold")
    fig.text(0.03, 0.035,
             "Grey is the full resolution input. Dots are the vertices each method keeps. Neither output may stray further than %.5f degrees from any dropped vertex."
             % eps, fontsize=9, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.02, right=0.985, top=0.84, bottom=0.14, wspace=0.07)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fig.savefig(a.out, facecolor=SURFACE)
    print("wrote %s: original %d, dp %d, minlink %d" % (a.out, len(P), len(dp), len(ml)))


if __name__ == "__main__":
    main()
