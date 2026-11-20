"""Correctness tests, including a brute force oracle for the exact solver."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minlink import (
    douglas_peucker_indices,
    max_error,
    min_vertex_indices,
    segment_error,
    simplify_to_budget,
    valid_targets,
    verify_optimality,
    visvalingam_indices,
)


def brute_force_min_vertices(P: np.ndarray, eps: float):
    """Independent oracle: test every pair with a direct point to segment scan.

    Deliberately written the slow obvious way (no wedges, no prefix scans) so
    that agreement with the fast solver is evidence about the fast solver.
    """
    n = len(P)
    label = [None] * n
    label[0] = 0
    parent = [-1] * n
    for i in range(n - 1):
        if label[i] is None:
            continue
        for j in range(i + 1, n):
            if segment_error(P, i, j) <= eps and (label[j] is None or label[j] > label[i] + 1):
                label[j] = label[i] + 1
                parent[j] = i
    path = [n - 1]
    while path[-1] != 0:
        path.append(parent[path[-1]])
    return np.array(path[::-1]), label


def _cases(seed: int = 7):
    rng = np.random.default_rng(seed)
    cases = []
    for n in (3, 5, 12, 40, 90):
        cases.append(rng.normal(size=(n, 2)) * 3.0)
        walk = np.cumsum(rng.normal(size=(n, 2)), axis=0)
        cases.append(walk)
    t = np.linspace(0, 6 * np.pi, 120)
    cases.append(np.stack([t, np.sin(t)], axis=1))
    spiral = np.stack([t * np.cos(t), t * np.sin(t)], axis=1)
    cases.append(spiral)
    folded = np.array([[0, 0], [10, 0], [1, 0.2], [11, 0.4], [2, 0.1], [12, 0]], dtype=float)
    cases.append(folded)
    cases.append(np.array([[0, 0], [1, 1], [1, 1], [2, 0]], dtype=float))
    return cases


def test_matches_brute_force_oracle():
    for P in _cases():
        for eps in (0.0, 0.05, 0.3, 1.0, 3.0):
            fast, _ = min_vertex_indices(P, eps)
            slow, _ = brute_force_min_vertices(P, eps)
            assert len(fast) == len(slow), (len(P), eps, len(fast), len(slow))
            assert max_error(P, fast) <= eps + 1e-9


def test_valid_targets_agrees_with_direct_scan():
    for P in _cases(11):
        for eps in (0.05, 0.5, 2.0):
            for i in range(len(P) - 1):
                got = set(int(j) for j in valid_targets(P, i, eps))
                want = {j for j in range(i + 1, len(P)) if segment_error(P, i, j) <= eps}
                assert got == want, (i, eps, sorted(got ^ want))


def test_certificate_holds():
    for P in _cases(3):
        for eps in (0.1, 0.75):
            idx, label = min_vertex_indices(P, eps)
            assert verify_optimality(P, eps, label)
            assert int(label[-1]) + 1 == len(idx)


def test_never_worse_than_shipped_heuristics():
    for P in _cases(5):
        for eps in (0.1, 0.5, 2.0):
            exact, _ = min_vertex_indices(P, eps)
            dp = douglas_peucker_indices(P, eps)
            vw = visvalingam_indices(P, eps)
            assert max_error(P, dp) <= eps + 1e-9
            assert max_error(P, vw) <= eps + 1e-9
            assert len(exact) <= len(dp)
            assert len(exact) <= len(vw)


def test_endpoints_preserved_and_monotone():
    P = _cases(2)[4]
    prev = len(P) + 1
    for eps in (0.0, 0.01, 0.1, 1.0, 10.0):
        idx, _ = min_vertex_indices(P, eps)
        assert idx[0] == 0 and idx[-1] == len(P) - 1
        assert len(idx) <= prev
        prev = len(idx)


def test_budget_inversion():
    P = _cases(9)[-4]
    for budget in (3, 5, 10):
        out, eps = simplify_to_budget(P, budget)
        assert len(out) <= budget
        assert eps >= 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print("all %d tests passed" % len(fns))
