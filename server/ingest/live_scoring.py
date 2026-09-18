"""Ties a session's real event log to a pushed profile update -- the §12
"trigger -> pushed update" path the load test measures p95 latency
against. Recomputes this session's canonical views from its *full* real
event log on every call (§9.2: "recomputed at each trigger, not
incrementally folded... removes online/offline divergence at the root"),
scores every not-yet-scored closed view against the trained ranker,
folds each into the session's taste vector in chronological order, and
returns the payload `server/ingest/routes.py` pushes back over the
WebSocket connection that triggered it.

Returns `None` when there is nothing new to report: no ranker trained
yet, no closed views at all, or no view has closed since the last call
for this session. The caller (routes.py) simply skips the push in that
case -- never invents an update to send.
"""
from __future__ import annotations

import json
from uuid import UUID

import redis.asyncio as redis

from server.catalog_store import get_store
from server.features.live import LiveView, extract_session_features, view_is_fast_skip
from server.features.replay import recompute_session
from server.features.window_spec import CommitmentEvent
from server.models import ranker_store
from server.models.taste_vector import MIN_SCORED_VIEWS_FOR_OWN_VECTOR, normalize, update, weight_from_calibrated_interest
from sim.embedding import DIMENSIONS, build_item_vectors

_COMMITMENT_TYPES = {"cart_add", "wishlist", "checkout_start"}
_STATE_TTL_SECONDS = 1800  # matches the session idle timeout

_item_vectors_cache = None
_catalog_centroid_cache: tuple[float, ...] | None = None


def _item_vectors():
    global _item_vectors_cache, _catalog_centroid_cache
    if _item_vectors_cache is None:
        _item_vectors_cache = build_item_vectors()
        vectors = [iv.vector for iv in _item_vectors_cache.values()]
        dims = len(vectors[0])
        _catalog_centroid_cache = tuple(sum(v[d] for v in vectors) / len(vectors) for d in range(dims))
    return _item_vectors_cache


def _catalog_centroid() -> tuple[float, ...]:
    _item_vectors()
    return _catalog_centroid_cache


def _taste_state_key(session_id: UUID) -> str:
    return f"prism:session:{session_id}:taste_vector"


def _last_scored_end_key(session_id: UUID) -> str:
    return f"prism:session:{session_id}:last_scored_view_end"


async def _load_taste_state(r: redis.Redis, session_id: UUID) -> tuple[tuple[float, ...], int]:
    raw = await r.get(_taste_state_key(session_id))
    if raw is None:
        return normalize(_catalog_centroid()), 0
    data = json.loads(raw)
    return tuple(data["vector"]), data["scored_view_count"]


async def _save_taste_state(r: redis.Redis, session_id: UUID, vector: tuple[float, ...], scored_view_count: int) -> None:
    await r.set(
        _taste_state_key(session_id),
        json.dumps({"vector": list(vector), "scored_view_count": scored_view_count}),
        ex=_STATE_TTL_SECONDS,
    )


def _commitment_events_from_rows(rows: list[dict]) -> list[CommitmentEvent]:
    return [
        CommitmentEvent(t=r["ts_mono"], item_id=r["payload"]["item_id"], type=r["type"])
        for r in rows
        if r["type"] in _COMMITMENT_TYPES and r["payload"].get("item_id")
    ]


async def score_session_update(r: redis.Redis, session_id: UUID, event_rows: list[dict]) -> dict | None:
    if not ranker_store.is_trained():
        return None

    store = get_store()
    near_substitute_set_by_item = {i["item_id"]: i["near_substitute_set_id"] for i in store.core_items if i["near_substitute_set_id"]}
    brand_tokens: set[str] = set()
    for item in store.all_items:
        brand_tokens.update(item["brand"].lower().replace("&", " ").split())

    # recompute_session (item_view.py's compute_item_views) returns views
    # sorted by (item_id, start) -- grouped for the admin console's event
    # log viewer, not chronological. Real, previously-undiscovered bug
    # caught by eval/load_test.py: with that ordering, `item_views[-1]`
    # is whichever item sorts alphabetically last, not whichever view
    # closed most recently, so a genuinely-new closed view could be
    # silently skipped whenever its item_id doesn't happen to sort last.
    # Re-sorting chronologically here is required before any of the
    # "what's new since last call" logic below.
    item_views = sorted(
        recompute_session(event_rows, near_substitute_set_by_item, brand_tokens),
        key=lambda v: (v.end, v.start),
    )
    if not item_views:
        return None

    last_scored_end_raw = await r.get(_last_scored_end_key(session_id))
    last_scored_end = float(last_scored_end_raw) if last_scored_end_raw is not None else -1.0
    if item_views[-1].end <= last_scored_end:
        return None  # nothing has closed since the last call

    live_views = [
        LiveView(
            item_id=v.item_id,
            surface=v.surface,
            mode=v.mode,
            start=v.start,
            end=v.end,
            category=store.by_id.get(v.item_id, {}).get("category"),
            near_substitute_set_id=near_substitute_set_by_item.get(v.item_id),
        )
        for v in item_views
    ]
    normalized = extract_session_features(event_rows, live_views)
    commitment_events = _commitment_events_from_rows(event_rows)
    item_vectors = _item_vectors()

    vector, scored_view_count = await _load_taste_state(r, session_id)
    last_p_i = None
    last_item_id = None

    for view, live_view, norm in zip(item_views, live_views, normalized):
        if view.end <= last_scored_end:
            continue
        _, p_i = ranker_store.score(view.mode, norm)
        fast_skip = view_is_fast_skip(live_view, live_views, commitment_events)
        if p_i is None and not fast_skip:
            continue  # unscoreable and not a fast skip -- nothing to fold in
        w_i = weight_from_calibrated_interest(p_i if p_i is not None else 0.0, fast_skip)
        item_vec = item_vectors.get(view.item_id)
        if item_vec is None:
            continue
        vector = update(vector, w_i, item_vec.vector)
        scored_view_count += 1
        last_p_i, last_item_id = p_i, view.item_id

    await _save_taste_state(r, session_id, vector, scored_view_count)
    await r.set(_last_scored_end_key(session_id), str(item_views[-1].end), ex=_STATE_TTL_SECONDS)

    public_vector = vector if scored_view_count >= MIN_SCORED_VIEWS_FOR_OWN_VECTOR else normalize(_catalog_centroid())
    return {
        "type": "profile_update",
        "scored_view_count": scored_view_count,
        "vector": list(public_vector),
        "dimensions": list(DIMENSIONS),
        "last_item_id": last_item_id,
        "last_p_i": last_p_i,
    }
