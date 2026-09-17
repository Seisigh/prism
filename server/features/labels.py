"""Label construction (§9.1) and the fast-skip negative-class definition
(§9.3 item 8, §9.5). Neither of these is a feature function — they never
appear in `signals.SIGNAL_REGISTRY` and the leakage test does not (and
should not) exempt them from the "no feature reads a sealed event" rule.
That's not a coincidence of implementation, it's the point: both
`tier1_label` and `is_fast_skip` are deliberately allowed to look at what
happens *after* the sealed window (session-wide commitment and revisit
events) precisely because they are the prediction targets, not inputs a
feature function is allowed to see. `is_fast_skip` originally looked only
at a view's own duration, which *is* fully determined at view close — but
that turned out to be unsafe on its own (see its docstring): a view's
duration alone can't disambiguate a confident reject from a confident
accept, so it now needs the same session-wide, forward-looking commitment
and revisit information `tier1_label` uses.
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


def is_fast_skip(
    view_duration_ms: float,
    item_id: str,
    view_start: float,
    commitment_events: list[CommitmentEvent],
    other_view_starts_for_item: list[float],
    threshold_ms: float = FAST_SKIP_THRESHOLD_MS_DEFAULT,
) -> bool:
    """The negative-class definition (§9.3 item 8). Duration alone is
    **not** safe: the simulator's own drift-diffusion process shows dwell
    is ∩-shaped in utility — longest near indifference, *shortest at
    either a confident reject or a confident accept* (a strong positive
    utility resolves to commitment just as fast as a strong negative one
    resolves to rejection). See STATE.md's "dwell vs. utility" section
    for the actual decile curve. Keying fast_skip on duration alone would
    therefore put the *strongest positives* — items decided on instantly
    — into the negative class alongside genuine fast rejections.

    Fast skip requires BOTH a short exposure AND no later commitment or
    revisit of that same item in the session: a short view that later
    gets committed to, or gets looked at again, was never a confident
    reject — it's ambiguous at best, and ambiguous is not the same as
    negative. Only a short view that is *never* returned to and *never*
    committed to is safely a fast skip.
    """
    if view_duration_ms >= threshold_ms:
        return False
    if tier1_label(item_id, view_start, commitment_events):
        return False  # committed later -> a fast decision toward yes, not a skip
    if any(t > view_start for t in other_view_starts_for_item):
        return False  # revisited later -> not a confident, final reject
    return True
