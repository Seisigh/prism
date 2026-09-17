"""Offline recomputation: turns a session's raw stored event log back into
canonical item views + modes using the exact same pure functions the SDK
mirrors online (item_view.py, mode.py). This is both:

1. The engine behind the Gate 0 manual gate's event-log viewer (§10.14) —
   the author reads the raw log and this recomputation side by side.
2. The "offline" half of the §10.9 skew test, compared against the
   "online" mode the SDK attached to each event in real time.

Known simplification, logged rather than silently assumed correct: the
SDK's `recordCategoryNavClick` (which can expire an active query early,
§4.1) isn't its own persisted event type — §7.2's type list has no slot
for it. This recomputation treats a `page_view` on the `category` surface
as a proxy for a category-nav click, which is right in the common case
(arriving at a category page via the nav strip) but not exhaustive (a
category page reached another way, e.g. browser back, wouldn't have been
a real nav click). That's a genuine, small source of online/offline mode
skew, which is exactly the thing the skew test exists to surface rather
than paper over.
"""
from __future__ import annotations

from server.features.item_view import HardClose, ItemView, PointerFocusSample, VisibilitySample, compute_item_views
from server.features.mode import PriorView, QuerySubmission, assign_mode
from server.features.window_spec import CommitmentEvent

_COMMITMENT_TYPES = {"cart_add": "cart_add", "wishlist": "wishlist", "checkout_start": "checkout_start"}


def _visibility_samples_from_raw(events: list[dict]) -> list[VisibilitySample]:
    """view_start/view_end are already threshold-crossing events off the
    SDK's naive IntersectionObserver watcher (see sdk/src/itemVisibility.ts) —
    translating them to synthetic ratio=1.0/0.0 samples at those exact
    timestamps reconstructs the identical boolean signal item_view.py's
    `_raw_runs` expects, so the real merge/300ms/500ms rules apply on
    top of it here, offline, same as they would in a live pipeline."""
    samples = []
    for e in events:
        if e["type"] == "view_start":
            item_id = e["payload"].get("item_id")
            if item_id:
                samples.append(VisibilitySample(t=e["ts_mono"], item_id=item_id, surface=e["surface"], ratio=1.0))
        elif e["type"] == "view_end":
            item_id = e["payload"].get("item_id")
            if item_id:
                samples.append(VisibilitySample(t=e["ts_mono"], item_id=item_id, surface=e["surface"], ratio=0.0))
    return samples


def _hard_closes_from_raw(events: list[dict]) -> list[HardClose]:
    closes = []
    first_page_view_skipped = False
    for e in events:
        if e["type"] == "visibility_change" and e["payload"].get("hidden"):
            closes.append(HardClose(t=e["ts_mono"], kind="tab_blur"))
        elif e["type"] == "session_end":
            closes.append(HardClose(t=e["ts_mono"], kind="session_end"))
        elif e["type"] == "page_view":
            if not first_page_view_skipped:
                first_page_view_skipped = True  # the session's first page load isn't a "navigation away"
                continue
            closes.append(HardClose(t=e["ts_mono"], kind="navigation"))
    return closes


def _commitment_events_from_raw(events: list[dict]) -> list[CommitmentEvent]:
    out = []
    for e in events:
        if e["type"] in _COMMITMENT_TYPES:
            item_id = e["payload"].get("item_id")
            if item_id:
                out.append(CommitmentEvent(t=e["ts_mono"], item_id=item_id, type=_COMMITMENT_TYPES[e["type"]]))
    return out


def _category_nav_click_times(events: list[dict]) -> list[float]:
    out = []
    seen_first = False
    for e in events:
        if e["type"] == "page_view" and e["surface"] == "category":
            if not seen_first:
                seen_first = True
            out.append(e["ts_mono"])
    return sorted(out)


def _query_submissions(events: list[dict]) -> list[QuerySubmission]:
    return sorted(
        (
            QuerySubmission(submitted_at=e["ts_mono"], query=e["payload"].get("query", ""))
            for e in events
            if e["type"] == "search"
        ),
        key=lambda q: q.submitted_at,
    )


def _brand_tokens_from_context(brand_tokens: set[str] | None) -> set[str]:
    return brand_tokens or set()


def recompute_session(
    events: list[dict],
    near_substitute_set_by_item: dict[str, str] | None = None,
    brand_tokens: set[str] | None = None,
) -> list[ItemView]:
    """The single entry point: raw stored events in, canonical
    (view, mode) pairs out. `near_substitute_set_by_item` and
    `brand_tokens` are catalog-derived context the raw event log alone
    doesn't carry (mirrors what the SDK receives from the host app)."""
    events = sorted(events, key=lambda e: (e["ts_mono"], e["seq"]))
    near_substitute_set_by_item = near_substitute_set_by_item or {}
    resolved_brand_tokens = _brand_tokens_from_context(brand_tokens)

    visibility = _visibility_samples_from_raw(events)
    hard_closes = _hard_closes_from_raw(events)
    queries = _query_submissions(events)
    nav_clicks = _category_nav_click_times(events)

    prior_views: list[PriorView] = []

    def mode_resolver(item_id: str, surface: str, t: float) -> str:
        active_query = next((q for q in reversed(queries) if q.submitted_at <= t), None)
        nav_click_at = next((c for c in reversed(nav_clicks) if c <= t), None)
        set_id = near_substitute_set_by_item.get(item_id)
        mode = assign_mode(
            t=t,
            item_id=item_id,
            near_substitute_set_id=set_id,
            prior_views=prior_views,
            active_query=active_query,
            category_nav_click_at=nav_click_at,
            brand_tokens=resolved_brand_tokens,
        )
        prior_views.append(PriorView(item_id=item_id, start=t, near_substitute_set_id=set_id))
        return mode

    return compute_item_views(
        visibility_samples=visibility,
        pointer_focus_samples=_pointer_focus_from_raw(events),
        hard_closes=hard_closes,
        mode_resolver=mode_resolver,
    )


def _pointer_focus_from_raw(events: list[dict]) -> list[PointerFocusSample]:
    # Every raw event already carries the surface it happened on; treating
    # each as a focus sample for that surface is a reasonable proxy for
    # "which surface the visitor's attention was on" without needing to
    # decode individual pointer_batch target_ids.
    return [PointerFocusSample(t=e["ts_mono"], surface=e["surface"]) for e in events]
