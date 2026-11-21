"""
FILE PURPOSE: The two extension points that keep Tier 3 purely additive (TDR section 2): pre_booking_hooks and post_cancel_hooks. Both lists stay EMPTY in Tier 1 and Tier 2.
DEPENDS ON: nothing (standard library only). Must not import booking_engine (avoid circular imports).
PROMPT FOR LLM IMPLEMENTATION:
1. Define a frozen dataclass HookContext with fields: student_id (int), slot_id (int), examination_id (int), booking_id (int | None), actor_id (int | None).
2. Module-level lists pre_booking_hooks and post_cancel_hooks (typed as list of callables taking a HookContext). They are empty at import time.
3. register_pre_booking(fn) and register_post_cancel(fn) append a function (ignore duplicates). clear_hooks() empties both lists (tests only).
4. run_pre_booking(ctx): call every pre hook in registration order INSIDE the booking transaction; a hook may raise a BookingError to veto the booking; any other exception propagates (the caller rolls back). Returns None.
5. run_post_cancel(ctx): call every post hook AFTER the cancel transaction has committed; exceptions are caught, logged with logger.exception (never the payload) and never undo the cancellation.
6. Document in the module docstring that Tier 3 payments (P16) register one hook of each kind and that Tier 1/2 code never imports anything from a tier3 package.
DEBUGGING:
# print(f"[DEBUG] hooks pre={len(pre_booking_hooks)} post={len(post_cancel_hooks)} ctx={ctx}")
OFFLINE DOCKER TEST CASES:
- Both lists are empty after import and after clear_hooks().
- A registered pre hook that raises BookingError("payment_required", ...) stops book_slot and no booking row exists.
- A registered post hook that raises RuntimeError does not stop cancel_booking from committing.
- Hooks run in registration order; registering the same function twice runs it once.

FILE PURPOSE: Extension points for Tier 3 additive features (pre_booking_hooks and post_cancel_hooks).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HookContext:
    student_id: int
    slot_id: int
    examination_id: int
    booking_id: int | None = None
    actor_id: int | None = None


pre_booking_hooks: list[Callable[[HookContext], None]] = []
post_cancel_hooks: list[Callable[[HookContext], None]] = []


def register_pre_booking(fn: Callable[[HookContext], None]) -> None:
    if fn not in pre_booking_hooks:
        pre_booking_hooks.append(fn)


def register_post_cancel(fn: Callable[[HookContext], None]) -> None:
    if fn not in post_cancel_hooks:
        post_cancel_hooks.append(fn)


def clear_hooks() -> None:
    pre_booking_hooks.clear()
    post_cancel_hooks.clear()


def run_pre_booking(ctx: HookContext) -> None:
    for hook in list(pre_booking_hooks):
        hook(ctx)


def run_post_cancel(ctx: HookContext) -> None:
    for hook in list(post_cancel_hooks):
        try:
            hook(ctx)
        except Exception:
            logger.exception(
                "Error executing post_cancel_hook for student_id=%s, booking_id=%s",
                ctx.student_id,
                ctx.booking_id,
            )
