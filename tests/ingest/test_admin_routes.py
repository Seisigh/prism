"""server/ingest/admin_routes.py: the admin console API, end to end
through the real FastAPI app -- auth is the load-bearing thing to prove
actually works, not just the pure functions it's built from."""
import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from server.config import settings
from server.ingest.admin_auth import COOKIE_NAME
from server.main import app

pytestmark = pytest.mark.asyncio


async def _pg_or_skip():
    import asyncpg

    try:
        conn = await asyncpg.connect(dsn=settings.database_url)
        await conn.close()
    except Exception:
        pytest.skip("Postgres not reachable")


async def _redis_or_skip():
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.ping()
    except Exception:
        pytest.skip("Redis not reachable")


@pytest.fixture(autouse=True)
def _set_admin_password(monkeypatch):
    # Set explicitly rather than relying on .env having real values —
    # this suite must prove auth works from its own fixtures, not from
    # whatever happens to be in the environment it runs in.
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    monkeypatch.setattr(settings, "admin_session_secret", "test-session-secret")


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def test_admin_responses_are_never_cached():
    """Real bug found live: a stale browser-cached response for
    /api/admin/signal-registry kept overriding live data on a later
    fetch(), even though curl and a fresh navigation both got the
    current response. Every /api/admin/* response must say so."""
    async with await _client() as client:
        resp = await client.get("/api/admin/whoami")
        assert resp.headers.get("cache-control") == "no-store"


async def test_non_admin_responses_are_not_forced_no_store():
    async with await _client() as client:
        resp = await client.get("/api/season")
        assert resp.headers.get("cache-control") != "no-store"


async def test_whoami_unauthenticated():
    async with await _client() as client:
        resp = await client.get("/api/admin/whoami")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": False}


async def test_login_rejects_wrong_password():
    async with await _client() as client:
        resp = await client.post("/api/admin/login", json={"password": "wrong"})
        assert resp.status_code == 401


async def test_login_accepts_correct_password_and_sets_a_cookie():
    async with await _client() as client:
        resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        assert resp.status_code == 200
        assert COOKIE_NAME in resp.cookies


async def test_login_cookie_is_not_secure_outside_production():
    """Real bug, found live: an unconditionally Secure cookie is
    silently dropped by the browser over plain http://, which is exactly
    how local dev serves this app -- login would 200 and then behave as
    if it never happened."""
    async with await _client() as client:
        resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        set_cookie_header = resp.headers.get("set-cookie", "")
        assert "Secure" not in set_cookie_header


async def test_login_cookie_is_secure_in_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    async with await _client() as client:
        resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        set_cookie_header = resp.headers.get("set-cookie", "")
        assert "Secure" in set_cookie_header


async def test_sessions_list_requires_authentication():
    async with await _client() as client:
        resp = await client.get("/api/admin/sessions")
        assert resp.status_code == 401


async def test_sessions_list_succeeds_once_logged_in():
    await _pg_or_skip()
    await _redis_or_skip()
    async with await _client() as client:
        login_resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        client.cookies.set(COOKIE_NAME, login_resp.cookies[COOKIE_NAME])
        resp = await client.get("/api/admin/sessions")
        assert resp.status_code == 200
        assert "sessions" in resp.json()


async def test_new_profile_requires_authentication():
    async with await _client() as client:
        resp = await client.post("/api/admin/new-profile")
        assert resp.status_code == 401


# Every /api/admin/* route except /login and /whoami (which deliberately
# answers {"authenticated": false} rather than throwing) must reject an
# unauthenticated request with 401 — checked directly against each route,
# not inferred from a couple of examples, since this is the exact failure
# mode ("hidden on the client, open on the server") auth exists to close.
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/sessions"),
        ("GET", "/api/admin/sessions/00000000-0000-0000-0000-000000000000/signals"),
        ("GET", "/api/admin/signal-distributions"),
        ("GET", "/api/admin/signal-registry"),
        ("GET", "/api/admin/season"),
        ("POST", "/api/admin/new-profile"),
    ],
)
async def test_every_admin_endpoint_requires_authentication(method, path):
    async with await _client() as client:
        resp = await client.request(method, path)
        assert resp.status_code == 401


async def test_signal_registry_matches_the_real_signal_set_once_authenticated():
    from server.features.signals import SIGNAL_REGISTRY
    from server.features.signals_directional import DIRECTIONAL_SIGNAL_REGISTRY
    from server.features.signals_gate1 import GATE1_SIGNAL_REGISTRY

    all_signals = {**SIGNAL_REGISTRY, **GATE1_SIGNAL_REGISTRY, **DIRECTIONAL_SIGNAL_REGISTRY}
    async with await _client() as client:
        login_resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        client.cookies.set(COOKIE_NAME, login_resp.cookies[COOKIE_NAME])
        resp = await client.get("/api/admin/signal-registry")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == set(all_signals.keys())
        for entry in body.values():
            assert set(entry.keys()) == {"measures", "higher", "lower", "unavailable_when"}


async def test_set_season_requires_authentication():
    async with await _client() as client:
        resp = await client.post("/api/admin/season", json={"season": "summer"})
        assert resp.status_code == 401


async def test_season_get_set_round_trip_once_authenticated():
    await _pg_or_skip()
    async with await _client() as client:
        login_resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        client.cookies.set(COOKIE_NAME, login_resp.cookies[COOKIE_NAME])

        resp = await client.post("/api/admin/season", json={"season": "holiday"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "season": "holiday"}

        resp = await client.get("/api/admin/season")
        assert resp.status_code == 200
        body = resp.json()
        assert body["season"] == "holiday"
        assert set(body["valid_seasons"]) == {"spring", "summer", "fall", "winter", "holiday", "none"}

        # Restore the default so this test doesn't leak state into others.
        await client.post("/api/admin/season", json={"season": "none"})


async def test_set_season_rejects_an_invalid_value_once_authenticated():
    async with await _client() as client:
        login_resp = await client.post("/api/admin/login", json={"password": "test-password-123"})
        client.cookies.set(COOKIE_NAME, login_resp.cookies[COOKIE_NAME])
        resp = await client.post("/api/admin/season", json={"season": "not_a_real_season"})
        assert resp.status_code == 400


async def test_public_season_endpoint_needs_no_authentication():
    # /api/season lives on the storefront app (server/main.py) -- covered
    # directly against the real app instance rather than the admin-only
    # _client() helper, since this one must work with zero cookies.
    await _pg_or_skip()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        resp = await client.get("/api/season")
        assert resp.status_code == 200
        assert resp.json()["season"] in {"spring", "summer", "fall", "winter", "holiday", "none"}


def test_live_view_websocket_rejects_without_a_session_cookie():
    with pytest.raises(Exception) as exc_info:
        with TestClient(app).websocket_connect(
            "/api/admin/live/00000000-0000-0000-0000-000000000000"
        ):
            pass
    # Starlette raises WebSocketDisconnect with the close code the server
    # sent (4401) when the handshake's own code closes it before accept().
    assert getattr(exc_info.value, "code", None) == 4401


def test_live_view_websocket_rejects_a_cookie_signed_with_no_secret_configured(monkeypatch):
    # Same forged-cookie shape a real attacker would try against a
    # deployment that forgot to set ADMIN_SESSION_SECRET.
    monkeypatch.setattr(settings, "admin_session_secret", None)
    with pytest.raises(Exception) as exc_info:
        with TestClient(app).websocket_connect(
            "/api/admin/live/00000000-0000-0000-0000-000000000000",
            cookies={COOKIE_NAME: "1234567890."},
        ):
            pass
    assert getattr(exc_info.value, "code", None) == 4401
