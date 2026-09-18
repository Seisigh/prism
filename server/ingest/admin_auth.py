"""Admin console authentication (BUILD_BRIEF.md §6.7): "behind
authentication in every environment including local: a single password
read from the environment, a signed session cookie, no user accounts."
There is no "skip auth in dev" branch anywhere in this module — that is
the point of "including local."

The signature is a plain HMAC-SHA256 over an issue timestamp, verified
with a constant-time comparison and a fixed TTL. No session store, no
user table, matching §6.7's own "explicitly not building" scaling
posture: one password, one cookie format, nothing to persist.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import Cookie, HTTPException

from server.config import settings

COOKIE_NAME = "prism_admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 12  # 12 hours


def _sign(value: str) -> str:
    secret = settings.admin_session_secret
    if not secret:
        # No signing key configured. Never fall back to a fixed value —
        # this repo is public, so a fallback baked into source would let
        # anyone forge a session without the password. Callers must check
        # settings.admin_session_secret before relying on this.
        raise RuntimeError("admin_session_secret is not configured")
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_cookie_value() -> str:
    issued_at = str(int(time.time()))
    return f"{issued_at}.{_sign(issued_at)}"


def verify_session_cookie(value: str | None) -> bool:
    if not settings.admin_session_secret:
        # Fails closed exactly like a missing password below, rather
        # than signing/verifying against a default that would ship
        # readable inside this repo.
        return False
    if not value or "." not in value:
        return False
    issued_at, signature = value.split(".", 1)
    if not hmac.compare_digest(_sign(issued_at), signature):
        return False
    try:
        issued_at_int = int(issued_at)
    except ValueError:
        return False
    return (time.time() - issued_at_int) < SESSION_TTL_SECONDS


def check_password(password: str) -> bool:
    """Fails closed when no password (`settings.admin_password`) or no
    session-signing secret (`settings.admin_session_secret`) is
    configured — an operator who forgot to set either gets a console
    nobody can log into, never one anybody can, per config.py's own
    docstring. Checked together here so `login()` never reaches
    `create_session_cookie_value()` (and `_sign`'s RuntimeError) with a
    correct password but a missing secret."""
    if not settings.admin_password or not settings.admin_session_secret:
        return False
    return hmac.compare_digest(password, settings.admin_password)


def require_admin_session(prism_admin_session: str | None = Cookie(default=None)) -> None:
    """FastAPI dependency: raises 401 unless the request carries a valid,
    unexpired signed session cookie. Used on every `/api/admin/*` route
    except the login endpoint itself."""
    if not verify_session_cookie(prism_admin_session):
        raise HTTPException(status_code=401, detail="admin authentication required")
