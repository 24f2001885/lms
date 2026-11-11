"""
app/services/windows.py - Unified time provider and timeline window verification.

The ONLY place in the application that evaluates timeline windows (PDR Risk R-3).
Other modules MUST call windows.now_utc() via module reference, never direct import.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from flask import current_app

from app.errors import BOOKING_CLOSED, CANCEL_DEADLINE_PASSED, WindowError
from app.models.examination import Examination

SLOT_CREATION_CLOSED = "slot_creation_closed"
SLOT_EDIT_LOCKED = "slot_edit_locked"


def now_utc() -> datetime:
    """Return current naive UTC datetime (the single system clock)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _get_tz() -> ZoneInfo:
    """Resolve display timezone from Flask config."""
    tz_name = current_app.config.get("APP_TIMEZONE", "Asia/Kolkata")
    return ZoneInfo(tz_name)


def to_local(dt: datetime | None) -> datetime | None:
    """Convert naive UTC datetime to aware local timezone datetime."""
    if dt is None:
        return None
    utc_dt = dt.replace(tzinfo=UTC)
    return utc_dt.astimezone(_get_tz())


def from_local_input(text: str | None) -> datetime:
    """Parse local HTML datetime-local string (YYYY-MM-DDTHH:MM) to naive UTC."""
    if not text or not text.strip():
        raise ValueError("Empty datetime string")
    clean = text.strip()
    try:
        local_dt = datetime.fromisoformat(clean)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {clean}") from e

    aware_local = local_dt.replace(tzinfo=_get_tz())
    utc_aware = aware_local.astimezone(UTC)
    return utc_aware.replace(tzinfo=None)


def format_local(dt: datetime | None, fmt: str = "%d %b %Y, %H:%M") -> str:
    """Format naive UTC datetime as local timezone display string."""
    if dt is None:
        return ""
    local_dt = to_local(dt)
    return local_dt.strftime(fmt)


def to_input_value(dt: datetime | None) -> str:
    """Convert naive UTC datetime to local YYYY-MM-DDTHH:MM for HTML inputs."""
    if dt is None:
        return ""
    local_dt = to_local(dt)
    return local_dt.strftime("%Y-%m-%dT%H:%M")


def is_slot_creation_open(exam: Examination, now: datetime | None = None) -> bool:
    """Return True if slot creation is open (switch on, within dates, not deleted)."""
    if exam.is_deleted or not exam.slot_creation_open:
        return False
    current = now or now_utc()
    return exam.slot_creation_start <= current <= exam.slot_creation_end


def is_booking_open(exam: Examination, now: datetime | None = None) -> bool:
    """Return True if student booking is open (switch on, within dates, not deleted)."""
    if exam.is_deleted or not exam.booking_open:
        return False
    current = now or now_utc()
    return exam.booking_start <= current <= exam.booking_end


def can_student_cancel(exam: Examination, now: datetime | None = None) -> bool:
    """Return True if current time is within the cancellation deadline."""
    if exam.is_deleted:
        return False
    current = now or now_utc()
    return current <= exam.cancellation_deadline


def slots_editable(exam: Examination, now: datetime | None = None) -> bool:
    """Examiners may create, update, or remove slots only BEFORE booking opens."""
    if exam.is_deleted:
        return False
    current = now or now_utc()
    return current < exam.booking_start


def assert_slot_creation_open(exam: Examination, now: datetime | None = None) -> None:
    current = now or now_utc()
    if exam.is_deleted or not exam.slot_creation_open:
        raise WindowError(SLOT_CREATION_CLOSED, f"Slot creation is closed for '{exam.name}'.")
    if current < exam.slot_creation_start:
        raise WindowError(SLOT_CREATION_CLOSED, f"Slot creation opens on {format_local(exam.slot_creation_start)}.")
    if current > exam.slot_creation_end:
        raise WindowError(SLOT_CREATION_CLOSED, "Slot creation period has ended.")


def assert_booking_open(exam: Examination, now: datetime | None = None) -> None:
    current = now or now_utc()
    if exam.is_deleted or not exam.booking_open:
        raise WindowError(BOOKING_CLOSED, f"Booking is closed for '{exam.name}'.")
    if current < exam.booking_start:
        raise WindowError(BOOKING_CLOSED, f"Booking opens on {format_local(exam.booking_start)}.")
    if current > exam.booking_end:
        raise WindowError(BOOKING_CLOSED, "Booking period has ended.")


def assert_slots_editable(exam: Examination, now: datetime | None = None) -> None:
    current = now or now_utc()
    if not slots_editable(exam, current):
        raise WindowError(SLOT_EDIT_LOCKED, "Slots cannot be modified once booking has opened.")


def assert_can_cancel(exam: Examination, now: datetime | None = None) -> None:
    current = now or now_utc()
    if not can_student_cancel(exam, current):
        raise WindowError(CANCEL_DEADLINE_PASSED, "Cancellation deadline has passed.")


def window_state(exam: Examination, now: datetime | None = None) -> dict:
    """Return dictionary of window states and user-facing reasons for buttons."""
    current = now or now_utc()

    # Slot creation state
    sc_open = is_slot_creation_open(exam, current)
    if exam.is_deleted:
        sc_reason = "Examination deleted"
    elif not exam.slot_creation_open:
        sc_reason = "Switch closed by administrator"
    elif current < exam.slot_creation_start:
        sc_reason = f"Opens on {format_local(exam.slot_creation_start)}"
    elif current > exam.slot_creation_end:
        sc_reason = "Creation period ended"
    else:
        sc_reason = f"Closes on {format_local(exam.slot_creation_end)}"

    # Booking state
    bk_open = is_booking_open(exam, current)
    if exam.is_deleted:
        bk_reason = "Examination deleted"
    elif not exam.booking_open:
        bk_reason = "Switch closed by administrator"
    elif current < exam.booking_start:
        bk_reason = f"Opens on {format_local(exam.booking_start)}"
    elif current > exam.booking_end:
        bk_reason = "Booking period ended"
    else:
        bk_reason = f"Closes on {format_local(exam.booking_end)}"

    return {
        "slot_creation": {
            "open": sc_open,
            "label": "Open" if sc_open else "Closed",
            "reason": sc_reason,
        },
        "booking": {
            "open": bk_open,
            "label": "Open" if bk_open else "Closed",
            "reason": bk_reason,
        },
        "cancel": {
            "allowed": can_student_cancel(exam, current),
            "deadline_str": format_local(exam.cancellation_deadline),
        },
    }