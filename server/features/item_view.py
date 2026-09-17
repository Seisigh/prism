"""The canonical item view (BUILD_BRIEF.md §8). One function, one source of
truth for dwell. Every downstream feature and every mode assignment reads
views produced here — nowhere else is allowed to compute a view boundary.

    A VIEW is a maximal interval where the item's card is >= 50% visible
      for >= 300ms continuously, merging gaps < 500ms into a single view.
    A DETAIL_VIEW is a distinct type: the product detail page for that item.
    When an item is visible in multiple surfaces at once, attribute the view
      to the surface holding pointer focus; ties resolve to the deepest
      surface (detail > compare > grid > rail).
    Close a view on: visibility below 50% for >= 500ms, navigation, tab
      blur, or session end.
    Mode is assigned at view OPEN and does not change mid-view.

This module only computes VIEW BOUNDARIES + surface attribution. Mode
assignment (§4) is a separate concern injected via a callback so the two
can be unit-tested independently — see server/features/mode.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

Surface = Literal["home", "category", "search", "detail", "compare", "cart"]

VISIBLE_RATIO_THRESHOLD = 0.5
MIN_QUALIFYING_DURATION_MS = 300.0
MAX_MERGE_GAP_MS = 500.0

# Deepest wins on a pointer-focus tie. Index = depth (higher is deeper).
_SURFACE_DEPTH = {"rail": 0, "grid": 0, "home": 0, "category": 0, "search": 0, "cart": 0, "compare": 1, "detail": 2}


@dataclass(frozen=True)
class VisibilitySample:
    """One IntersectionObserver reading for one (item, surface) pair.
    `t` is session-relative monotonic milliseconds (matches ts_mono)."""

    t: float
    item_id: str
    surface: str
    ratio: float


@dataclass(frozen=True)
class PointerFocusSample:
    """The surface the pointer is currently over, at time `t`. The most
    recent sample at or before a given instant determines focus there."""

    t: float
    surface: str


@dataclass(frozen=True)
class HardClose:
    """A navigation, tab-blur, or session-end event that force-closes any
    open view at time `t`, regardless of the 500ms grace gap."""

    t: float
    kind: Literal["navigation", "tab_blur", "session_end"]


@dataclass(frozen=True)
class ItemView:
    item_id: str
    surface: str
    start: float
    end: float
    mode: str
    closed_by: Literal["visibility_timeout", "navigation", "tab_blur", "session_end", "superseded"]

    @property
    def duration_ms(self) -> float:
        return self.end - self.start


ModeResolver = Callable[[str, str, float], str]
"""(item_id, surface, view_open_t) -> mode. Injected so item_view.py never
imports server.features.mode directly (keeps this module's own tests free
of mode-assignment fixtures) — see BUILD_BRIEF.md §3's boundary rule."""


def _default_mode_resolver(item_id: str, surface: str, t: float) -> str:
    return "discovery"


@dataclass
class _Run:
    start: float
    end: float


def _raw_runs(samples: list[VisibilitySample], end_horizon: float | None = None) -> list[_Run]:
    """Continuous ratio>=0.5 intervals from a time-sorted sample sequence
    for one (item, surface). Visibility is piecewise-constant, holding the
    last known ratio forward until the next sample (matches how a batched
    IntersectionObserver stream is actually recorded). A run still open at
    the last sample (no closing below-threshold sample yet — e.g. a live
    session being read mid-view, or a single-sample `view_start` with no
    `view_end` yet) extends to `end_horizon`, not to its own last sample's
    timestamp — otherwise a still-open single-sample run would collapse
    to zero duration and silently vanish."""
    if not samples:
        return []
    ordered = sorted(samples, key=lambda s: s.t)
    runs: list[_Run] = []
    run_start: float | None = None
    for i, s in enumerate(ordered):
        visible = s.ratio >= VISIBLE_RATIO_THRESHOLD
        if visible and run_start is None:
            run_start = s.t
        elif not visible and run_start is not None:
            runs.append(_Run(run_start, s.t))
            run_start = None
    if run_start is not None:
        horizon = end_horizon if end_horizon is not None else ordered[-1].t
        runs.append(_Run(run_start, max(horizon, run_start)))
    return runs


def _qualifying_seed_runs(runs: list[_Run]) -> list[_Run]:
    return [r for r in runs if (r.end - r.start) >= MIN_QUALIFYING_DURATION_MS]


def _merge_runs(seeds: list[_Run]) -> list[_Run]:
    """Merge seed runs separated by a gap < 500ms into one view span. A
    sub-300ms blip between two qualifying runs is implicitly absorbed by
    this merge (the view's span covers it) without needing its own
    duration to qualify — that's the whole point of the merge-gap rule."""
    if not seeds:
        return []
    ordered = sorted(seeds, key=lambda r: r.start)
    merged = [_Run(ordered[0].start, ordered[0].end)]
    for r in ordered[1:]:
        last = merged[-1]
        if r.start - last.end < MAX_MERGE_GAP_MS:
            last.end = max(last.end, r.end)
        else:
            merged.append(_Run(r.start, r.end))
    return merged


