"""Exact minimum-vertex polyline simplification.

Douglas-Peucker and Visvalingam-Whyatt are greedy: they pick vertices to drop
with a local rule and offer no guarantee about how many vertices survive. The
minimum-vertex problem is not hard, it is a shortest path. Build a graph whose
nodes are the input vertices and whose edges are the shortcuts that stay inside
the error bound, then the fewest-vertex simplification is the fewest-edge path
from the first vertex to the last.

This module solves that exactly and returns a machine checkable certificate of
optimality with the answer. The classical formulation is Imai and Iri (1988),
with the wedge based edge enumeration of Chan and Chin (1996).
"""

from __future__ import annotations

import numpy as np

TWO_PI = 2.0 * np.pi
_UNREACHABLE = np.iinfo(np.int64).max // 4


def as_points(points) -> np.ndarray:
    """Coerce an input polyline to a contiguous float array of shape (n, 2)."""
    P = np.asarray(points, dtype=float)
    if P.ndim != 2 or P.shape[1] < 2:
        raise ValueError("points must have shape (n, 2)")
    return np.ascontiguousarray(P[:, :2])


def segment_error(P: np.ndarray, a: int, b: int) -> float:
    """Largest distance from any vertex strictly between a and b to segment a-b.

    This is the error that dropping those vertices actually costs, measured
    point to segment (not point to infinite line), which is the same quantity
    GEOS and PostGIS bound in Douglas-Peucker.
    """
    if b - a < 2:
        return 0.0
    A = P[a]
    AB = P[b] - A
    Q = P[a + 1:b] - A
    denom = float(AB @ AB)
    if denom == 0.0:
        return float(np.hypot(Q[:, 0], Q[:, 1]).max())
    t = np.clip((Q @ AB) / denom, 0.0, 1.0)
    R = Q - t[:, None] * AB
    return float(np.hypot(R[:, 0], R[:, 1]).max())


def valid_targets(P: np.ndarray, i: int, eps: float) -> np.ndarray:
    """Every j > i whose shortcut from i keeps all skipped vertices within eps.

    Two stage test. The wedge stage is a necessary condition evaluated for all
    j at once: a skipped vertex is within eps of the segment only if it is
    within eps of the infinite line, and the directions that satisfy that for
    every skipped vertex form a shrinking intersection of angular intervals,
    which prefix scans compute in one pass. The second stage pays for an exact
    point to segment check only on the j where a skipped vertex can fall beyond
    the far endpoint, which the running maximum radius detects.
    """
    D = P[i + 1:] - P[i]
    m = len(D)
    if m == 0:
        return np.empty(0, dtype=np.int64)
    r = np.hypot(D[:, 0], D[:, 1])
    inside = r <= eps
    ok = np.ones(m, dtype=bool)
    constrained = np.flatnonzero(~inside)
    if constrained.size:
        theta = np.arctan2(D[:, 1], D[:, 0])
        # Unwrap onto one branch: any direction in the intersection sits within
        # pi/2 of the first constrained vertex, so the nearest branch is right.
        ref = theta[constrained[0]]
        theta = ref + (np.mod(theta - ref + np.pi, TWO_PI) - np.pi)
        half = np.arcsin(np.clip(eps / np.maximum(r, 1e-300), 0.0, 1.0))
        lo = np.where(inside, -np.inf, theta - half)
        hi = np.where(inside, np.inf, theta + half)
        lo = np.maximum.accumulate(lo)
        hi = np.minimum.accumulate(hi)
        ok[1:] = (
            (lo[:-1] <= hi[:-1] + 1e-12)
            & (theta[1:] >= lo[:-1] - 1e-12)
            & (theta[1:] <= hi[:-1] + 1e-12)
        )
        rmax = np.maximum.accumulate(r)
        recheck = np.zeros(m, dtype=bool)
        recheck[1:] = ok[1:] & (rmax[:-1] > r[1:])
        A = P[i]
        for j in np.flatnonzero(recheck):
            # Only vertices farther from i than the endpoint itself can project
            # past that endpoint; every other skipped vertex is already within
            # eps of the line and projects inside the segment.
            far = np.flatnonzero(r[:j] > r[j])
            if far.size == 0:
                continue
            AB = P[i + 1 + int(j)] - A
            Q = P[i + 1 + far] - A
            denom = float(AB @ AB)
            if denom == 0.0:
                worst = float(np.hypot(Q[:, 0], Q[:, 1]).max())
            else:
                t = np.clip((Q @ AB) / denom, 0.0, 1.0)
                R = Q - t[:, None] * AB
                worst = float(np.hypot(R[:, 0], R[:, 1]).max())
            if worst > eps:
                ok[j] = False
    return np.flatnonzero(ok) + i + 1


