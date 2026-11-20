"""minlink: provably minimum-vertex polyline simplification."""

from .baselines import (
    douglas_peucker_indices,
    geos_indices,
    max_error,
    visvalingam_indices,
)
from .core import (
    min_vertex_indices,
    segment_error,
    simplify,
    simplify_to_budget,
    valid_targets,
    verify_optimality,
)
from .metrics import encoded_size, non_simple_count, zoom_tolerance

__all__ = [
    "simplify",
    "simplify_to_budget",
    "min_vertex_indices",
    "verify_optimality",
    "valid_targets",
    "segment_error",
    "douglas_peucker_indices",
    "visvalingam_indices",
    "geos_indices",
    "max_error",
    "zoom_tolerance",
    "encoded_size",
    "non_simple_count",
]
__version__ = "0.1.0"
