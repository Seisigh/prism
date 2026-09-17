"""Cross-browser trajectory normalization (§7.3): "Resample every
trajectory onto a fixed 60Hz grid by linear interpolation before any
feature extraction." Pointer coalescing differs across browser engines,
so raw sample spacing partly measures the browser rather than the
visitor — this removes that confound before `signals.py` ever sees a
trajectory.
"""
from __future__ import annotations

from server.features.window_spec import RawEvent

GRID_HZ = 60.0
GRID_STEP_MS = 1000.0 / GRID_HZ


def resample_pointer_trajectory(samples: list[RawEvent], item_id: str, surface: str) -> list[RawEvent]:
    """Linear interpolation onto a fixed 60Hz grid spanning the input
    samples' own time range. Fewer than 2 samples can't be interpolated
    and are returned unchanged (there's no trajectory to resample)."""
    pts = sorted(((e.t, float(e.payload["x"]), float(e.payload["y"])) for e in samples), key=lambda p: p[0])
    if len(pts) < 2:
        return list(samples)

    t0, tn = pts[0][0], pts[-1][0]
    out: list[RawEvent] = []
    grid_t = t0
    src_i = 0
    while grid_t <= tn:
        while src_i < len(pts) - 2 and pts[src_i + 1][0] < grid_t:
            src_i += 1
        (ta, xa, ya), (tb, xb, yb) = pts[src_i], pts[src_i + 1]
        frac = 0.0 if tb == ta else (grid_t - ta) / (tb - ta)
        frac = min(1.0, max(0.0, frac))
        x = xa + (xb - xa) * frac
        y = ya + (yb - ya) * frac
        out.append(RawEvent(t=grid_t, type="pointer_sample", item_id=item_id, surface=surface, payload={"x": x, "y": y}))
        grid_t += GRID_STEP_MS
    return out
