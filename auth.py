"""Signed-cookie session helpers (stdlib only; no DB queries live here)."""

import hashlib
import hmac
import os
import secrets

from database.db import get_user_by_id

COOKIE_NAME = "session"

# Falls back to a random per-process key: sessions reset on restart and do not
# work across multiple workers. Set SECRET_KEY in the environment to persist.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


def _signature(user_id):
    return hmac.new(
        SECRET_KEY.encode("utf-8"), str(user_id).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def sign_session(user_id):
    """Return the cookie value '<user_id>.<signature>'."""
    return f"{user_id}.{_signature(user_id)}"


def read_session(cookie_value):
    """Return the user id from a valid cookie value, else None."""
    if not cookie_value or "." not in cookie_value:
        return None
    raw_id, _, signature = cookie_value.partition(".")
    try:
        user_id = int(raw_id)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _signature(user_id)):
        return None
    return user_id


def set_session_cookie(response, user_id):
    response.set_cookie(
        COOKIE_NAME,
        sign_session(user_id),
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME, path="/")


def get_current_user(request):
    """Return the logged-in user row, or None. Cached on request.state."""
    if hasattr(request.state, "current_user"):
        return request.state.current_user
    user_id = read_session(request.cookies.get(COOKIE_NAME))
    user = get_user_by_id(user_id) if user_id is not None else None
    request.state.current_user = user
    return user
