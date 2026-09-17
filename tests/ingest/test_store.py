"""Integration tests against the real docker-compose Postgres (see
docker-compose.yml / SETUP_WINDOWS.md). Skipped automatically if the DB
isn't reachable, so the rest of the suite stays runnable without it."""
import uuid

import pytest

from server.ingest.db import get_pg_pool
from server.ingest.envelope import Envelope
from server.ingest.store import delete_sessions_by_code, ensure_session, get_session_events, insert_events

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


async def test_payload_roundtrips_as_a_dict_not_a_json_string():
    pool = await _pool_or_skip()
    session_id = uuid.uuid4()
    code = f"test-{uuid.uuid4().hex[:8]}"
    await ensure_session(pool, session_id, code)
    await insert_events(pool, [_envelope(session_id, payload={"nested": {"a": 1}})])

    events = await get_session_events(pool, session_id)
    assert events[0]["payload"] == {"nested": {"a": 1}}

    await delete_sessions_by_code(pool, code)
