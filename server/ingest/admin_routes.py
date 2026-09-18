"""Admin console API (BUILD_BRIEF.md §6.7). Every route except `/login`
depends on `require_admin_session` -- there is no environment where these
are reachable without a valid signed session cookie, including local
(§6.7: "behind authentication in every environment including local").
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect

from server.config import settings
from server.ingest import admin_signals, admin_store
from server.ingest.admin_auth import COOKIE_NAME, check_password, create_session_cookie_value, require_admin_session, verify_session_cookie
from server.ingest.db import get_pg_pool, get_redis
from server.ingest.live_scoring import _load_taste_state
from server.ingest.store import get_session_events
from sim.embedding import DIMENSIONS

logger = logging.getLogger("prism.admin")
router = APIRouter(prefix="/api/admin")

LIVE_POLL_INTERVAL_SECONDS = 1.0


@router.post("/login")
async def login(body: dict, response: Response):
    password = body.get("password", "")
    if not check_password(password):
        raise HTTPException(status_code=401, detail="incorrect password")
    response.set_cookie(
        COOKIE_NAME,
        create_session_cookie_value(),
        httponly=True,
        samesite="strict",
        # Real bug, found live: an unconditional `secure=True` cookie is
        # silently dropped by the browser over plain http://, which is
        # exactly how local dev serves this app -- login would appear to
        # succeed (200 OK) and then immediately behave as if it hadn't.
        # `settings.app_env` is "production" only behind the real
        # deployed https:// origin (fly.toml sets it), so this stays
        # Secure everywhere it matters and never silently breaks locally.
        secure=settings.app_env == "production",
        max_age=60 * 60 * 12,
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/whoami")
async def whoami(prism_admin_session: str | None = Cookie(default=None)):
    # Deliberately does NOT depend on require_admin_session -- the
    # frontend calls this to decide whether to show the login form or
    # the console, and a 401-throwing dependency would make that check
    # itself throw instead of returning a plain answer.
    return {"authenticated": verify_session_cookie(prism_admin_session)}


@router.get("/sessions", dependencies=[Depends(require_admin_session)])
async def sessions_list(real_only: bool = False, demo_only: bool = False, has_commitment: bool | None = None, since_days: int | None = None):
    pool = await get_pg_pool()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=since_days) if since_days else None
    rows = await admin_store.list_sessions(pool, real_only=real_only, demo_only=demo_only, has_commitment=has_commitment, since=since)
    return {"sessions": _jsonable(rows)}


@router.get("/sessions/{session_id}/signals", dependencies=[Depends(require_admin_session)])
async def session_signals(session_id: UUID):
    pool = await get_pg_pool()
    rows = await admin_signals.get_session_signal_table(pool, session_id)
    return {"session_id": str(session_id), "rows": rows}


@router.get("/signal-distributions", dependencies=[Depends(require_admin_session)])
async def signal_distributions(limit_sessions: int = 50):
    pool = await get_pg_pool()
    sessions = await admin_store.list_sessions(pool)
    session_ids = [s["session_id"] for s in sessions[:limit_sessions]]
    distributions = await admin_signals.get_signal_distributions(pool, session_ids)
    return {"n_sessions": len(session_ids), "distributions": distributions}


@router.post("/new-profile", dependencies=[Depends(require_admin_session)])
async def new_profile():
    # §6.7 "New profile": issuing a fresh session_id and clearing local
    # state is a client-side action (a new session_id is generated the
    # same way any first-time visitor gets one) -- this endpoint exists
    # so the action is logged server-side and auth-gated, not because
    # the server needs to allocate anything.
    return {"ok": True}


def _jsonable(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        d = dict(row)
        for key, value in d.items():
            if isinstance(value, UUID):
                d[key] = str(value)
            elif isinstance(value, dt.datetime):
                d[key] = value.isoformat()
        out.append(d)
    return out


@router.websocket("/live/{session_id}")
async def live_view(websocket: WebSocket, session_id: UUID):
    if not verify_session_cookie(websocket.cookies.get(COOKIE_NAME)):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    pool = await get_pg_pool()
    r = get_redis()
    last_seq = -1
    try:
        while True:
            events = await get_session_events(pool, session_id)
            new_events = [e for e in events if e["seq"] > last_seq]
            if new_events:
                last_seq = max(e["seq"] for e in new_events)
                vector, scored_view_count = await _load_taste_state(r, session_id)
                await websocket.send_json(
                    {
                        "type": "live_update",
                        "new_events": _jsonable(new_events),
                        "taste_vector": list(vector),
                        "dimensions": list(DIMENSIONS),
                        "scored_view_count": scored_view_count,
                    }
                )
            await asyncio.sleep(LIVE_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("admin live view crashed for session %s", session_id)
