"""Integration tests against the real docker-compose Postgres (see
docker-compose.yml / SETUP_WINDOWS.md). Skipped automatically if the DB
isn't reachable, so the rest of the suite stays runnable without it."""
import uuid

import pytest

from server.ingest.db import get_pg_pool
from server.ingest.envelope import Envelope
from server.ingest.store import delete_sessions_by_code, ensure_session, get_session_events, insert_events, update_session_device

pytestmark = pytest.mark.asyncio


async def _pool_or_skip():
    try:
        return await get_pg_pool()
    except Exception as e:
        pytest.skip(f"Postgres not reachable: {e}")


def _envelope(session_id, event_id=None, seq=1, item_id="i1", type_="page_view", payload=None) -> Envelope:
    return Envelope(
        event_id=event_id or uuid.uuid4(),
        session_id=session_id,
        seq=seq,
        ts_mono=float(seq * 100),
        ts_wall=1_700_000_000_000.0,
        demo=False,
        surface="home",
        mode=None,
        type=type_,
        payload=payload or {"item_id": item_id},
    )


async def test_insert_is_idempotent_on_event_id():
    pool = await _pool_or_skip()
    session_id = uuid.uuid4()
    code = f"test-{uuid.uuid4().hex[:8]}"
    await ensure_session(pool, session_id, code)

    envelope = _envelope(session_id)
    await insert_events(pool, [envelope])
    await insert_events(pool, [envelope])  # retransmit, same event_id

    events = await get_session_events(pool, session_id)
    assert len(events) == 1

    await delete_sessions_by_code(pool, code)


async def test_delete_by_code_removes_all_events():
    pool = await _pool_or_skip()
    session_id = uuid.uuid4()
    code = f"test-{uuid.uuid4().hex[:8]}"
    await ensure_session(pool, session_id, code)
    await insert_events(pool, [_envelope(session_id, seq=1), _envelope(session_id, seq=2)])

    assert len(await get_session_events(pool, session_id)) == 2

    deleted = await delete_sessions_by_code(pool, code)
    assert deleted == 1
    assert await get_session_events(pool, session_id) == []


async def test_update_session_device_populates_previously_null_columns():
    """Real bug found while building the admin console's sessions list
    (§6.7): device info arrives in the first page_view event's payload,
    after ensure_session already created the row with no device info at
    all -- nothing called an UPDATE, so browser/pointer_type/etc. were
    always NULL for every real session."""
    pool = await _pool_or_skip()
    session_id = uuid.uuid4()
    code = f"test-{uuid.uuid4().hex[:8]}"
    await ensure_session(pool, session_id, code)

    await update_session_device(
        pool,
        session_id,
        {"browser": "Chrome", "engine_version": "120.0", "device_pixel_ratio": 2.0, "viewport_width": 1440, "viewport_height": 900, "pointer_type": "mouse"},
    )

    row = await pool.fetchrow("SELECT browser, pointer_type, viewport_width FROM sessions WHERE session_id = $1", session_id)
    assert row["browser"] == "Chrome"
    assert row["pointer_type"] == "mouse"
    assert row["viewport_width"] == 1440

    await delete_sessions_by_code(pool, code)


async def test_update_session_device_does_not_overwrite_with_none():
    pool = await _pool_or_skip()
    session_id = uuid.uuid4()
    code = f"test-{uuid.uuid4().hex[:8]}"
    await ensure_session(pool, session_id, code)
    await update_session_device(pool, session_id, {"browser": "Chrome"})
    await update_session_device(pool, session_id, {})  # a second, device-less call must not clear it

    row = await pool.fetchrow("SELECT browser FROM sessions WHERE session_id = $1", session_id)
    assert row["browser"] == "Chrome"

    await delete_sessions_by_code(pool, code)


async def test_payload_roundtrips_as_a_dict_not_a_json_string():
    pool = await _pool_or_skip()
    session_id = uuid.uuid4()
    code = f"test-{uuid.uuid4().hex[:8]}"
    await ensure_session(pool, session_id, code)
    await insert_events(pool, [_envelope(session_id, payload={"nested": {"a": 1}})])

    events = await get_session_events(pool, session_id)
    assert events[0]["payload"] == {"nested": {"a": 1}}

    await delete_sessions_by_code(pool, code)
