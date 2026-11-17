"""
In-process sliding-window rate limiter and the rate_limited decorator.
"""

import hashlib
from collections import deque
from collections.abc import Callable
from threading import Lock
from typing import Any

from flask import g, make_response, request

from app.errors import error_response
from app.services import windows


class SlidingWindowLimiter:
    def __init__(self, max_failures: int, window_seconds: int, max_keys: int = 10000):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._store: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = windows.now_utc().timestamp()
        with self._lock:
            if key not in self._store:
                return True, 0
            timestamps = self._store[key]
            while timestamps and timestamps[0] < now - self.window_seconds:
                timestamps.popleft()
            if not timestamps:
                del self._store[key]
                return True, 0
            count = len(timestamps)
            if count >= self.max_failures:
                retry_after = int(timestamps[0] + self.window_seconds - now)
                if retry_after < 1:
                    retry_after = 1
                return False, retry_after
            return True, 0

    def record_failure(self, key: str) -> bool:
        now = windows.now_utc().timestamp()
        with self._lock:
            if key not in self._store:
                if len(self._store) >= self.max_keys:
                    self._evict()
                self._store[key] = deque()
            timestamps = self._store[key]
            timestamps.append(now)
            while timestamps and timestamps[0] < now - self.window_seconds:
                timestamps.popleft()
            return len(timestamps) == self.max_failures

    def reset(self, key: str) -> None:
        with self._lock:
            if key in self._store:
                del self._store[key]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict(self) -> None:
        if not self._store:
            return
        oldest_key = None
        oldest_time = float("inf")
        for k, dq in self._store.items():
            if dq and dq[-1] < oldest_time:
                oldest_time = dq[-1]
                oldest_key = k
        if oldest_key:
            del self._store[oldest_key]
        else:
            self._store.popitem()


class ProxyLimiter:
    def __init__(
        self, config_key_failures: str, config_key_window: str = "LOGIN_RATE_LIMIT_WINDOW_MINUTES"
    ):
        self.config_key_failures = config_key_failures
        self.config_key_window = config_key_window
        self._instance: SlidingWindowLimiter | None = None
        self._lock = Lock()

    def _get_limiter(self) -> SlidingWindowLimiter:
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    max_f = 5
                    win_m = 15
                    try:
                        from flask import current_app

                        if current_app:
                            max_f = current_app.config.get(self.config_key_failures, 5)
                            win_m = current_app.config.get(self.config_key_window, 15)
                    except RuntimeError:
                        # Outside of application context; fall back to defaults
                        max_f = 5
                        win_m = 15
                    self._instance = SlidingWindowLimiter(max_f, win_m * 60)
        return self._instance

    def check(self, key: str) -> tuple[bool, int]:
        return self._get_limiter().check(key)

    def record_failure(self, key: str) -> bool:
        return self._get_limiter().record_failure(key)

    def reset(self, key: str) -> None:
        if self._instance is not None:
            self._instance.reset(key)

    def clear(self) -> None:
        if self._instance is not None:
            self._instance.clear()


login_limiter = ProxyLimiter("LOGIN_RATE_LIMIT_FAILURES")
ip_limiter = ProxyLimiter("LOGIN_RATE_LIMIT_IP_FAILURES")
password_limiter = ProxyLimiter("LOGIN_RATE_LIMIT_FAILURES")


def reset_all():
    login_limiter.clear()
    ip_limiter.clear()
    password_limiter.clear()


def login_keys(email: str, ip: str) -> list[str]:
    em_hash = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
    return [f"login:{em_hash}:{ip}", f"ip:{ip}"]


def password_key(user_id: int) -> str:
    return f"pw:{user_id}"


def rate_limited(kind: str) -> Callable:
    """
    Decorator for POST views to apply rate limiting based on `kind` ("login" or "password").
    Sets g.auth_outcome = "success" | "failure" | None inside the view.
    """

    def decorator(view_func: Callable) -> Callable:
        import functools
        import logging

        from app.extensions import db
        from app.services.audit_service import AUTH_LOCKOUT, log_action

        logger = logging.getLogger("emp.security")

        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if request.method != "POST":
                return view_func(*args, **kwargs)

            ip = request.remote_addr or "127.0.0.1"
            keys = []

            if kind == "login":
                email = request.form.get("email", "")
                if not email and request.is_json:
                    email = request.get_json(silent=True).get("email", "")
                keys = login_keys(email, ip)
            elif kind == "password":
                user_id = getattr(g.user, "id", None) if hasattr(g, "user") and g.user else None
                if user_id:
                    keys = [password_key(user_id)]

            for key in keys:
                limiter = (
                    ip_limiter
                    if key.startswith("ip:")
                    else (login_limiter if key.startswith("login:") else password_limiter)
                )
                allowed, retry_after = limiter.check(key)
                if not allowed:
                    logger.warning(f"rate limit blocked kind={kind} key={key[:20]}")
                    msg = f"Too many failed attempts. Try again in {(retry_after + 59) // 60} minutes."
                    if request.path.startswith("/api/"):
                        resp = error_response("too_many_requests", msg, 429)
                        resp.headers["Retry-After"] = str(retry_after)
                        return resp
                    else:
                        from flask import current_app

                        blocked_cb = current_app.view_functions.get("auth.blocked_response")
                        if blocked_cb:
                            resp = blocked_cb(kind, retry_after)
                            resp.headers["Retry-After"] = str(retry_after)
                            return resp
                        else:
                            resp = make_response(msg, 429)
                            resp.headers["Retry-After"] = str(retry_after)
                            return resp

            g.auth_outcome = None
            response = view_func(*args, **kwargs)

            outcome = getattr(g, "auth_outcome", None)
            if outcome == "failure":
                for key in keys:
                    limiter = (
                        ip_limiter
                        if key.startswith("ip:")
                        else (login_limiter if key.startswith("login:") else password_limiter)
                    )
                    became_blocked = limiter.record_failure(key)
                    if became_blocked:
                        log_action(
                            None,
                            AUTH_LOCKOUT,
                            "system",
                            None,
                            {"scope": kind, "key": key[:20]},
                            ip_address=ip,
                        )
                        db.session.commit()
            elif outcome == "success":
                for key in keys:
                    if not key.startswith("ip:"):
                        limiter = login_limiter if key.startswith("login:") else password_limiter
                        limiter.reset(key)

            return response

        return wrapper

    return decorator
