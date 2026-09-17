"""Label construction (§9.1) and the fast-skip negative-class definition
(§9.3 item 8, §9.5). Neither of these is a feature function — they never
appear in `signals.SIGNAL_REGISTRY` and the leakage test does not (and
should not) exempt them from the "no feature reads a sealed event" rule,
because they aren't asserting the same thing: the label is deliberately
allowed to look at what happens *after* the sealed window (that's the
prediction target), while the fast-skip threshold looks only at a view's
own duration, which is fully determined at view close.
"""
from __future__ import annotations

from server.features.window_spec import CommitmentEvent


def tier1_label(item_id: str, view_start: float, commitment_events: list[CommitmentEvent]) -> bool:
    """§9.1: "a commitment event (cart add, wishlist, or checkout) for
    that item later in the session." Deliberately session-wide, not
    bounded by the view's own end — a visitor often adds to cart from a
    later view, or from the cart page itself, not the original view.
    This is the *training label*; it must never be fed into
    `signals.py`'s feature functions (that would be the label leaking
    into the features it's supposed to predict)."""
    return any(c.item_id == item_id and c.t >= view_start for c in commitment_events)


# §9.5: "Not a hardcoded constant. Fit the exposure distribution per
# surface and mode, take the antimode of the bimodal fit, and freeze the
# result in a committed constant with the fitting notebook beside it."
#
# There is no real session data to fit against yet at this point in the
# build (Gate 0 has no simulator and no deployed traffic) — that's a
# bootstrap problem the brief doesn't resolve for a from-scratch build.
# This placeholder uses Lagun & Lalmas (2016) engagement banding (the
# brief's own documented fallback for a non-bimodal distribution) as a
# reasonable Gate 0 default, and is flagged in STATE.md as needing the
# real per-(surface, mode) fit once simulated + real traces exist in
# Gate 1. Swapping this constant for a fitted dict is a one-line change
# at every call site below.
FAST_SKIP_THRESHOLD_MS_DEFAULT = 1500.0


def is_fast_skip(view_duration_ms: float, threshold_ms: float = FAST_SKIP_THRESHOLD_MS_DEFAULT) -> bool:
    """The negative-class definition: a view shorter than the fast-skip
    threshold is treated as a negative example of interest, not merely a
    view with no signal. Never used as a feature value itself."""
    return view_duration_ms < threshold_ms
