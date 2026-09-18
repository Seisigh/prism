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
    return hmac.new(settings.admin_session_secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_cookie_value() -> str:
    issued_at = str(int(time.time()))
    return f"{issued_at}.{_sign(issued_at)}"


def verify_session_cookie(value: str | None) -> bool:
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
    """Fails closed when no password is configured (`settings.admin_password`
    is `None`) — an operator who forgot to set one gets a console nobody
    can log into, never one anybody can, per config.py's own docstring."""
    if not settings.admin_password:
        return False
    return hmac.compare_digest(password, settings.admin_password)


def require_admin_session(prism_admin_session: str | None = Cookie(default=None)) -> None:
    """FastAPI dependency: raises 401 unless the request carries a valid,
    unexpired signed session cookie. Used on every `/api/admin/*` route
    except the login endpoint itself."""
    if not verify_session_cookie(prism_admin_session):
        raise HTTPException(status_code=401, detail="admin authentication required")
