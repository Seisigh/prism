"""Browsing mode assignment (BUILD_BRIEF.md §4) — the stratum, not a
feature column. Mode is assigned once, at view open, under strict
precedence: refind > comparison > directed_search > broad_search >
discovery. Every function here is pure and takes its inputs explicitly;
nothing reads global or hidden state, so it's independently testable from
`item_view.py` (which injects this module's `assign_mode` as a callback
rather than importing it at call sites — see item_view.py's docstring).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Mode = Literal["refind", "comparison", "directed_search", "broad_search", "discovery"]

QUERY_ACTIVE_WINDOW_MS = 180_000
REFIND_MIN_GAP_MS = 60_000
COMPARISON_WINDOW_MS = 120_000

# A token that looks like a model/SKU code: has a digit, short, alnum/hyphen.
# Mirrors catalog/titles.py's _SKU_LIKE heuristic — same judgment call,
# same shape of evidence (a token with a digit reads as a model number).
_MODEL_TOKEN_RE = re.compile(r"^[a-z]{0,4}-?\d+[a-z0-9-]*$", re.IGNORECASE)


def _tokenize(query: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9-]+", query.lower()) if t]


def classify_query_tokens(query: str, brand_tokens: set[str]) -> Literal["directed", "broad"]:
    """§4.1: "directed_search: Active query containing a model token, an
    invented-brand token, or >=3 tokens." Else broad_search."""
    tokens = _tokenize(query)
    if len(tokens) >= 3:
        return "directed"
    if any(_MODEL_TOKEN_RE.match(t) for t in tokens):
        return "directed"
    lowered_brands = {b.lower() for b in brand_tokens}
    if any(t in lowered_brands for t in tokens):
        return "directed"
    return "broad"


@dataclass(frozen=True)
class QuerySubmission:
    submitted_at: float
    query: str


def is_query_active(
    t: float,
    submission: QuerySubmission | None,
    category_nav_click_at: float | None = None,
) -> bool:
    """A query is active for 180s after submission, or until a
    category-nav click, whichever comes first."""
    if submission is None or t < submission.submitted_at:
        return False
    if t - submission.submitted_at >= QUERY_ACTIVE_WINDOW_MS:
        return False
    if category_nav_click_at is not None and submission.submitted_at <= category_nav_click_at <= t:
        return False
    return True


@dataclass(frozen=True)
class PriorView:
    item_id: str
    start: float
    near_substitute_set_id: str | None = None


def is_refind(t: float, item_id: str, prior_views: list[PriorView]) -> bool:
    """Item was viewed >=1 time earlier this session, >=60s prior."""
    return any(v.item_id == item_id and (t - v.start) >= REFIND_MIN_GAP_MS for v in prior_views)


def is_comparison(
    t: float,
    item_id: str,
    near_substitute_set_id: str | None,
    prior_views: list[PriorView],
) -> bool:
    """>=2 views of items within the same near-substitute set inside a
    120s window — the current view is one of the two, so this checks for
    >=1 *other* item from the same set viewed within the last 120s."""
    if near_substitute_set_id is None:
        return False
    window_start = t - COMPARISON_WINDOW_MS
    return any(
        v.near_substitute_set_id == near_substitute_set_id
        and v.item_id != item_id
        and window_start <= v.start <= t
        for v in prior_views
    )


def assign_mode(
    t: float,
    item_id: str,
    near_substitute_set_id: str | None,
    prior_views: list[PriorView],
    active_query: QuerySubmission | None,
    category_nav_click_at: float | None,
    brand_tokens: set[str],
) -> Mode:
    """Precedence: refind > comparison > directed_search > broad_search >
    discovery. `discovery` is the fallback per §4.1's table: no active
    query, arrived via home rail / category grid / recommendation rail —
    every surface that isn't `search` reaches this branch when no query is
    active, so no separate "arrival surface" input is needed."""
    if is_refind(t, item_id, prior_views):
        return "refind"
    if is_comparison(t, item_id, near_substitute_set_id, prior_views):
        return "comparison"
    if is_query_active(t, active_query, category_nav_click_at):
        assert active_query is not None
        return "directed_search" if classify_query_tokens(active_query.query, brand_tokens) == "directed" else "broad_search"
    return "discovery"
