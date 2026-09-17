"""Within-(session, mode, surface) normalization (§4.2): "Dwell is
z-scored within (session, mode, surface), then centered within item."
This is a session-local normalizer — it needs only the session's own
other views in the same stratum, not a pretrained population model, so it
belongs in Gate 0 rather than waiting on Gate 1's simulator-calibrated
normalizers.
"""
from __future__ import annotations

import statistics


def z_score(x: float, population: list[float]) -> float | None:
    """None when the population can't support a z-score (fewer than 2
    points, or zero variance) — never divide by zero, never impute 0.0
    for a genuinely uncomputable statistic."""
    if len(population) < 2:
        return None
    mean = statistics.fmean(population)
    stdev = statistics.pstdev(population)
    if stdev == 0:
        return None
    return (x - mean) / stdev


# The "centered within item" half of §4.2 (subtracting an item's own
# across-session baseline after the within-session z-score) needs
# multiple sessions' worth of views of the same item to have a baseline
# to center against — that's aggregation state belonging to
# `server/ingest`'s session store, not this pure-function module. Not
# implemented yet; flagged in STATE.md rather than half-built here.
