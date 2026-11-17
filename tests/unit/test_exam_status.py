"""
tests/unit/test_exam_status.py - Lifecycle status computation tests for examinations.
"""

from datetime import datetime

from app.services import exam_status


def test_draft_before_any_window(app, make_examination):
    exam = make_examination(
        slot_creation_start=datetime(2030, 1, 5),
        slot_creation_open=False,
        booking_open=False,
    )
    assert exam_status.compute_status(exam, now=datetime(2030, 1, 1)) == "draft"


def test_slot_creation_when_open(app, make_examination):
    exam = make_examination(
        slot_creation_start=datetime(2030, 1, 1),
        slot_creation_end=datetime(2030, 1, 10),
        slot_creation_open=True,
    )
    assert exam_status.compute_status(exam, now=datetime(2030, 1, 5)) == "slot_creation"


def test_booking_open_when_open(app, make_examination):
    exam = make_examination(
        booking_start=datetime(2030, 1, 10),
        booking_end=datetime(2030, 1, 20),
        booking_open=True,
    )
    assert exam_status.compute_status(exam, now=datetime(2030, 1, 15)) == "booking_open"


def test_closed_after_booking_end_without_slots(app, make_examination):
    exam = make_examination(booking_end=datetime(2030, 1, 20))
    assert exam_status.compute_status(exam, now=datetime(2030, 1, 25)) == "closed"


def test_completed_after_all_slots_past_and_evaluated(
    app, make_examination, make_examiner, make_student, make_slot, make_booking, make_evaluation
):
    exam = make_examination(booking_end=datetime(2030, 1, 20))
    examiner = make_examiner()
    student = make_student()

    slot = make_slot(
        exam, examiner, start_at=datetime(2030, 1, 21, 10, 0), end_at=datetime(2030, 1, 21, 12, 0)
    )
    booking = make_booking(student, slot)
    make_evaluation(booking, examiner, status="published", total=85.0)

    # After slot ends at 12:00
    assert exam_status.compute_status(exam, now=datetime(2030, 1, 22, 10, 0)) == "completed"


def test_closed_when_one_booking_unevaluated(
    app, make_examination, make_examiner, make_student, make_slot, make_booking
):
    exam = make_examination(booking_end=datetime(2030, 1, 20))
    examiner = make_examiner()
    student = make_student()

    slot = make_slot(
        exam, examiner, start_at=datetime(2030, 1, 21, 10, 0), end_at=datetime(2030, 1, 21, 12, 0)
    )
    make_booking(student, slot)  # Unevaluated booking

    assert exam_status.compute_status(exam, now=datetime(2030, 1, 22, 10, 0)) == "closed"


def test_refresh_status_writes_one_audit_row_and_is_idempotent(app, make_examination, make_admin):
    admin = make_admin()
    exam = make_examination(
        booking_start=datetime(2030, 1, 10),
        booking_end=datetime(2030, 1, 20),
        booking_open=True,
    )
    now = datetime(2030, 1, 15)

    # First refresh: transitions draft -> booking_open
    changed1 = exam_status.refresh_status(exam, actor_id=admin.id, now=now)
    assert changed1 is True
    assert exam.status == "booking_open"

    # Second refresh: status unchanged, returns False
    changed2 = exam_status.refresh_status(exam, actor_id=admin.id, now=now)
    assert changed2 is False
