"""
The two extension points (pre_booking_hooks and post_cancel_hooks) that keep
Tier 3 purely additive, and the Domain Events API for triggering emails safely
after business commits (P12).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("emp.events")


@dataclass(frozen=True)
class HookContext:
    student_id: int
    slot_id: int
    examination_id: int
    booking_id: int | None
    actor_id: int | None


pre_booking_hooks: list[Callable[[HookContext], None]] = []
post_cancel_hooks: list[Callable[[HookContext], None]] = []


def register_pre_booking(fn: Callable[[HookContext], None]) -> None:
    if fn not in pre_booking_hooks:
        pre_booking_hooks.append(fn)


def register_post_cancel(fn: Callable[[HookContext], None]) -> None:
    if fn not in post_cancel_hooks:
        post_cancel_hooks.append(fn)


def run_pre_booking(ctx: HookContext) -> None:
    for hook in pre_booking_hooks:
        hook(ctx)


def run_post_cancel(ctx: HookContext) -> None:
    for hook in post_cancel_hooks:
        try:
            hook(ctx)
        except Exception:
            logger.exception("post_cancel_hook failed")


# --- Domain Events API (P12) ---

EVENT_BOOKING_CREATED = "booking.created"
EVENT_BOOKING_CANCELLED = "booking.cancelled"
EVENT_BOOKING_RESCHEDULED = "booking.rescheduled"
EVENT_EXAMINER_APPROVED = "examiner.approved"
EVENT_EVALUATION_PUBLISHED = "evaluation.published"

_event_handlers: dict[str, list[Callable[..., None]]] = {}


def register_event(name: str, fn: Callable[..., None]) -> None:
    handlers = _event_handlers.setdefault(name, [])
    if fn not in handlers:
        handlers.append(fn)


def emit(name: str, **payload: Any) -> None:
    for handler in _event_handlers.get(name, []):
        try:
            handler(**payload)
        except Exception:
            logger.exception(f"Event handler failed for {name}")


def clear_events() -> None:
    _event_handlers.clear()


def clear_hooks() -> None:
    pre_booking_hooks.clear()
    post_cancel_hooks.clear()
