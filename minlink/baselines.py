"""The two simplification heuristics that real GIS stacks actually ship."""

from __future__ import annotations

import heapq

import numpy as np

from .core import as_points, segment_error


def douglas_peucker_indices(P: np.ndarray, eps: float) -> np.ndarray:
    """Douglas-Peucker: split at the worst vertex, recurse, stop under eps.

    This is what shapely.simplify, PostGIS ST_Simplify, turf.js and every
    mapping tutorial use. It is greedy: the split point is chosen by local
    error, never by how many vertices the choice will cost downstream.
    """
    n = len(P)
    if n <= 2:
        return np.arange(n, dtype=np.int64)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        A = P[a]
        AB = P[b] - A
        Q = P[a + 1:b] - A
        denom = float(AB @ AB)
        if denom == 0.0:
            d = np.hypot(Q[:, 0], Q[:, 1])
        else:
            t = np.clip((Q @ AB) / denom, 0.0, 1.0)
            R = Q - t[:, None] * AB
            d = np.hypot(R[:, 0], R[:, 1])
        k = int(np.argmax(d))
        if float(d[k]) > eps:
            split = a + 1 + k
            keep[split] = True
            stack.append((a, split))
            stack.append((split, b))
    return np.flatnonzero(keep).astype(np.int64)


def _triangle_area(P: np.ndarray, a: int, b: int, c: int) -> float:
    u = P[b] - P[a]
    v = P[c] - P[a]
    return 0.5 * abs(float(u[0] * v[1] - u[1] * v[0]))


def visvalingam_order(P: np.ndarray) -> list[int]:
    """Visvalingam-Whyatt removal order, smallest effective area first.

    Used by mapshaper, d3 and PostGIS ST_SimplifyVW. Returns the interior
    vertices in the order the algorithm discards them.
    """
    n = len(P)
    if n <= 2:
        return []
    prev = list(range(-1, n - 1))
    nxt = list(range(1, n + 1))
    alive = np.ones(n, dtype=bool)
    heap = []
    stamp = [0] * n
    for i in range(1, n - 1):
        heapq.heappush(heap, (_triangle_area(P, i - 1, i, i + 1), i, 0))
    order = []
    floor = 0.0
    while heap:
        area, i, s = heapq.heappop(heap)
        if not alive[i] or s != stamp[i]:
            continue
        floor = max(floor, area)
        order.append(i)
        alive[i] = False
        p, q = prev[i], nxt[i]
        nxt[p] = q
        prev[q] = p
        for v in (p, q):
            if 0 < v < n - 1 and alive[v]:
                stamp[v] += 1
                heapq.heappush(heap, (max(floor, _triangle_area(P, prev[v], v, nxt[v])), v, stamp[v]))
    return order


def visvalingam_indices(P: np.ndarray, eps: float) -> np.ndarray:
    """Most aggressive Visvalingam stop whose realized error still clears eps.

    Visvalingam is parameterised by an area, not a distance, so comparing it at
    a distance tolerance needs a stopping rule. Bisecting its own removal order
    for the longest prefix that still measures within eps is the most
    favourable reading of the heuristic, which is the one worth beating.
    """
    n = len(P)
    if n <= 2:
        return np.arange(n, dtype=np.int64)
    order = visvalingam_order(P)
    lo, hi = 0, len(order)
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        keep = np.ones(n, dtype=bool)
        keep[order[:mid]] = False
        idx = np.flatnonzero(keep)
        if max_error(P, idx) <= eps:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    keep = np.ones(n, dtype=bool)
    keep[order[:best]] = False
    return np.flatnonzero(keep).astype(np.int64)


def max_error(P: np.ndarray, idx) -> float:
    """Realized error of a simplification: the worst dropped vertex."""
    idx = np.asarray(idx, dtype=np.int64)
    worst = 0.0
    for a, b in zip(idx[:-1], idx[1:]):
        e = segment_error(P, int(a), int(b))
        if e > worst:
            worst = e
    return worst


def geos_indices(P: np.ndarray, eps: float) -> np.ndarray:
    """shapely/GEOS Douglas-Peucker, mapped back to input vertex indices.

    Kept as a cross check that the local Douglas-Peucker is the shipped one and
    not a weakened straw man.
    """
    from shapely.geometry import LineString

    coords = np.asarray(LineString(P).simplify(eps, preserve_topology=False).coords, dtype=float)
    idx = [0]
    for q in coords[1:]:
        k = int(np.argmin(np.hypot(P[:, 0] - q[0], P[:, 1] - q[1])))
        if k > idx[-1]:
            idx.append(k)
    if idx[-1] != len(P) - 1:
        idx.append(len(P) - 1)
    return np.array(idx, dtype=np.int64)
