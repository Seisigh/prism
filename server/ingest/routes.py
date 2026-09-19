"""WebSocket + HTTP ingest endpoints (§7). Telemetry safety (§7.4): every
handler here degrades to a dropped batch rather than crashing the
connection or blocking the visitor's browsing — malformed envelopes are
logged and skipped, not fatal.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from server.catalog_store import get_store
from server.features.replay import recompute_session
from server.ingest.app_config import get_active_season
from server.ingest.db import get_pg_pool, get_redis
from server.ingest.envelope import Envelope
from server.ingest.live_scoring import score_session_update
from server.ingest.store import (
    delete_sessions_by_code,
    ensure_session,
    find_session_ids_by_code,
    get_session_events,
    insert_events,
    update_session_device,
)

logger = logging.getLogger("prism.ingest")
router = APIRouter()

MAX_BATCH_SIZE = 500  # backpressure: a single batch this large is dropped, not queued (§7.4)


def _parse_batch(raw: list[dict]) -> list[Envelope]:
    envelopes = []
    for item in raw:
        try:
            envelopes.append(Envelope.model_validate(item))
        except ValidationError as e:
            logger.warning("dropped malformed envelope: %s", e)
    return envelopes


async def _capture_device_info(pool, envelopes: list[Envelope]) -> None:
    """The SDK sends device info exactly once, in the first `page_view`
    event's payload (sdk/index.ts's `init()`), not in the envelope
    itself (§7.1 doesn't carry it). Scans every batch for one rather
    than assuming it's always the very first event a session sends --
    a retransmit or reconnect could reorder batches at the edges."""
    for e in envelopes:
        if e.type == "page_view" and isinstance(e.payload.get("device"), dict):
            await update_session_device(pool, e.session_id, e.payload["device"])


async def _maybe_push_profile_update(websocket: WebSocket, pool, r, session_id: UUID) -> None:
    """§12's live scoring path: view closes -> real features -> ranker
    score -> calibration -> taste-vector update -> pushed WebSocket
    message, all on the semantic trigger of an event batch that closed a
    view. Wrapped per §7.4 ("telemetry never breaks the UI"): a scoring
    failure is logged and swallowed, never allowed to drop the
    connection or block ingest of the next batch."""
    try:
        events = await get_session_events(pool, session_id)
        update = await score_session_update(r, session_id, events)
        if update is not None:
            await websocket.send_json(update)
    except Exception:
        logger.exception("live scoring failed for session %s; continuing without a push", session_id)


@router.websocket("/ws")
async def telemetry_ws(websocket: WebSocket, session_id: UUID = Query(...), code: str = Query(...)):
    # `code` is the visitor-facing string generated client-side (§1 of
    # COPY.md, "Your code: a7f3-92kd") — a separate, shorter, deliberately
    # unguessable-but-typeable identifier from the internal `session_id`
    # UUID the envelope carries. It never appears in the envelope schema
    # itself (§7.1 is fixed), so it travels on the connection instead.
    await websocket.accept()
    pool = await get_pg_pool()
    r = get_redis()
    await ensure_session(pool, session_id, code=code, active_season=await get_active_season(pool))
    try:
        while True:
            raw = await websocket.receive_json()
            batch = raw if isinstance(raw, list) else [raw]
            if len(batch) > MAX_BATCH_SIZE:
                batch = batch[:MAX_BATCH_SIZE]  # drop the overflow, never buffer unboundedly
            envelopes = _parse_batch(batch)
            if envelopes:
                await insert_events(pool, envelopes, r)
                await _capture_device_info(pool, envelopes)
                await _maybe_push_profile_update(websocket, pool, r, session_id)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("telemetry_ws crashed; closing connection without taking the app down")


@router.post("/api/events")
async def post_events(raw: list[dict], session_id: UUID = Query(...), code: str = Query(...)):
    """sendBeacon fallback target for unload (§7.2) and a plain HTTP path
    for clients that never got a WS connection up."""
    pool = await get_pg_pool()
    envelopes = _parse_batch(raw[:MAX_BATCH_SIZE])
    if envelopes:
        await ensure_session(pool, session_id, code=code, active_season=await get_active_season(pool))
        await insert_events(pool, envelopes, get_redis())
        await _capture_device_info(pool, envelopes)
    return {"accepted": len(envelopes)}


@router.get("/api/sessions/{session_id}/events")
async def get_events(session_id: UUID):
    """Backs the event-log viewer for the Gate 0 manual gate — the raw
    log, in order, so it can be checked by hand against what actually
    happened."""
    pool = await get_pg_pool()
    events = await get_session_events(pool, session_id)
    return {"session_id": str(session_id), "events": events}


@router.get("/api/sessions/{session_id}/views")
async def get_recomputed_views(session_id: UUID):
    """The *offline* recomputation of canonical item views + modes from
    the raw log (server/features/replay.py + item_view.py + mode.py) —
    shown alongside the raw log in the event-log viewer so the author can
    check the canonical boundaries by hand, and reused by the skew test
    to compare against the SDK's online computation."""
    pool = await get_pg_pool()
    events = await get_session_events(pool, session_id)
    store = get_store()
    near_substitute_set_by_item = {
        item["item_id"]: item["near_substitute_set_id"] for item in store.core_items if item["near_substitute_set_id"]
    }
    brand_tokens: set[str] = set()
    for item in store.all_items:
        brand_tokens.update(item["brand"].lower().replace("&", " ").split())
    views = recompute_session(events, near_substitute_set_by_item, brand_tokens)
    return {
        "session_id": str(session_id),
        "views": [
            {
                "item_id": v.item_id,
                "surface": v.surface,
                "start": v.start,
                "end": v.end,
                "duration_ms": v.duration_ms,
                "mode": v.mode,
                "closed_by": v.closed_by,
            }
            for v in views
        ],
    }


@router.get("/api/sessions/by-code/{code}")
async def lookup_sessions_by_code(code: str):
    """The visitor's code (`a7f3-92kd`) -> internal session_id(s), for the
    event-log viewer — the author has the code, not the UUID."""
    pool = await get_pg_pool()
    session_ids = await find_session_ids_by_code(pool, code)
    if not session_ids:
        raise HTTPException(status_code=404, detail="no data under that code")
    return {"session_ids": [str(sid) for sid in session_ids]}


@router.delete("/api/sessions/{code}")
async def delete_by_code(code: str):
    """Non-negotiable #5's delete endpoint, keyed on the visitor-facing
    code (not the internal session_id, which the visitor never sees)."""
    pool = await get_pg_pool()
    deleted = await delete_sessions_by_code(pool, code)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="no data under that code")
    return {"deleted_sessions": deleted}
