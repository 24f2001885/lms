"""
FILE PURPOSE: P6 additions for tests/conftest.py (run_in_threads concurrency helper and mutable clock fixture).
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.services import windows


def run_in_threads(app, functions, barrier: bool = True):
    """Execute callables concurrently inside isolated Flask app contexts."""
    db.session.remove()
    sync_barrier = threading.Barrier(len(functions)) if barrier and len(functions) > 1 else None

    def _worker(fn):
        if sync_barrier is not None:
            sync_barrier.wait(timeout=10)
        with app.app_context():
            try:
                return fn()
            except Exception as exc:
                db.session.rollback()
                return exc
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        futures = [pool.submit(_worker, fn) for fn in functions]
        return [f.result() for f in futures]


class MutableClock:
    def __init__(self, initial: datetime):
        self._now = initial

    def now(self) -> datetime:
        return self._now

    def set(self, dt: datetime) -> None:
        self._now = dt

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


@pytest.fixture
def clock(monkeypatch):
    clk = MutableClock(windows.now_utc())
    monkeypatch.setattr(windows, "now_utc", clk.now)
    return clk
