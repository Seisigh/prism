"""server/ingest/live_scoring.py: the orchestration from a session's real
event log to a pushed profile-update payload. Ranker scoring itself is
stubbed (already covered by tests/models/test_ranker_store.py) so this
test is scoped to the orchestration logic: view recomputation, the
not-yet-scored cutoff, taste-vector folding, and the population-prior
gate below 3 scored views.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
import redis.asyncio as redis

from server.config import settings
from server.ingest import live_scoring

pytestmark = pytest.mark.asyncio


async def _redis_or_skip() -> redis.Redis:
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.ping()
    except Exception:
        pytest.skip("Redis not reachable")
    return r


_seq_counter = [0]


def _event(t, type_, surface="detail", payload=None):
    _seq_counter[0] += 1
    return {"ts_mono": t, "seq": _seq_counter[0], "type": type_, "surface": surface, "payload": payload or {}}


def _session_events(item_id: str, view_start: float, view_end: float) -> list[dict]:
    return [
        _event(0.0, "page_view", surface="detail"),
        _event(view_start, "view_start", payload={"item_id": item_id}),
        _event((view_start + view_end) / 2, "pointer_sample", payload={"item_id": item_id, "x": 10, "y": 10}),
        _event(view_end, "view_end", payload={"item_id": item_id}),
    ]


@pytest.fixture(autouse=True)
def _stub_catalog_and_embeddings(monkeypatch):
    fake_store = SimpleNamespace(
        core_items=[],
        all_items=[{"item_id": "i1", "brand": "Acme Co."}],
        by_id={"i1": {"category": "Test Category"}},
    )
    monkeypatch.setattr(live_scoring, "get_store", lambda: fake_store)
    fake_vectors = {"i1": SimpleNamespace(vector=(0.1, 0.2, 0.3, 0.0, 0.5, 0.1, 0.0), category="Test Category", near_substitute_set_id=None)}
    monkeypatch.setattr(live_scoring, "_item_vectors", lambda: fake_vectors)
    monkeypatch.setattr(live_scoring, "_catalog_centroid", lambda: (0.1, 0.2, 0.3, 0.0, 0.5, 0.1, 0.0))
    monkeypatch.setattr(live_scoring.ranker_store, "is_trained", lambda: True)
    monkeypatch.setattr(live_scoring.ranker_store, "score", lambda mode, signals: (0.5, 0.9))


async def test_score_session_update_returns_none_with_no_closed_views():
    r = await _redis_or_skip()
    session_id = uuid4()
    events = [_event(0.0, "page_view"), _event(100.0, "view_start", payload={"item_id": "i1"})]  # never closes
    result = await live_scoring.score_session_update(r, session_id, events)
    assert result is None


async def test_score_session_update_returns_a_payload_for_one_closed_view():
    r = await _redis_or_skip()
    session_id = uuid4()
    events = _session_events("i1", 1000.0, 3000.0)
    result = await live_scoring.score_session_update(r, session_id, events)
    assert result is not None
    assert result["type"] == "profile_update"
    assert result["scored_view_count"] == 1
    assert result["last_item_id"] == "i1"
    assert result["last_p_i"] == 0.9


async def test_score_session_update_below_three_scored_views_serves_the_population_prior():
    r = await _redis_or_skip()
    session_id = uuid4()
    events = _session_events("i1", 1000.0, 3000.0)
    result = await live_scoring.score_session_update(r, session_id, events)
    assert result["scored_view_count"] == 1
    assert tuple(result["vector"]) == live_scoring.normalize(live_scoring._catalog_centroid())


async def test_score_session_update_ignores_a_view_already_scored():
    r = await _redis_or_skip()
    session_id = uuid4()
    events = _session_events("i1", 1000.0, 3000.0)
    first = await live_scoring.score_session_update(r, session_id, events)
    assert first is not None
    second = await live_scoring.score_session_update(r, session_id, events)
    assert second is None
