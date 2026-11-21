from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Booking, ExaminationSlot


def test_slot_booked_count_cannot_exceed_capacity(app, make_examination, make_examiner):
    """Verify that booked_count cannot exceed max_capacity at database level."""
    exam = make_examination()
    examiner = make_examiner()

    slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=datetime(2030, 1, 15, 10, 0),
        end_at=datetime(2030, 1, 15, 12, 0),
        max_capacity=5,
        booked_count=6,  # Exceeds max_capacity
    )
    db.session.add(slot)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_slot_seats_left_property(app, make_examination, make_examiner):
    """Verify seats_left calculation property."""
    exam = make_examination()
    examiner = make_examiner()

    slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=datetime(2030, 1, 15, 10, 0),
        end_at=datetime(2030, 1, 15, 12, 0),
        max_capacity=5,
        booked_count=2,
    )
    assert slot.seats_left == 3


def test_active_booking_unique_per_student_exam(
    app, make_examination, make_examiner, make_student, make_slot
):
    """Verify partial unique index blocks 2 active bookings for the same student on the same exam."""
    exam = make_examination()
    examiner = make_examiner()
    student = make_student()

    slot1 = make_slot(exam, examiner)
    slot2 = make_slot(
        exam, examiner, start_at=datetime(2030, 1, 16, 10, 0), end_at=datetime(2030, 1, 16, 12, 0)
    )

    b1 = Booking(
        student_id=student.id,
        slot_id=slot1.id,
        examination_id=exam.id,
        status="booked",
        booked_at=datetime.utcnow(),
    )
    db.session.add(b1)
    db.session.commit()

    # Attempting a second active booking on slot2 for the same exam must fail
    b2 = Booking(
        student_id=student.id,
        slot_id=slot2.id,
        examination_id=exam.id,
        status="booked",
        booked_at=datetime.utcnow(),
    )
    db.session.add(b2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_rebook_after_cancel_allowed(app, make_examination, make_examiner, make_student, make_slot):
    """Verify student CAN book again after cancelling previous booking (partial index ignores cancelled)."""
    exam = make_examination()
    examiner = make_examiner()
    student = make_student()

    slot1 = make_slot(exam, examiner)
    slot2 = make_slot(
        exam, examiner, start_at=datetime(2030, 1, 16, 10, 0), end_at=datetime(2030, 1, 16, 12, 0)
    )

    # Cancelled first booking
    b1 = Booking(
        student_id=student.id,
        slot_id=slot1.id,
        examination_id=exam.id,
        status="cancelled",
        booked_at=datetime.utcnow(),
        cancelled_at=datetime.utcnow(),
    )
    db.session.add(b1)
    db.session.commit()

    # Second active booking must succeed
    b2 = Booking(
        student_id=student.id,
        slot_id=slot2.id,
        examination_id=exam.id,
        status="booked",
        booked_at=datetime.utcnow(),
    )
    db.session.add(b2)
    db.session.commit()
    assert b2.id is not None


def test_partial_unique_index_sql_present(app):
    """Verify that uq_bookings_active_student_exam exists in sqlite_master with WHERE clause."""
    query = text(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='uq_bookings_active_student_exam';"
    )
    result = db.session.execute(query).scalar()
    assert result is not None
    assert "WHERE status IN ('booked', 'completed')" in result
