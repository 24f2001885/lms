"""
FILE PURPOSE: The ONLY place that knows the time and evaluates examination time windows (risk R-3: timezone and boundary bugs).
DEPENDS ON: app/models/examination.py, app/errors.py (WindowError, BOOKING_CLOSED, CANCEL_DEADLINE_PASSED), zoneinfo, app config APP_TIMEZONE.
PROMPT FOR LLM IMPLEMENTATION:
1. now_utc() returns the current time as a NAIVE UTC datetime (datetime.now(timezone.utc).replace(tzinfo=None)). It is the single clock of the whole project. Every other module must call it as windows.now_utc() through the module object, NEVER "from app.services.windows import now_utc", so tests can monkeypatch one attribute. Put this rule in a comment.
2. Timezone helpers using zoneinfo.ZoneInfo(current_app.config["APP_TIMEZONE"]): to_local(dt) (naive UTC -> aware local), from_local_input(text) (parse an HTML datetime-local string such as "2030-01-10T10:00", treat it as APP_TIMEZONE local time, return naive UTC, raise ValueError on bad text), format_local(dt, fmt="%d %b %Y, %H:%M") (empty string for None), to_input_value(dt) (naive UTC -> "YYYY-MM-DDTHH:MM" local, for pre-filling forms).
3. Constants for error codes defined here: SLOT_CREATION_CLOSED = "slot_creation_closed", SLOT_EDIT_LOCKED = "slot_edit_locked"; BOOKING_CLOSED and CANCEL_DEADLINE_PASSED come from app/errors.py.
4. Predicates, all taking (exam, now=None) and using now_utc() when now is None; boundaries are INCLUSIVE on both ends (start <= now <= end) as in TDR 3.3 step 3:
   - is_slot_creation_open: exam.slot_creation_open is True AND slot_creation_start <= now <= slot_creation_end AND not exam.is_deleted.
   - is_booking_open: exam.booking_open is True AND booking_start <= now <= booking_end AND not exam.is_deleted.
   - can_student_cancel: now <= exam.cancellation_deadline (the booking status check is the engine's job).
   - slots_editable: now < exam.booking_start (examiners may update or remove slots only BEFORE student booking starts, PDR 5.3).
5. Assertion helpers that raise WindowError(code, message): assert_slot_creation_open, assert_booking_open, assert_slots_editable, assert_can_cancel. Messages are plain English and include the relevant local date when useful ("Slot creation opens on 10 Jan 2030, 10:00.", "Booking is closed.").
6. window_state(exam, now=None) returns a dict for the UI: {"slot_creation": {"open": bool, "label": "Open"/"Closed"/"Scheduled", "reason": str}, "booking": {...}, "cancel": {...}} where reason explains WHY it is closed (switch off, not started yet with the start date, ended, deleted). This feeds the disabled-button reason lines required by Design Plan principle 3.
7. No database access in this file other than reading attributes of the Examination object passed in.
DEBUGGING:
# print(f"[DEBUG] windows now={now} booking={exam.booking_start}->{exam.booking_end} flag={exam.booking_open} open={result}")
OFFLINE DOCKER TEST CASES:
- is_booking_open is False when the switch is off even inside the dates, False when the switch is on but now is 1 second before booking_start, True exactly at booking_start and exactly at booking_end, False 1 second after booking_end.
- from_local_input("2030-01-10T10:00") with APP_TIMEZONE Asia/Kolkata returns 2030-01-10 04:30 (naive UTC); to_input_value reverses it.
- from_local_input("not a date") raises ValueError.
- window_state reason mentions the start date when booking has not started.
- grep over app/ finds no "from app.services.windows import now_utc".

app/services/windows.py - Centralized timeline window and schedule verification service.

Provides a unified UTC time provider and window constraint assertion functions
to prevent timezone drift and scheduling bugs (PDR Risk R-3, TDR Section 1).
"""

from datetime import UTC, datetime

from app.errors import WindowError
from app.models.examination import Examination


def now_utc() -> datetime:
    """
    Return current time in naive UTC (matching SQLite's CURRENT_TIMESTAMP).
    Single source of truth for all timeline and booking window checks.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def is_slot_creation_open(exam: Examination, current_time: datetime | None = None) -> bool:
    """
    Return True if examiner slot creation is currently permitted.
    Requires BOTH the Admin toggle switch to be True AND current time to be
    within slot_creation_start and slot_creation_end.
    """
    if not exam.slot_creation_open:
        return False

    now = current_time or now_utc()
    return exam.slot_creation_start <= now <= exam.slot_creation_end


def assert_slot_creation_open(exam: Examination, current_time: datetime | None = None) -> None:
    """
    Raise WindowError if examiner slot creation window is closed.
    """
    now = current_time or now_utc()
    if not exam.slot_creation_open:
        raise WindowError(
            code="slot_creation_closed",
            message=f"Slot creation is currently closed by administrator for '{exam.name}'.",
        )
    if now < exam.slot_creation_start:
        raise WindowError(
            code="slot_creation_not_started",
            message=f"Slot creation for '{exam.name}' has not opened yet.",
        )
    if now > exam.slot_creation_end:
        raise WindowError(
            code="slot_creation_ended",
            message=f"Slot creation deadline for '{exam.name}' has passed.",
        )


def is_booking_open(exam: Examination, current_time: datetime | None = None) -> bool:
    """
    Return True if student booking is currently open.
    Requires BOTH the Admin toggle switch to be True AND current time to be
    within booking_start and booking_end.
    """
    if not exam.booking_open:
        return False

    now = current_time or now_utc()
    return exam.booking_start <= now <= exam.booking_end


def assert_booking_open(exam: Examination, current_time: datetime | None = None) -> None:
    """
    Raise WindowError if student booking window is closed.
    """
    now = current_time or now_utc()
    if not exam.booking_open:
        raise WindowError(
            code="booking_closed",
            message=f"Student booking is currently disabled by administrator for '{exam.name}'.",
        )
    if now < exam.booking_start:
        raise WindowError(
            code="booking_not_started",
            message=f"Booking for '{exam.name}' opens on {exam.booking_start.strftime('%d %b %Y, %H:%M')}.",
        )
    if now > exam.booking_end:
        raise WindowError(
            code="booking_ended",
            message=f"Booking for '{exam.name}' closed on {exam.booking_end.strftime('%d %b %Y, %H:%M')}.",
        )


def is_cancellation_allowed(exam: Examination, current_time: datetime | None = None) -> bool:
    """
    Return True if student booking cancellation is allowed (now <= cancellation_deadline).
    """
    now = current_time or now_utc()
    return now <= exam.cancellation_deadline


def assert_cancellation_allowed(exam: Examination, current_time: datetime | None = None) -> None:
    """
    Raise WindowError if cancellation deadline has elapsed.
    """
    now = current_time or now_utc()
    if now > exam.cancellation_deadline:
        raise WindowError(
            code="cancel_deadline_passed",
            message=f"Cancellation deadline for '{exam.name}' has passed.",
        )