"""The `app_config` single-row-per-key store (close-out item 4). Today
this holds exactly one key, the globally-active merchandising season --
changeable from the admin console, read by the public storefront to pick
seasonal rail items and badges. Deliberately not a settings framework:
one key, one get, one set.
"""
from __future__ import annotations

import asyncpg

ACTIVE_SEASON_KEY = "active_season"
DEFAULT_SEASON = "none"
VALID_SEASONS = ("spring", "summer", "fall", "winter", "holiday", "none")


async def get_active_season(pool: asyncpg.Pool) -> str:
    value = await pool.fetchval("SELECT value FROM app_config WHERE key = $1", ACTIVE_SEASON_KEY)
    return value if value in VALID_SEASONS else DEFAULT_SEASON


async def set_active_season(pool: asyncpg.Pool, season: str) -> None:
    if season not in VALID_SEASONS:
        raise ValueError(f"not a valid season: {season!r}")
    await pool.execute(
        """
        INSERT INTO app_config (key, value) VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        ACTIVE_SEASON_KEY,
        season,
    )