def min_vertex_indices(P: np.ndarray, eps: float) -> tuple[np.ndarray, np.ndarray]:
    """Fewest-vertex simplification within eps. Returns (indices, layer labels).

    The labels are the shortest path distances in the shortcut graph and are the
    optimality certificate: see verify_optimality.
    """
    n = len(P)
    if n <= 2 or eps < 0:
        return np.arange(n, dtype=np.int64), np.arange(n, dtype=np.int64)
    label = np.full(n, _UNREACHABLE, dtype=np.int64)
    parent = np.full(n, -1, dtype=np.int64)
    label[0] = 0
    for i in range(n - 1):
        if label[i] >= _UNREACHABLE:
            continue
        js = valid_targets(P, i, eps)
        better = js[label[js] > label[i] + 1]
        label[better] = label[i] + 1
        parent[better] = i
    out = [n - 1]
    while out[-1] != 0:
        out.append(int(parent[out[-1]]))
    return np.array(out[::-1], dtype=np.int64), label


def simplify(points, eps: float) -> np.ndarray:
    """Minimum-vertex simplification of a polyline within tolerance eps."""
    P = as_points(points)
    idx, _ = min_vertex_indices(P, float(eps))
    return P[idx]


def verify_optimality(P: np.ndarray, eps: float, label: np.ndarray) -> bool:
    """Check the certificate: no shortcut in the graph skips a layer.

    If label[0] == 0 and every valid shortcut (i, j) satisfies
    label[j] <= label[i] + 1, then label is a feasible potential on the
    shortcut graph, so no path from 0 to n-1 can be shorter than label[n-1],
    and the returned path attains it. That makes the vertex count provably
    minimal rather than merely small.
    """
    n = len(P)
    if label[0] != 0:
        return False
    for i in range(n - 1):
        if label[i] >= _UNREACHABLE:
            continue
        js = valid_targets(P, i, eps)
        if js.size and int(label[js].max()) > int(label[i]) + 1:
            return False
    return True


def simplify_to_budget(points, max_vertices: int, lo: float = 0.0,
                       hi: float | None = None, rounds: int = 24):
    """Tightest tolerance whose minimum-vertex answer fits a vertex budget.

    Vector tile writers get a vertex budget, not a tolerance. Because the
    minimum vertex count is monotone in eps, a bisection on eps inverts it to
    the resolution of the bisection, which 24 rounds puts at about one part in
    sixteen million of the polyline's own diagonal. Each round is a full exact
    solve, so the cost is rounds times the cost of simplify.
    """
    P = as_points(points)
    if max_vertices < 2:
        raise ValueError("max_vertices must be at least 2")
    if len(P) <= max_vertices:
        return P, 0.0
    if hi is None:
        span = P.max(axis=0) - P.min(axis=0)
        hi = float(np.hypot(*span)) or 1.0
    best = None
    for _ in range(rounds):
        mid = 0.5 * (lo + hi)
        idx, _lab = min_vertex_indices(P, mid)
        if len(idx) <= max_vertices:
            best = (P[idx], mid)
            hi = mid
        else:
            lo = mid
    if best is None:
        idx, _lab = min_vertex_indices(P, hi)
        best = (P[idx], hi)
    return best
