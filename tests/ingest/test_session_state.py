import uuid

import pytest
import redis.asyncio as redis

from server.config import settings
from server.ingest.session_state import is_session_active, qualifies_for_normalization, record_view, touch_session

pytestmark = pytest.mark.asyncio


async def _redis_or_skip() -> redis.Redis:
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.ping()
    except Exception as e:
        pytest.skip(f"Redis not reachable: {e}")
    return r


async def test_touch_session_makes_it_active():
    r = await _redis_or_skip()
    session_id = uuid.uuid4()
    assert await is_session_active(r, session_id) is False
    await touch_session(r, session_id)
    assert await is_session_active(r, session_id) is True
    await r.delete(f"prism:session:{session_id}:active")
    await r.aclose()


async def test_view_count_below_threshold_does_not_qualify():
    r = await _redis_or_skip()
    session_id = uuid.uuid4()
    await record_view(r, session_id)
    await record_view(r, session_id)
    assert await qualifies_for_normalization(r, session_id) is False
    await r.delete(f"prism:session:{session_id}:view_count")
    await r.aclose()


async def test_view_count_at_threshold_qualifies():
    r = await _redis_or_skip()
    session_id = uuid.uuid4()
    for _ in range(3):
        await record_view(r, session_id)
    assert await qualifies_for_normalization(r, session_id) is True
    await r.delete(f"prism:session:{session_id}:view_count")
    await r.aclose()


async def test_unknown_session_does_not_qualify():
    r = await _redis_or_skip()
    assert await qualifies_for_normalization(r, uuid.uuid4()) is False
    await r.aclose()
