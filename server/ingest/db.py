"""Postgres connection pool + Redis client, both lazily created and
cached per-process. No ORM — asyncpg with hand-written SQL (§2: "No ORM
heroics")."""
from __future__ import annotations

import json
from pathlib import Path

import asyncpg
import redis.asyncio as redis

from server.config import settings

_pg_pool: asyncpg.Pool | None = None
_redis: redis.Redis | None = None
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Lets store.py pass/receive plain Python dicts for jsonb columns
    # instead of asyncpg's default (a raw string it won't auto-serialize).
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=10, init=_init_connection
        )
        async with _pg_pool.acquire() as conn:
            await conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _pg_pool


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_connections() -> None:
    global _pg_pool, _redis
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    if _redis is not None:
        await _redis.aclose()
        _redis = None
