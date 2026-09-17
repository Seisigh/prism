"""Gate 1 additions to the signal set (BUILD_BRIEF.md §9.4): "revisit
count, focused idle, acceleration profile, pause count, category
breadth, query specificity, attention split across spec/images/reviews,
zoom and gallery advances — all safe."

Six of those eight are implemented here, all computable from event types
the SDK already emits (pointer_sample, plus session-level context the
caller supplies via `ItemContext`) — no new instrumentation needed:

- `revisit_count`, `category_breadth`, `query_specificity` read only
  `ItemContext`'s Gate-1 fields (session history *up to but excluding*
  this view — the caller's responsibility, not this module's; see
  `ItemContext`'s docstring in signals.py).
- `pause_count`, `acceleration_profile`, `focused_idle` read only
  in-window `pointer_sample` events, the same primitive
  `peak_pointer_velocity_on_approach` already uses.

**Deliberately not implemented, and not silently approximated:**
`attention_split_spec_images_reviews` and `zoom_and_gallery_advances`
need event types the SDK does not emit yet (DOM-region-scoped
visibility, and gallery/zoom interaction events) — flagged in STATE.md
as a real gap rather than faked from unrelated data.

Every function still follows §9.2: `None` for genuinely unavailable,
never an imputed zero. A count that is always knowable from session
history (revisit_count, category_breadth) returns 0.0 / 1.0 rather than
None when the true answer is "none yet" — that is a real, known value,
not a missing one; the Gate 0 module's own `hover_dwell_on_target`
already draws this same distinction (no hover *events* -> None, not "0
seconds of hover").
"""
from __future__ import annotations

import math

from server.features.signals import ItemContext, _pointer_samples
from server.features.window_spec import RawEvent, WindowSpec

PAUSE_VELOCITY_THRESHOLD_PX_PER_MS = 0.05


# 1. Revisit count --------------------------------------------------------------


def revisit_count(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """How many times this exact item was already viewed earlier this
    session. Always computable from session history -> never None."""
    return float(len(ctx.prior_view_starts_for_item))


def near_substitute_coview_count(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """How many *other* items from this item's near-substitute set were
    viewed nearby in time (the caller mirrors is_comparison's own 120s
    window when computing this, per server/features/mode.py). None if
    this item has no near-substitute set at all -- there is no
    "co-view count" for an item comparison mode could never trigger on."""
    if ctx.near_substitute_coview_count is None:
        return None
    return float(ctx.near_substitute_coview_count)


# 2. Category breadth -------------------------------------------------------------


def category_breadth(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Distinct categories seen so far this session, including this
    view's own item. None only if the caller genuinely doesn't know this
    item's category (a catalog-lookup failure, not a browsing fact)."""
    if ctx.category is None:
        return None
    return float(len(set(ctx.prior_view_categories) | {ctx.category}))


# 3. Query specificity --------------------------------------------------------------


def query_specificity(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """log1p(token count) of the currently-active search query. None
    when no query is active for this view (discovery/refind/comparison
    reached without one) -- there is no "specificity of nothing"."""
    if ctx.active_query_token_count is None:
        return None
    return math.log1p(float(ctx.active_query_token_count))


# 4. Pause count -----------------------------------------------------------------


def _velocities(samples: list[tuple[float, float, float]]) -> list[float]:
    out = []
    for (t0, x0, y0), (t1, x1, y1) in zip(samples, samples[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        out.append(math.hypot(x1 - x0, y1 - y0) / dt)
    return out


def pause_count(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Number of times pointer speed drops below threshold then rises
    back above it within the window -- a proxy for hesitation stops
    along the approach/fixation path. Touch has no pointer trajectory."""
    if ctx.pointer_type == "touch":
        return None
    samples = _pointer_samples(events, window)
    if len(samples) < 3:
        return None
    velocities = _velocities(samples)
    if not velocities:
        return None
    pauses = 0
    in_pause = False
    for v in velocities:
        if v < PAUSE_VELOCITY_THRESHOLD_PX_PER_MS:
            if not in_pause:
                pauses += 1
                in_pause = True
        else:
            in_pause = False
    return float(pauses)


# 5. Acceleration profile -----------------------------------------------------------


def acceleration_profile(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Peak |change in speed per ms| across the window -- a second-order
    complement to peak_pointer_velocity_on_approach, capturing abrupt
    speed changes (overshoot-and-correct) rather than raw top speed."""
    if ctx.pointer_type == "touch":
        return None
    samples = _pointer_samples(events, window)
    if len(samples) < 3:
        return None
    velocities = _velocities(samples)
    if len(velocities) < 2:
        return None
    peak = 0.0
    for i in range(len(velocities) - 1):
        dt = samples[i + 2][0] - samples[i][0]
        if dt <= 0:
            continue
        peak = max(peak, abs(velocities[i + 1] - velocities[i]) / dt)
    return peak if peak > 0 else None


# 6. Focused idle -----------------------------------------------------------------


def focused_idle(events: list[RawEvent], window: WindowSpec, ctx: ItemContext) -> float | None:
    """Total time (ms) the pointer spent effectively stationary
    (speed below threshold) within the window -- sustained fixation
    without movement, distinct from pause_count's *number* of stops."""
    if ctx.pointer_type == "touch":
        return None
    samples = _pointer_samples(events, window)
    if len(samples) < 2:
        return None
    idle_ms = 0.0
    for (t0, x0, y0), (t1, x1, y1) in zip(samples, samples[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        speed = math.hypot(x1 - x0, y1 - y0) / dt
        if speed < PAUSE_VELOCITY_THRESHOLD_PX_PER_MS:
            idle_ms += dt
    return idle_ms if idle_ms > 0 else None


GATE1_SIGNAL_REGISTRY = {
    "revisit_count": revisit_count,
    "near_substitute_coview_count": near_substitute_coview_count,
    "category_breadth": category_breadth,
    "query_specificity": query_specificity,
    "pause_count": pause_count,
    "acceleration_profile": acceleration_profile,
    "focused_idle": focused_idle,
}
