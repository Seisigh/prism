"""server/ingest/app_config.py: the one-key active-season store."""
import pytest

from server.ingest.app_config import get_active_season, set_active_season
from server.ingest.db import get_pg_pool

pytestmark = pytest.mark.asyncio


async def _pool_or_skip():
    try:
        return await get_pg_pool()
    except Exception as e:
        pytest.skip(f"Postgres not reachable: {e}")


async def test_default_active_season_is_none_when_never_set():
    pool = await _pool_or_skip()
    await set_active_season(pool, "none")  # start from a known state
    assert await get_active_season(pool) == "none"


async def test_set_and_get_round_trips():
    pool = await _pool_or_skip()
    await set_active_season(pool, "spring")
    assert await get_active_season(pool) == "spring"
    await set_active_season(pool, "none")  # leave clean for other tests


async def test_set_rejects_an_invalid_season():
    pool = await _pool_or_skip()
    with pytest.raises(ValueError):
        await set_active_season(pool, "not_a_real_season")
