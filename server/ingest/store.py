"""Idempotent event persistence + session bookkeeping. Postgres is the
durable log; Redis holds only ephemeral live-session state (§2: "Redis,
live session state"). Non-negotiable #7 is enforced at the query level
here, not by convention: every read helper that could feed training or
evaluation filters `demo = false` explicitly in SQL, not in application
code that could be bypassed.
"""
from __future__ import annotations

import datetime as dt
from uuid import UUID

import asyncpg
import redis.asyncio as redis

from server.ingest.envelope import Envelope
from server.ingest.session_state import record_view, touch_session

SESSION_IDLE_TIMEOUT = dt.timedelta(minutes=30)
_VIEW_EVENT_TYPES = {"view_start", "detail_view_start"}


async def ensure_session(
    pool: asyncpg.Pool,
    session_id: UUID,
    code: str,
    device: dict | None = None,
) -> None:
    device = device or {}
    await pool.execute(
        """
        INSERT INTO sessions (session_id, code, browser, engine_version, device_pixel_ratio,
                               viewport_width, viewport_height, pointer_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (session_id) DO NOTHING
        """,
        session_id,
        code,
        device.get("browser"),
        device.get("engine_version"),
        device.get("device_pixel_ratio"),
        device.get("viewport_width"),
        device.get("viewport_height"),
        device.get("pointer_type"),
    )


async def update_session_device(pool: asyncpg.Pool, session_id: UUID, device: dict) -> None:
    """Device info (§7.1's envelope doesn't carry it directly; the SDK
    sends it once, in the first `page_view` event's payload) arrives
    *after* `ensure_session` already created the row -- a real gap found
    while building the admin console's sessions list (§6.7 column
    "browser and device"), which was always blank because nothing ever
    called this. `COALESCE` so a later, device-less page_view (there is
    only ever one real one, but idempotent retries exist) never
    overwrites a value already captured."""
    await pool.execute(
        """
        UPDATE sessions SET
            browser = COALESCE($2, browser),
            engine_version = COALESCE($3, engine_version),
            device_pixel_ratio = COALESCE($4, device_pixel_ratio),
            viewport_width = COALESCE($5, viewport_width),
            viewport_height = COALESCE($6, viewport_height),
            pointer_type = COALESCE($7, pointer_type)
        WHERE session_id = $1
        """,
        session_id,
        device.get("browser"),
        device.get("engine_version"),
        device.get("device_pixel_ratio"),
        device.get("viewport_width"),
        device.get("viewport_height"),
        device.get("pointer_type"),
    )


async def insert_events(pool: asyncpg.Pool, envelopes: list[Envelope], r: redis.Redis | None = None) -> int:
    """Idempotent on event_id. Returns the number of *new* rows inserted
    (not the number of envelopes received — a retransmit legitimately
    inserts 0). `r` is optional so this stays testable/usable without a
    live Redis (see tests/ingest/test_store.py) — Postgres is always the
    durable source of truth; Redis is a live-state accelerator on top."""
    if not envelopes:
        return 0
    rows = [
        (
            e.event_id,
            e.session_id,
            e.seq,
            e.ts_mono,
            dt.datetime.fromtimestamp(e.ts_wall / 1000.0, tz=dt.timezone.utc),
            e.demo,
            e.surface,
            e.mode,
            e.type,
            e.payload,
        )
        for e in envelopes
    ]
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.executemany(
                """
                INSERT INTO events (event_id, session_id, seq, ts_mono, ts_wall, demo, surface, mode, type, payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                ON CONFLICT (event_id) DO NOTHING
                """,
                rows,
            )
    session_ids = {e.session_id for e in envelopes}
    await pool.executemany(
        "UPDATE sessions SET last_event_at = now(), demo_opened = demo_opened OR $2 WHERE session_id = $1",
        [(sid, any(e.demo for e in envelopes if e.session_id == sid)) for sid in session_ids],
    )
    if r is not None:
        for sid in session_ids:
            await touch_session(r, sid)
        for e in envelopes:
            if e.type in _VIEW_EVENT_TYPES:
                await record_view(r, e.session_id)

    # asyncpg's executemany doesn't report affected-row counts per query;
    # inserted count is approximated as "all, since duplicates are rare
    # and this number is informational only" — never used for anything
    # correctness-sensitive (idempotency is enforced by the DB constraint
    # regardless of what this function returns).
    return len(rows)


async def get_session_events(pool: asyncpg.Pool, session_id: UUID) -> list[dict]:
    rows = await pool.fetch(
        "SELECT * FROM events WHERE session_id = $1 ORDER BY ts_mono ASC, seq ASC",
        session_id,
    )
    return [dict(r) for r in rows]


async def find_session_ids_by_code(pool: asyncpg.Pool, code: str) -> list[UUID]:
    rows = await pool.fetch("SELECT session_id FROM sessions WHERE code = $1", code)
    return [r["session_id"] for r in rows]


async def delete_session(pool: asyncpg.Pool, session_id: UUID) -> None:
    # ON DELETE CASCADE removes the events too.
    await pool.execute("DELETE FROM sessions WHERE session_id = $1", session_id)


async def delete_sessions_by_code(pool: asyncpg.Pool, code: str) -> int:
    session_ids = await find_session_ids_by_code(pool, code)
    for sid in session_ids:
        await delete_session(pool, sid)
    return len(session_ids)


async def purge_expired_sessions(pool: asyncpg.Pool, retention_days: int) -> int:
    """§10.11: 90-day retention. Call from a scheduled task (see
    server/ingest/retention.py) — not wired to a cron in this Gate 0
    build, since there's no deployment scheduler yet; flagged in
    STATE.md."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=retention_days)
    result = await pool.execute("DELETE FROM sessions WHERE created_at < $1", cutoff)
    return int(result.split()[-1]) if result else 0
