"""
Builds and verifies the Flask-Login session identity token "<user id>:<fingerprint>".
A password change kills every older session of that user without any DB change (R-21).
"""

import hashlib
import hmac
from collections.abc import Callable

from flask import current_app

from app.models.user import User


def fingerprint(user: User) -> str:
    """Return the first 16 hex chars of HMAC-SHA256(SECRET_KEY, user.password_hash)."""
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    msg = user.password_hash.encode("utf-8")
    h = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return h[:16]


def make_token(user: User) -> str:
    """Return the full session token '<id>:<fingerprint>'."""
    return f"{user.id}:{fingerprint(user)}"


def parse_token(token: str) -> tuple[int, str] | None:
    """Parse a token; return (user_id, fingerprint) or None if invalid."""
    if not token or ":" not in token:
        return None
    parts = token.split(":", 1)
    if len(parts) != 2:
        return None
    uid_str, fgpt = parts
    if len(fgpt) != 16:
        return None
    try:
        uid = int(uid_str)
        if uid <= 0:
            return None
    except ValueError:
        return None
    return uid, fgpt


def verify_token(token: str, loader: Callable[[int], User | None]) -> User | None:
    """Parse token, load user via loader, and compare fingerprints."""
    parsed = parse_token(token)
    if not parsed:
        return None
    uid, fgpt = parsed
    user = loader(uid)
    if not user:
        return None
    expected = fingerprint(user)
    if hmac.compare_digest(fgpt, expected):
        return user
    return None


def absolute_lifetime_exceeded(
    login_at_epoch: float | None, now_epoch: float, max_minutes: int
) -> bool:
    """Return True if login_at is missing, far in the future, or older than max_minutes."""
    if login_at_epoch is None:
        return True
    try:
        login_at = float(login_at_epoch)
    except (ValueError, TypeError):
        return True

    if login_at > now_epoch + 60:
        return True

    age_minutes = (now_epoch - login_at) / 60.0
    return age_minutes > max_minutes
