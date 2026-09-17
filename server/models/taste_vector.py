"""The taste vector (§11), fully specified:

    v_0 = catalog centroid                  # NOT the zero vector; normalize(0)
                                            # is undefined and the first update
                                            # would crash or produce NaN
    w_i = clip(2 * p_i - 1, -0.5, 1.0)     # p_i = calibrated interest
    w_i = -0.5                              # if the view is a fast skip
    v  <- normalize( (1 - lambda) * v + eta * w_i * e_i )
    eta = 0.3,  lambda = 0.067              # ~10-view half-life

Until a session has 3 scored views, the population prior is served instead
of the session's own vector (below that the vector is mostly
initialization noise) — that's `min_scored_views_for_own_vector` here,
enforced by `TasteVectorTracker.public_vector`, not left to callers to
remember.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

ETA = 0.3
LAMBDA = 0.067
MIN_SCORED_VIEWS_FOR_OWN_VECTOR = 3
FAST_SKIP_WEIGHT = -0.5


def normalize(v: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        raise ValueError("normalize(0) is undefined — see module docstring; v_0 must be the catalog centroid, never the zero vector")
    return tuple(x / norm for x in v)


def clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def weight_from_calibrated_interest(p_i: float, is_fast_skip: bool) -> float:
    if is_fast_skip:
        return FAST_SKIP_WEIGHT
    return clip(2 * p_i - 1, -0.5, 1.0)


def update(v: tuple[float, ...], w_i: float, e_i: tuple[float, ...]) -> tuple[float, ...]:
    """One taste-vector update step. `e_i` is the viewed item's embedding
    (same dimensionality as `v`) — see sim/embedding.py for Gate 1's
    concrete embedding space, though this function is embedding-agnostic."""
    if len(v) != len(e_i):
        raise ValueError(f"dimension mismatch: v has {len(v)} dims, e_i has {len(e_i)}")
    blended = tuple((1 - LAMBDA) * v_d + ETA * w_i * e_d for v_d, e_d in zip(v, e_i))
    return normalize(blended)


@dataclass
class TasteVectorTracker:
    """Per-session mutable state: the running vector plus a count of
    *scored* views (views with a calibrated interest value, i.e. not
    missing/unscoreable) — the population-prior gate reads that count,
    not just any view."""

    catalog_centroid: tuple[float, ...]
    vector: tuple[float, ...] = field(init=False)
    scored_view_count: int = 0

    def __post_init__(self) -> None:
        self.vector = normalize(self.catalog_centroid)

    def observe_view(self, item_embedding: tuple[float, ...], p_i: float | None, is_fast_skip: bool) -> None:
        """`p_i=None` means no calibrated interest is available for this
        view (e.g. the calibration model isn't confident, or the mode
        doesn't support it) — such a view updates neither the vector nor
        the scored-view count, per §11's "calibrated interest" framing;
        a fast skip *does* count (it's still informative, just negative)."""
        if p_i is None and not is_fast_skip:
            return
        w_i = weight_from_calibrated_interest(p_i if p_i is not None else 0.0, is_fast_skip)
        self.vector = update(self.vector, w_i, item_embedding)
        self.scored_view_count += 1

    def public_vector(self, population_prior: tuple[float, ...]) -> tuple[float, ...]:
        """§11: "Until a session has 3 scored views, serve the population
        prior rather than the session's own vector.""" ""
        if self.scored_view_count < MIN_SCORED_VIEWS_FOR_OWN_VECTOR:
            return population_prior
        return self.vector
