"""Human-readable descriptions of every registered behavioral signal
(§6.7 admin console legibility): what it measures, what a higher or
lower value implies, and when it's unavailable rather than zero.

This is the single source of truth the admin console's tooltips render
from — written once here, next to the functions it describes, instead of
as UI copy that could quietly drift out of sync with what the signal
functions actually compute. `server/ingest/admin_routes.py` serves this
dict verbatim; `server/features/` itself never imports from `ingest` (see
the import-linter contract in `pyproject.toml`), so this module only
describes signals, it never serves them.

Each entry's `unavailable_when` matches the actual early-return conditions
in the signal's own function — written by reading each one, not guessed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalDescription:
    measures: str
    higher: str
    lower: str
    unavailable_when: str


SIGNAL_DESCRIPTIONS: dict[str, SignalDescription] = {
    "item_dwell": SignalDescription(
        measures="log(1 + seconds) the sealed view window spanned — the oldest and simplest signal in the project.",
        higher="A longer look. Not simply 'more interested': STATE.md's ∩-shaped dwell finding means the longest "
        "views cluster near indifference (a genuinely hard call), not near strong preference in either direction.",
        lower="A brief glance — but a very short dwell is also what a confident accept or a confident reject both "
        "look like; short alone doesn't say which.",
        unavailable_when="Never — always computable once a qualifying view exists.",
    ),
    "viewport_time": SignalDescription(
        measures="Total time the card was actually ≥50% visible within the sealed window, log-scaled — can be less "
        "than the full window if visibility dipped in and out.",
        higher="The card stayed solidly on-screen for most of the view.",
        lower="Visibility was brief or intermittent relative to the window.",
        unavailable_when="No visibility samples ever reached the 50% threshold within the window.",
    ),
    "hover_dwell_on_target": SignalDescription(
        measures="Total hover time over the item's own element, log-scaled.",
        higher="The cursor rested on the item itself for longer, not just nearby.",
        lower="The cursor passed over without pausing on the item.",
        unavailable_when="Touch pointer (no hover concept exists), or no hover_start event was recorded in the window.",
    ),
    "max_scroll_depth": SignalDescription(
        measures="The furthest scroll ratio (0-1 down the page) reached while this item was in the sealed window.",
        higher="The visitor scrolled well past this item's position before the view closed.",
        lower="The visitor stayed near where this item first appeared.",
        unavailable_when="No scroll_sample events were recorded in the window.",
    ),
    "scroll_reversals": SignalDescription(
        measures="Count of scroll-direction changes (down-then-up or up-then-down) within the window.",
        higher="Back-and-forth scrolling — re-reading, searching back for something, or comparing against what's "
        "above/below.",
        lower="Scrolling stayed in one direction the whole time, or didn't happen.",
        unavailable_when="Fewer than 3 scroll samples in the window — not enough motion to detect a reversal.",
    ),
    "peak_pointer_velocity_on_approach": SignalDescription(
        measures="Peak instantaneous cursor speed among pointer samples in the view's opening — the 'approach' onto "
        "the card.",
        higher="A fast, direct approach onto the item.",
        lower="A slow, deliberate approach.",
        unavailable_when="Touch pointer, or fewer than 2 pointer samples in the window.",
    ),
    "trajectory_curvature_auc": SignalDescription(
        measures="Area between the actual pointer path and the straight chord from its first to last in-window "
        "point — a rotation-invariant curvature proxy, not raw distance traveled.",
        higher="A curved, indirect path onto the item — mouse-tracking literature reads this as decision conflict "
        "along the way, not just a longer path.",
        lower="A nearly straight line onto the item.",
        unavailable_when="Touch pointer, or fewer than 3 pointer samples, or the path's start and end points "
        "coincide (a zero-length chord).",
    ),
    "trajectory_x_flips": SignalDescription(
        measures="Number of times the cursor's horizontal direction reversed within the window.",
        higher="Repeated back-and-forth horizontal motion — hesitation between this item and something beside it.",
        lower="Horizontal motion stayed in one direction.",
        unavailable_when="Touch pointer, or fewer than 3 pointer samples.",
    ),
    "revisit_count": SignalDescription(
        measures="How many times this exact item was already viewed earlier in this same session.",
        higher="The visitor kept coming back to this specific item.",
        lower="First time seeing this item this session (0 is a real, known answer here, not a missing one).",
        unavailable_when="Never — always computable from session history.",
    ),
    "near_substitute_coview_count": SignalDescription(
        measures="How many other items from this item's near-substitute set were viewed nearby in time (mirrors "
        "the 120s window `mode.py` uses to detect comparison mode).",
        higher="The visitor is actively weighing this item against close alternatives.",
        lower="No nearby comparison against similar items (0 is a real, known answer).",
        unavailable_when="This item has no near-substitute set at all — there's no 'co-view count' for an item "
        "comparison mode could never trigger on.",
    ),
    "category_breadth": SignalDescription(
        measures="Count of distinct categories seen so far this session, including this item's own.",
        higher="Browsing is spanning multiple categories, not staying in one lane.",
        lower="Staying within a single category (1 is the common case — most sessions, real and simulated, never "
        "leave one category; see STATE.md's close-out investigation).",
        unavailable_when="This item's own category is unknown — a catalog-lookup failure, not a browsing fact.",
    ),
    "query_specificity": SignalDescription(
        measures="log(1 + token count) of the search query active when this view happened.",
        higher="A longer, more specific search query was driving this view.",
        lower="A short, broad query.",
        unavailable_when="No search query is active for this view — reached via discovery, refind, or comparison "
        "with nothing typed. There is no 'specificity of nothing.'",
    ),
    "pause_count": SignalDescription(
        measures="Number of times pointer speed drops below a stationary threshold and rises back above it — "
        "distinct stopping points along the path, not their total duration.",
        higher="Multiple hesitation stops along the approach.",
        lower="Continuous motion with no stops (0 is a real answer once there's enough motion to judge).",
        unavailable_when="Touch pointer, or fewer than 3 pointer samples.",
    ),
    "acceleration_profile": SignalDescription(
        measures="Peak absolute change in pointer speed per millisecond — abrupt speed changes, complementary to "
        "peak velocity's raw top speed.",
        higher="Sharp overshoot-and-correct motion — the cursor sped up or braked abruptly.",
        lower="Smooth, steady motion with no sudden speed changes.",
        unavailable_when="Touch pointer, or fewer than 3 pointer samples (need at least 2 velocity readings).",
    ),
    "focused_idle": SignalDescription(
        measures="Total time the pointer spent effectively stationary (speed below threshold) within the window — "
        "sustained fixation, distinct from pause_count's count of stops.",
        higher="Extended stretches with the cursor parked, not moving — sustained attention on one spot.",
        lower="The cursor kept moving throughout; little or no idle time.",
        unavailable_when="Touch pointer, or fewer than 2 pointer samples — most often because the tab was genuinely "
        "idle for the whole window, not because idling itself is unmeasurable.",
    ),
    "early_direction_bias": SignalDescription(
        measures="Scale-free ratio in [-1, 1] of how far the cursor leaned toward this item's own position versus "
        "the next item's position, integrated over the early part of the view (the final 1000ms before the window "
        "seals is always excluded, so this can't just restate the outcome).",
        higher="Positive — the cursor was already leaning toward this item early on, before the decision was final.",
        lower="Negative — the cursor was already leaning away, toward the next item, early on.",
        unavailable_when="No valid early window exists (common for short, decisive views whose first third falls "
        "entirely inside the excluded final 1000ms), or this surface has no meaningful 'next item' reject position.",
    ),
    "direction_lock_in_speed": SignalDescription(
        measures="How early the directional lean above locked in and never changed sign again, as a fraction of "
        "the view's own duration (higher = faster lock-in, independent of which way it leaned).",
        higher="Direction resolved quickly and stayed resolved.",
        lower="Direction stayed undecided longer, or flipped late in the view.",
        unavailable_when="Same as early_direction_bias — no accept/reject reference positions exist for this surface.",
    ),
}
