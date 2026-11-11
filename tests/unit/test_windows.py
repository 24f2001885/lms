"""
tests/unit/test_windows.py - Boundary tests for the time-window helper (PDR Risk R-3).
"""

from datetime import datetime

import pytest

from app.errors import WindowError
from app.services import windows


@pytest.mark.parametrize(
    "test_dt,switch_open,expected_open",
    [
        (datetime(2030, 1, 1, 9, 59, 59), True, False),   # 1 second before start
        (datetime(2030, 1, 1, 10, 0, 0), True, True),      # Exactly at start (inclusive)
        (datetime(2030, 1, 5, 12, 0, 0), True, True),      # Mid-window
        (datetime(2030, 1, 10, 18, 0, 0), True, True),    # Exactly at end (inclusive)
        (datetime(2030, 1, 10, 18, 0, 1), True, False),   # 1 second after end
        (datetime(2030, 1, 5, 12, 0, 0), False, False),   # Inside dates but switch OFF
    ],
)
def test_slot_creation_window_boundaries(app, make_examination, test_dt, switch_open, expected_open):
    exam = make_examination(
        slot_creation_start=datetime(2030, 1, 1, 10, 0, 0),
        slot_creation_end=datetime(2030, 1, 10, 18, 0, 0),
        slot_creation_open=switch_open,
    )
    assert windows.is_slot_creation_open(exam, now=test_dt) is expected_open


@pytest.mark.parametrize(
    "test_dt,switch_open,expected_open",
    [
        (datetime(2030, 1, 10, 9, 59, 59), True, False),  # 1 second before start
        (datetime(2030, 1, 10, 10, 0, 0), True, True),     # Exactly at start (inclusive)
        (datetime(2030, 1, 15, 12, 0, 0), True, True),     # Mid-window
        (datetime(2030, 1, 20, 18, 0, 0), True, True),     # Exactly at end (inclusive)
        (datetime(2030, 1, 20, 18, 0, 1), True, False),    # 1 second after end
        (datetime(2030, 1, 15, 12, 0, 0), False, False),   # Inside dates but switch OFF
    ],
)
def test_booking_window_boundaries(app, make_examination, test_dt, switch_open, expected_open):
    exam = make_examination(
        booking_start=datetime(2030, 1, 10, 10, 0, 0),
        booking_end=datetime(2030, 1, 20, 18, 0, 0),
        booking_open=switch_open,
    )
    assert windows.is_booking_open(exam, now=test_dt) is expected_open


def test_can_student_cancel_until_deadline_inclusive(app, make_examination):
    deadline = datetime(2030, 1, 18, 12, 0, 0)
    exam = make_examination(cancellation_deadline=deadline)

    assert windows.can_student_cancel(exam, now=datetime(2030, 1, 18, 11, 59, 59)) is True
    assert windows.can_student_cancel(exam, now=deadline) is True
    assert windows.can_student_cancel(exam, now=datetime(2030, 1, 18, 12, 0, 1)) is False


def test_slots_editable_only_before_booking_start(app, make_examination):
    b_start = datetime(2030, 1, 10, 10, 0, 0)
    exam = make_examination(booking_start=b_start)

    assert windows.slots_editable(exam, now=datetime(2030, 1, 10, 9, 59, 59)) is True
    # Exactly at booking_start, slots are locked from editing
    assert windows.slots_editable(exam, now=b_start) is False


def test_soft_deleted_exam_never_open(app, make_examination):
    exam = make_examination(
        booking_start=datetime(2030, 1, 1),
        booking_end=datetime(2030, 1, 20),
        booking_open=True,
        is_deleted=True,
    )
    assert windows.is_booking_open(exam, now=datetime(2030, 1, 10)) is False
    assert windows.is_slot_creation_open(exam, now=datetime(2030, 1, 5)) is False


def test_assert_helpers_raise_window_error_with_codes(app, make_examination):
    exam = make_examination(
        booking_start=datetime(2030, 1, 10),
        booking_end=datetime(2030, 1, 20),
        booking_open=False,
    )
    with pytest.raises(WindowError) as exc:
        windows.assert_booking_open(exam, now=datetime(2030, 1, 15))
    assert exc.value.code == "booking_closed"


def test_from_local_input_kolkata_to_utc(app):
    # Asia/Kolkata is UTC+5:30
    utc_dt = windows.from_local_input("2030-01-10T10:00")
    assert utc_dt == datetime(2030, 1, 10, 4, 30, 0)
    assert windows.to_input_value(utc_dt) == "2030-01-10T10:00"


def test_bad_local_input_raises_value_error(app):
    with pytest.raises(ValueError):
        windows.from_local_input("not-a-valid-date")