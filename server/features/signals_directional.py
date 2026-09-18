"""Directional motor signals -- added *after* diagnosing a real gap, not
alongside the original signal set. Write-up in STATE.md's "Eighteen
signals that measure magnitude, none that measure direction" section has
the full finding; the short version: every signal in `signals.py` and
`signals_gate1.py` measures the *magnitude or shape* of pointer motion
(how fast, how curved, how many reversals, how long a pause) -- none of
them measure *which* of the two real on-screen destinations (the item's
own action region, "accept," vs the next item / back control / scroll-
forward direction, "reject") the trajectory actually leaned toward. Once
`sim/generative.py`'s motor model was coupled to the DDM's evidence path
(so direction became mechanistically real in the trace), recovery still
didn't improve, because nothing read the new information out. These two
signals are that readout.

**The tautology this had to avoid, and how (author's ruling):** a
trajectory's *final* position is close to worthless as a feature -- at
the end of a view that led to a cart add, the cursor is already sitting
on the item, so "cursor near accept" would just be restating "committed"
under a different name, clearing the leakage test on a technicality
while measuring nothing. The actual claim in the mouse-tracking
literature is that *partial, still-resolving* evidence biases motor
output *before* the decision is final. So `early_direction_bias`
integrates only over the **first third of the view**, and separately
excludes the **final 1000ms before the window's own seal** regardless of
where that first-third boundary falls -- both restrictions applied
together, whichever produces the smaller window. A short view can
therefore have *no* valid early window at all (first-third boundary
falls inside the excluded final-1000ms zone); that's real, correctly-
reported unavailability (§9.2), not a bug -- see
`test_short_views_have_no_valid_early_window` for the case this produces
most often: the very fast, confident decisions this signal would
otherwise be most useful for.

`direction_stabilization_fraction` answers a different question ("how
early did the direction lock in," not "which way did it lean") and
scans the whole pre-exclusion window (not just the first third) for the
last point at which the sign of the direction ratio changed -- deferring
to whichever value the trajectory settled on before the final 1000ms,
never after.

**Scale-free by construction:** `(d_reject - d_accept) / (d_accept +
d_reject)`, bounded to [-1, 1] regardless of layout, viewport size, or
grid geometry -- positive leans accept, negative leans reject.

A third function, `_full_trajectory_direction_bias_DIAGNOSTIC_ONLY`,
computes the same ratio over the *entire* window with no exclusions --
this is the tautological version the design above exists to avoid, kept
only so a diagnostic script can show the contrast (a suspiciously strong
correlation with the outcome) directly. It is not registered in
`DIRECTIONAL_SIGNAL_REGISTRY` and must never be wired into a composite,
the ranker, or any other model input.
"""
from __future__ import annotations

import math

from server.features.signals import ItemContext, _pointer_samples
from server.features.window_spec import RawEvent, WindowSpec

EXCLUDE_BEFORE_SEAL_MS = 1000.0
EARLY_WINDOW_FRACTION = 1.0 / 3.0


def _direction_ratio(x: float, y: float, accept_pos: tuple[float, float], reject_pos: tuple[float, float]) -> float | None:
    d_accept = math.hypot(x - accept_pos[0], y - accept_pos[1])
    d_reject = math.hypot(x - reject_pos[0], y - reject_pos[1])
    denom = d_accept + d_reject
    if denom == 0:
        return None
    return (d_reject - d_accept) / denom


def _early_window(window: WindowSpec) -> WindowSpec | None:
    duration = window.t_end - window.t_start
    early_end = window.t_start + duration * EARLY_WINDOW_FRACTION
    exclusion_floor = window.t_end - EXCLUDE_BEFORE_SEAL_MS
    end = min(early_end, exclusion_floor)
    if end <= window.t_start:
        return None
    return WindowSpec(t_start=window.t_start, t_end=end, seal_reason=window.seal_reason)


def _pre_exclusion_window(window: WindowSpec) -> WindowSpec | None:
    end = window.t_end - EXCLUDE_BEFORE_SEAL_MS
    if end <= window.t_start:
        return None
    return WindowSpec(t_start=window.t_start, t_end=end, seal_reason=window.seal_reason)


def early_direction_bias(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Time-integrated (mean) scale-free direction ratio over the first
    third of the view, additionally excluding the final 1000ms before
    the seal. None if touch, if either destination is unknown for this
    surface, if the resulting window is empty, or if no pointer samples
    fall inside it."""
    if ctx.pointer_type == "touch" or ctx.accept_pos is None or ctx.reject_pos is None:
        return None
    sub_window = _early_window(window)
    if sub_window is None:
        return None
    samples = _pointer_samples(events, sub_window)
    ratios = [r for (_t, x, y) in samples for r in [_direction_ratio(x, y, ctx.accept_pos, ctx.reject_pos)] if r is not None]
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def direction_stabilization_fraction(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Fraction of the view's own duration (§: "as a fraction of view
    duration") elapsed before the direction ratio's sign locked in and
    never changed again, scanning the whole window minus the final
    1000ms before seal. Lower means direction committed earlier. None
    under the same conditions as `early_direction_bias`, plus when the
    final sign in the scanned window is exactly zero (no sign to have
    stabilized to)."""
    if ctx.pointer_type == "touch" or ctx.accept_pos is None or ctx.reject_pos is None:
        return None
    view_duration = window.t_end - window.t_start
    if view_duration <= 0:
        return None
    sub_window = _pre_exclusion_window(window)
    if sub_window is None:
        return None
    samples = _pointer_samples(events, sub_window)
    signed = [
        (t, (0 if r == 0 else (1 if r > 0 else -1)))
        for (t, x, y) in samples
        for r in [_direction_ratio(x, y, ctx.accept_pos, ctx.reject_pos)]
        if r is not None
    ]
    if not signed:
        return None
    final_sign = signed[-1][1]
    if final_sign == 0:
        return None
    t_lock = signed[-1][0]
    for t, s in reversed(signed):
        if s != final_sign:
            break
        t_lock = t
    fraction = (t_lock - window.t_start) / view_duration
    return min(1.0, max(0.0, fraction))


def _full_trajectory_direction_bias_DIAGNOSTIC_ONLY(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """The tautological version (author's ruling): the same ratio, but
    over the *entire* window with no early-window or seal-exclusion
    restriction, so it can include the moments right before the seal
    when the cursor is already resting on whichever target won. Kept
    only to demonstrate, in a diagnostic script, how strongly a
    leakage-shaped feature correlates with the outcome by construction.
    **Never register this in a signal registry or feed it to a
    composite, the ranker, or any other model input.**"""
    if ctx.pointer_type == "touch" or ctx.accept_pos is None or ctx.reject_pos is None:
        return None
    samples = _pointer_samples(events, window)
    ratios = [r for (_t, x, y) in samples for r in [_direction_ratio(x, y, ctx.accept_pos, ctx.reject_pos)] if r is not None]
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


DIRECTIONAL_SIGNAL_REGISTRY = {
    "early_direction_bias": early_direction_bias,
    "direction_stabilization_fraction": direction_stabilization_fraction,
}
