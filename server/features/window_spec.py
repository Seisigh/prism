"""Sealed feature windows (BUILD_BRIEF.md §9). Every signal function takes
an explicit `WindowSpec` and this module is the *only* place that decides
which raw events a window admits — signal functions call `events_in_window`
rather than filtering timestamps themselves, so there's one enforcement
point to audit, not N of them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SealReason = Literal["view_close", "commitment_seal", "session_end", "tab_blur", "navigation"]

COMMITMENT_SEAL_BUFFER_MS = 1000.0


@dataclass(frozen=True)
class WindowSpec:
    """[t_start, t_end) — half-open. `t_end` is exclusive: an event at
    exactly t_end is at-or-after the seal and must never be admitted."""

    t_start: float
    t_end: float
    seal_reason: SealReason

    def __post_init__(self) -> None:
        if self.t_end < self.t_start:
            raise ValueError(f"WindowSpec has t_end < t_start: {self.t_end} < {self.t_start}")


@dataclass(frozen=True)
class RawEvent:
    """The subset of the telemetry envelope (§7.1) feature functions need.
    `item_id` is None for events not scoped to a specific item (e.g. a
    scroll_batch on the whole viewport)."""

    t: float
    type: str
    item_id: str | None
    surface: str
    payload: dict


@dataclass(frozen=True)
class CommitmentEvent:
    """cart_add | wishlist | checkout_start for a specific item — the
    Tier-1 label source (§9.1) and the thing every window gets sealed
    against."""

    t: float
    item_id: str
    type: Literal["cart_add", "wishlist", "checkout_start"]


def seal_window_for_view(
    view_start: float,
    view_end: float,
    item_id: str,
    commitment_events: list[CommitmentEvent],
) -> WindowSpec:
    """§9.1: "Features for a view are computed from the view interval
    truncated at the first commitment event for that item, minus a
    1000ms buffer." If no commitment falls inside the view, the window is
    simply the view's own [start, end)."""
    relevant = [c.t for c in commitment_events if c.item_id == item_id and view_start <= c.t <= view_end]
    if not relevant:
        return WindowSpec(t_start=view_start, t_end=view_end, seal_reason="view_close")
    first_commit_t = min(relevant)
    sealed_end = first_commit_t - COMMITMENT_SEAL_BUFFER_MS
    # Never produce a negative-length window: if the commitment lands
    # within the buffer of view_start, the window collapses to zero
    # length rather than going negative. A zero-length window is a legal
    # input — every signal function must handle it by returning None,
    # exercised by test_leakage.py's zero-length-window case.
    sealed_end = max(sealed_end, view_start)
    return WindowSpec(t_start=view_start, t_end=sealed_end, seal_reason="commitment_seal")


def events_in_window(events: list[RawEvent], window: WindowSpec, item_id: str | None = None) -> list[RawEvent]:
    """The one enforcement point: `t_end` is exclusive, so an event at or
    after the seal is never returned. Signal functions must call this
    (or `has_commitment_...`-style helpers built on it) rather than
    filtering timestamps themselves."""
    out = [e for e in events if window.t_start <= e.t < window.t_end]
    if item_id is not None:
        out = [e for e in out if e.item_id == item_id]
    return out
