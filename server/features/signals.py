"""Gate 0 signal set (BUILD_BRIEF.md §9.3). Eight signals, all "safe"
(none touches a commitment event or micro-oscillation near Add to Cart —
those are permanently excluded per §9.4).

Every function has the signature `f(events, window, ctx) -> float | None`.
`None` means genuinely unavailable in this mode/surface (§9.2) — a touch
session has no hover or pointer-trajectory signals, a view with no scroll
activity has no scroll depth. **Never return 0.0 for a missing signal.**

Every function reads only `events_in_window(events, window, ...)` —
never `events` directly — so the leakage test in
tests/features/test_leakage.py can assert this mechanically for each
function in `SIGNAL_REGISTRY` rather than trusting a docstring.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal

from server.features.window_spec import RawEvent, WindowSpec, events_in_window

PointerType = Literal["mouse", "touch", "pen"]


@dataclass(frozen=True)
class ItemContext:
    item_id: str
    surface: str
    mode: str
    pointer_type: PointerType
    # Gate 1 additions (server/features/signals_gate1.py). All optional
    # and caller-supplied session context, not derived from `events` —
    # unlike the Gate 0 fields above, these describe facts about the
    # *rest of the session*, so the caller (not this module) is
    # responsible for the leakage guarantee: every value here must be
    # computed only from views strictly before this one. See
    # signals_gate1.py's docstring for the contract in full.
    category: str | None = None
    prior_view_starts_for_item: tuple[float, ...] = ()
    prior_view_categories: tuple[str, ...] = ()
    active_query_token_count: int | None = None
    near_substitute_coview_count: int | None = None
    # server/features/signals_directional.py's coordinates: the two real
    # on-screen destinations the reach was blended between (see
    # sim/generative.py / sim/session.py). Both None on a surface with no
    # meaningful reject location -- the caller's job to leave unset
    # rather than synthesize a position, per that module's docstring.
    accept_pos: tuple[float, float] | None = None
    reject_pos: tuple[float, float] | None = None


def _pointer_samples(events: list[RawEvent], window: WindowSpec) -> list[tuple[float, float, float]]:
    """(t, x, y) tuples from pointer_sample events in-window, time-sorted.
    Ingest unpacks each batched `pointer_batch` envelope (§7.2) into one
    `pointer_sample` RawEvent per resampled point before features ever see
    it — see server/ingest — so this module only deals in flat samples."""
    pts = [
        (e.t, float(e.payload["x"]), float(e.payload["y"]))
        for e in events_in_window(events, window)
        if e.type == "pointer_sample"
    ]
    return sorted(pts, key=lambda p: p[0])


def _scroll_samples(events: list[RawEvent], window: WindowSpec) -> list[tuple[float, float]]:
    pts = [
        (e.t, float(e.payload["y_ratio"]))
        for e in events_in_window(events, window)
        if e.type == "scroll_sample"
    ]
    return sorted(pts, key=lambda p: p[0])


def _visibility_samples(events: list[RawEvent], window: WindowSpec, item_id: str) -> list[tuple[float, float]]:
    pts = [
        (e.t, float(e.payload["ratio"]))
        for e in events_in_window(events, window, item_id=item_id)
        if e.type == "visibility_sample"
    ]
    return sorted(pts, key=lambda p: p[0])


# 1. Item dwell ---------------------------------------------------------------


def item_dwell(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """log(1+t) of the sealed window's own duration. Normalization within
    (session, mode, surface) per §4.2 happens one layer up (it needs the
    session's other views to compute a z-score) — this returns the raw
    per-view quantity that normalizer consumes."""
    duration_s = (window.t_end - window.t_start) / 1000.0
    if duration_s <= 0:
        return None
    return math.log1p(duration_s)


# 2. Viewport time via IntersectionObserver ------------------------------------


def viewport_time(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Total time the card was actually >=50% visible within the sealed
    window (can be less than the full window if visibility dipped) —
    distinct from item_dwell, which is just the window's span."""
    samples = _visibility_samples(events, window, ctx.item_id)
    if not samples:
        return None
    total_ms = 0.0
    for (t0, r0), (t1, _r1) in zip(samples, samples[1:]):
        if r0 >= 0.5:
            total_ms += t1 - t0
    if total_ms <= 0:
        return None
    return math.log1p(total_ms / 1000.0)


# 3. Hover dwell on target element ---------------------------------------------


def hover_dwell_on_target(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Touch has no hover — gated off entirely per §7.3, not just empty."""
    if ctx.pointer_type == "touch":
        return None
    scoped = events_in_window(events, window, item_id=ctx.item_id)
    starts = sorted(e.t for e in scoped if e.type == "hover_start")
    ends = sorted(e.t for e in scoped if e.type == "hover_end")
    if not starts:
        return None
    total_ms = 0.0
    for start in starts:
        end_candidates = [e for e in ends if e >= start]
        end = min(end_candidates) if end_candidates else window.t_end
        total_ms += max(0.0, end - start)
    if total_ms <= 0:
        return None
    return math.log1p(total_ms / 1000.0)


# 4. Max scroll depth -----------------------------------------------------------


def max_scroll_depth(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    samples = _scroll_samples(events, window)
    if not samples:
        return None
    return max(ratio for _t, ratio in samples)


# 5. Scroll reversals -------------------------------------------------------------


def scroll_reversals(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    samples = _scroll_samples(events, window)
    if len(samples) < 3:
        return None
    reversals = 0
    prev_dir = None
    for (_, r0), (_, r1) in zip(samples, samples[1:]):
        delta = r1 - r0
        if delta == 0:
            continue
        direction = 1 if delta > 0 else -1
        if prev_dir is not None and direction != prev_dir:
            reversals += 1
        prev_dir = direction
    return float(reversals)


# 6. Peak pointer velocity on approach ---------------------------------------------


def peak_pointer_velocity_on_approach(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Peak instantaneous speed among pointer samples in the view's
    opening window — the "approach" the visitor makes onto the card."""
    if ctx.pointer_type == "touch":
        return None
    samples = _pointer_samples(events, window)
    if len(samples) < 2:
        return None
    peak = 0.0
    for (t0, x0, y0), (t1, x1, y1) in zip(samples, samples[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        dist = math.hypot(x1 - x0, y1 - y0)
        peak = max(peak, dist / dt)
    return peak if peak > 0 else None


# 7. Trajectory curvature (area under curve) + x-flips ------------------------------


def trajectory_curvature_auc(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Area between the pointer path and the straight chord from its
    first to its last in-window point — a rotation-invariant curvature
    proxy (see tests/features/test_invariance.py)."""
    if ctx.pointer_type == "touch":
        return None
    samples = _pointer_samples(events, window)
    if len(samples) < 3:
        return None
    (x0, y0), (xn, yn) = (samples[0][1], samples[0][2]), (samples[-1][1], samples[-1][2])
    chord_len = math.hypot(xn - x0, yn - y0)
    if chord_len == 0:
        return None
    area = 0.0
    for _t, x, y in samples[1:-1]:
        # Perpendicular distance from (x, y) to the chord, via the
        # standard cross-product-over-length formula.
        area += abs((xn - x0) * (y0 - y) - (x0 - x) * (yn - y0)) / chord_len
    return area


def trajectory_x_flips(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    if ctx.pointer_type == "touch":
        return None
    samples = _pointer_samples(events, window)
    if len(samples) < 3:
        return None
    flips = 0
    prev_dir = None
    for (_, x0, _), (_, x1, _) in zip(samples, samples[1:]):
        dx = x1 - x0
        if dx == 0:
            continue
        direction = 1 if dx > 0 else -1
        if prev_dir is not None and direction != prev_dir:
            flips += 1
        prev_dir = direction
    return float(flips)


SignalFn = Callable[[list[RawEvent], WindowSpec, ItemContext], "float | None"]

SIGNAL_REGISTRY: dict[str, SignalFn] = {
    "item_dwell": item_dwell,
    "viewport_time": viewport_time,
    "hover_dwell_on_target": hover_dwell_on_target,
    "max_scroll_depth": max_scroll_depth,
    "scroll_reversals": scroll_reversals,
    "peak_pointer_velocity_on_approach": peak_pointer_velocity_on_approach,
    "trajectory_curvature_auc": trajectory_curvature_auc,
    "trajectory_x_flips": trajectory_x_flips,
}
