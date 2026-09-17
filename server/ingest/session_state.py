"""Live session state in Redis (§2: "Redis, live session state") —
ephemeral, fast, and separate from Postgres's durable append-only log.

Two things live here that Postgres would be the wrong tool for:

1. The §4.1a session-boundary check ("ends at 30 minutes with no
   events"). A Redis key with a rolling TTL matching that timeout makes
   "is this session still active" an O(1) key-existence check instead of
   a `MAX(ts_mono)` scan over Postgres on every event.
2. A live view counter, so "a session with fewer than 3 item views is
   excluded from normalization fitting" (§4.1a) is a cheap Redis
   `GET`/`INCR` instead of a `COUNT(*)` query, on the hot path of every
   view_start.
"""
from __future__ import annotations

from uuid import UUID

import redis.asyncio as redis

from server.config import settings

_SESSION_TTL_SECONDS = settings.session_idle_timeout_min * 60
_MIN_VIEWS_FOR_NORMALIZATION = 3


def _active_key(session_id: UUID) -> str:
    return f"prism:session:{session_id}:active"


def _view_count_key(session_id: UUID) -> str:
    return f"prism:session:{session_id}:view_count"


async def touch_session(r: redis.Redis, session_id: UUID) -> None:
    """Refresh the session's idle-timeout TTL — call on every event batch."""
    await r.set(_active_key(session_id), "1", ex=_SESSION_TTL_SECONDS)


async def is_session_active(r: redis.Redis, session_id: UUID) -> bool:
    return bool(await r.exists(_active_key(session_id)))


async def record_view(r: redis.Redis, session_id: UUID) -> int:
    """Increments and returns the session's live view count. The key
    shares the session's idle TTL so it naturally expires with it rather
    than needing separate cleanup."""
    count = await r.incr(_view_count_key(session_id))
    await r.expire(_view_count_key(session_id), _SESSION_TTL_SECONDS)
    return count


async def qualifies_for_normalization(r: redis.Redis, session_id: UUID) -> bool:
    count = await r.get(_view_count_key(session_id))
    return int(count or 0) >= _MIN_VIEWS_FOR_NORMALIZATION
