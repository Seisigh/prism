"""server/ingest/admin_auth.py: password check + signed session cookie."""
import time

from server.ingest import admin_auth


def test_check_password_rejects_when_none_configured(monkeypatch):
    monkeypatch.setattr(admin_auth.settings, "admin_password", None)
    assert admin_auth.check_password("anything") is False


def test_check_password_accepts_the_configured_password(monkeypatch):
    monkeypatch.setattr(admin_auth.settings, "admin_password", "correct-horse")
    assert admin_auth.check_password("correct-horse") is True
    assert admin_auth.check_password("wrong") is False


def test_session_cookie_round_trips():
    value = admin_auth.create_session_cookie_value()
    assert admin_auth.verify_session_cookie(value) is True


def test_session_cookie_rejects_tampered_signature():
    value = admin_auth.create_session_cookie_value()
    issued_at, _sig = value.split(".", 1)
    tampered = f"{issued_at}.0000000000000000000000000000000000000000000000000000000000000000"
    assert admin_auth.verify_session_cookie(tampered) is False


def test_session_cookie_rejects_expired(monkeypatch):
    value = admin_auth.create_session_cookie_value()
    future = time.time() + admin_auth.SESSION_TTL_SECONDS + 1
    monkeypatch.setattr(admin_auth.time, "time", lambda: future)
    assert admin_auth.verify_session_cookie(value) is False


def test_session_cookie_rejects_missing_or_malformed():
    assert admin_auth.verify_session_cookie(None) is False
    assert admin_auth.verify_session_cookie("") is False
    assert admin_auth.verify_session_cookie("no-dot-here") is False


def test_check_password_rejects_when_secret_not_configured(monkeypatch):
    """A missing signing secret must fail closed exactly like a missing
    password — not fall back to a value baked into this public repo."""
    monkeypatch.setattr(admin_auth.settings, "admin_password", "correct-horse")
    monkeypatch.setattr(admin_auth.settings, "admin_session_secret", None)
    assert admin_auth.check_password("correct-horse") is False


def test_verify_session_cookie_rejects_when_secret_not_configured(monkeypatch):
    # A cookie signed while a secret WAS configured must stop verifying
    # the moment the secret is unset — never trust a stale signature.
    value = admin_auth.create_session_cookie_value()
    monkeypatch.setattr(admin_auth.settings, "admin_session_secret", None)
    assert admin_auth.verify_session_cookie(value) is False


def test_verify_session_cookie_never_trivially_matches_an_empty_signature(monkeypatch):
    """Regression: _sign() must never be able to return an empty string
    that a hand-crafted "<timestamp>." cookie could trivially match."""
    monkeypatch.setattr(admin_auth.settings, "admin_session_secret", None)
    issued_at = str(int(time.time()))
    assert admin_auth.verify_session_cookie(f"{issued_at}.") is False