def _pointer_surface_at(t: float, focus_samples: list[PointerFocusSample]) -> str | None:
    candidates = [f for f in focus_samples if f.t <= t]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.t).surface


def _hard_close_at_or_after(t_start: float, closes: list[HardClose]) -> HardClose | None:
    after = [c for c in closes if c.t > t_start]
    return min(after, key=lambda c: c.t) if after else None


def compute_item_views(
    visibility_samples: list[VisibilitySample],
    pointer_focus_samples: list[PointerFocusSample] | None = None,
    hard_closes: list[HardClose] | None = None,
    mode_resolver: ModeResolver | None = None,
    session_horizon: float | None = None,
) -> list[ItemView]:
    """Computes canonical views for every item present in
    `visibility_samples`. Pure function — no I/O, no storage, no
    knowledge of ingest or transport, per §3's package boundary.
    """
    pointer_focus_samples = pointer_focus_samples or []
    hard_closes = sorted(hard_closes or [], key=lambda c: c.t)
    resolve_mode = mode_resolver or _default_mode_resolver

    # A still-open run (e.g. a `view_start` with no `view_end` yet,
    # because the log is being read mid-session) extends to the latest
    # timestamp seen anywhere in the input, not to its own single sample
    # — see _raw_runs' docstring. This fallback is deliberately separate
    # from `session_horizon`: it's just "the last thing we observed," not
    # a genuine session boundary, so it must never feed the `closed_by`
    # attribution below (that's `session_horizon`'s job, and only when
    # the caller explicitly knows the session actually ended there).
    open_run_horizon = max(s.t for s in visibility_samples) if visibility_samples else None

    by_item_surface: dict[tuple[str, str], list[VisibilitySample]] = {}
    for s in visibility_samples:
        by_item_surface.setdefault((s.item_id, s.surface), []).append(s)

    # Phase 1+2: per (item, surface) qualifying + merged candidate spans.
    candidates: dict[str, list[tuple[str, _Run]]] = {}
    for (item_id, surface), samples in by_item_surface.items():
        seeds = _qualifying_seed_runs(_raw_runs(samples, end_horizon=open_run_horizon))
        for run in _merge_runs(seeds):
            candidates.setdefault(item_id, []).append((surface, run))

    views: list[ItemView] = []
    for item_id, surface_runs in candidates.items():
        # Phase 4: multi-surface attribution. Overlapping runs across
        # surfaces for the same item resolve to one winner by pointer
        # focus at the overlap's start, tie-broken by surface depth.
        surface_runs.sort(key=lambda sr: sr[1].start)
        resolved: list[tuple[str, _Run]] = []
        for surface, run in surface_runs:
            overlap = None
            for i, (other_surface, other_run) in enumerate(resolved):
                if run.start < other_run.end and other_run.start < run.end:
                    overlap = (i, other_surface, other_run)
                    break
            if overlap is None:
                resolved.append((surface, run))
                continue

            idx, other_surface, other_run = overlap
            focus = _pointer_surface_at(max(run.start, other_run.start), pointer_focus_samples)
            if focus == surface:
                winner = surface
            elif focus == other_surface:
                winner = other_surface
            else:
                winner = max(
                    (surface, other_surface), key=lambda sfc: _SURFACE_DEPTH.get(sfc, 0)
                )
            if winner == other_surface:
                # This run loses; keep only the non-overlapping remainder,
                # if any, provided it still meets the qualifying duration.
                if run.start < other_run.start and (other_run.start - run.start) >= MIN_QUALIFYING_DURATION_MS:
                    resolved.append((surface, _Run(run.start, other_run.start)))
                if run.end > other_run.end and (run.end - other_run.end) >= MIN_QUALIFYING_DURATION_MS:
                    resolved.append((surface, _Run(other_run.end, run.end)))
            else:
                # This run wins; shrink the earlier one to before the
                # overlap (dropping it if that remainder no longer
                # qualifies), and let this run stand for the overlap plus
                # any tail beyond it.
                if other_run.start < run.start and (run.start - other_run.start) >= MIN_QUALIFYING_DURATION_MS:
                    resolved[idx] = (other_surface, _Run(other_run.start, run.start))
                else:
                    resolved.pop(idx)
                resolved.append((surface, run))

        # Phase 3: hard closes (navigation / tab blur / session end) clip
        # any run they fall inside; a run reopens as a fresh candidate
        # after the interruption only if the caller supplied later
        # visibility samples showing that (handled naturally since those
        # samples produce their own seed runs above).
        for surface, run in resolved:
            close = _hard_close_at_or_after(run.start, hard_closes)
            end = run.end
            closed_by: ItemView["closed_by"] = "visibility_timeout"
            if close is not None and close.t < end:
                end = close.t
                closed_by = close.kind  # type: ignore[assignment]
            elif session_horizon is not None and end >= session_horizon:
                closed_by = "session_end"
            if end - run.start < MIN_QUALIFYING_DURATION_MS:
                continue
            mode = resolve_mode(item_id, surface, run.start)
            views.append(ItemView(item_id=item_id, surface=surface, start=run.start, end=end, mode=mode, closed_by=closed_by))

    return sorted(views, key=lambda v: (v.item_id, v.start))
