"""Read-only aggregate queries backing the admin console (§6.7).
Aggregation happens in Python over rows already indexed by
`(session_id, ts_mono)`/`type` — a few thousand events per session at
most, so this is genuinely simpler and just as fast as hand-rolled SQL
aggregates at this scale (§6.7's own "explicitly not building" scaling
posture: no materialized views, no rollup tables).

Privacy (§6.7): every function here reads only pseudonymous
`session_id`/`code` plus behavioral data already collected — never an
IP, never anything that could identify a person, because none of that
exists in the schema to begin with.
"""
from __future__ import annotations

import datetime as dt
from uuid import UUID

import asyncpg

_VIEW_EVENT_TYPES = {"view_start", "detail_view_start"}
_COMMITMENT_TYPES = {"cart_add", "wishlist", "checkout_start"}


async def list_sessions(
    pool: asyncpg.Pool,
    real_only: bool = False,
    demo_only: bool = False,
    has_commitment: bool | None = None,
    since: dt.datetime | None = None,
) -> list[dict]:
    rows = await pool.fetch(
        """
        SELECT s.session_id, s.code, s.created_at, s.last_event_at, s.demo_opened,
               s.browser, s.engine_version, s.device_pixel_ratio, s.viewport_width,
               s.viewport_height, s.pointer_type, s.active_season,
               COUNT(*) FILTER (WHERE e.type = ANY($1::text[])) AS item_views,
               COUNT(*) FILTER (WHERE e.type = ANY($2::text[])) AS commitments,
               MIN(e.ts_mono) AS first_ts,
               MAX(e.ts_mono) AS last_ts
        FROM sessions s
        LEFT JOIN events e ON e.session_id = s.session_id
        WHERE ($3::timestamptz IS NULL OR s.created_at >= $3)
        GROUP BY s.session_id
        ORDER BY s.created_at DESC
        """,
        list(_VIEW_EVENT_TYPES),
        list(_COMMITMENT_TYPES),
        since,
    )

    mode_rows = await pool.fetch(
        """
        SELECT session_id, mode, COUNT(*) AS n
        FROM events
        WHERE type = ANY($1::text[]) AND mode IS NOT NULL
        GROUP BY session_id, mode
        """,
        list(_VIEW_EVENT_TYPES),
    )
    modes_by_session: dict[UUID, dict[str, int]] = {}
    for r in mode_rows:
        modes_by_session.setdefault(r["session_id"], {})[r["mode"]] = r["n"]

    out = []
    for r in rows:
        d = dict(r)
        duration_ms = (d["last_ts"] - d["first_ts"]) if d["first_ts"] is not None and d["last_ts"] is not None else None
        d["duration_ms"] = duration_ms
        d["mode_distribution"] = modes_by_session.get(d["session_id"], {})
        del d["first_ts"], d["last_ts"]
        out.append(d)

    if real_only:
        out = [d for d in out if not d["demo_opened"]]
    if demo_only:
        out = [d for d in out if d["demo_opened"]]
    if has_commitment is not None:
        out = [d for d in out if (d["commitments"] > 0) == has_commitment]
    return out


async def get_session_meta(pool: asyncpg.Pool, session_id: UUID) -> dict | None:
    row = await pool.fetchrow("SELECT * FROM sessions WHERE session_id = $1", session_id)
    return dict(row) if row else None
