"""
FILE PURPOSE: Rule tests for reschedule_booking, admin_cancel_booking, cancel_slot, and change_examiner.
"""

from datetime import timedelta

import pytest

from app.errors import BookingError
from app.models import (
    AuditLog,
    Evaluation,
    ExaminationExaminer,
    ExaminationSlot,
    User,
)
from app.services import admin_service, audit_service, booking_engine, hooks
from tests.unit.test_booking_engine_concurrency import _assert_slot_invariants


@pytest.fixture(autouse=True)
def _clean_hooks():
    hooks.clear_hooks()
    yield
    hooks.clear_hooks()


def test_reschedule_moves_booking_and_counts(
    app, db_session, admin, make_open_booking_setup, freeze_now
):
    exam, slot1, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    slot2 = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=slot1.start_at + timedelta(hours=3),
        end_at=slot1.end_at + timedelta(hours=3),
        max_capacity=1,
        status="available",
    )
    db_session.add(slot2)
    db_session.commit()

    booking = booking_engine.book_slot(students[0].id, slot1.id)
    db_session.refresh(slot1)
    assert slot1.status == "full"

    moved = booking_engine.reschedule_booking(booking.id, slot2.id, admin.id)
    db_session.refresh(slot1)
    db_session.refresh(slot2)

    assert moved.slot_id == slot2.id
    assert moved.rescheduled_from_slot_id == slot1.id
    assert slot1.booked_count == 0
    assert slot1.status == "available"
    assert slot2.booked_count == 1
    assert slot2.status == "full"

    audit = AuditLog.query.filter_by(
        action=audit_service.BOOKING_RESCHEDULE, entity_id=booking.id
    ).first()
    assert audit is not None
    _assert_slot_invariants(db_session)


def test_reschedule_refusals(app, db_session, admin, make_open_booking_setup, freeze_now):
    exam, slot1, examiner, students = make_open_booking_setup(student_count=2, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    slot2 = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=slot1.start_at + timedelta(hours=3),
        end_at=slot1.end_at + timedelta(hours=3),
        max_capacity=1,
        status="available",
    )
    db_session.add(slot2)
    db_session.commit()

    b1 = booking_engine.book_slot(students[0].id, slot1.id)
    booking_engine.book_slot(students[1].id, slot2.id)

    # Same slot refused
    with pytest.raises(BookingError) as exc:
        booking_engine.reschedule_booking(b1.id, slot1.id, admin.id)
    assert exc.value.code == "same_slot"

    # Full target slot refused
    with pytest.raises(BookingError) as exc:
        booking_engine.reschedule_booking(b1.id, slot2.id, admin.id)
    assert exc.value.code == "slot_full"

    # Evaluation attached refused
    ev = Evaluation(booking_id=b1.id, examiner_id=examiner.id, total_marks=50, status="draft")
    db_session.add(ev)
    db_session.commit()

    slot3 = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=slot1.start_at + timedelta(hours=6),
        end_at=slot1.end_at + timedelta(hours=6),
        max_capacity=2,
        status="available",
    )
    db_session.add(slot3)
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.reschedule_booking(b1.id, slot3.id, admin.id)
    assert exc.value.code == "booking_has_evaluation"
    _assert_slot_invariants(db_session)


def test_admin_cancel_booking_rules(app, db_session, admin, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=2)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)

    # Reason required
    with pytest.raises(BookingError) as exc:
        booking_engine.admin_cancel_booking(booking.id, admin.id, "no")
    assert exc.value.code == "reason_required"

    # Past student deadline still allowed for admin
    freeze_now(exam.booking_end + timedelta(days=1))
    called = []
    hooks.register_post_cancel(lambda ctx: called.append(ctx.actor_id))

    booking_engine.admin_cancel_booking(booking.id, admin.id, "Schedule conflict resolved")
    db_session.refresh(booking)
    db_session.refresh(slot)

    assert booking.status == "cancelled"
    assert booking.cancelled_by == admin.id
    assert slot.booked_count == 0
    assert called == [admin.id]
    _assert_slot_invariants(db_session)


def test_cancel_slot_cancels_bookings_and_zeroes_count(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=2, capacity=2)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking_engine.book_slot(students[0].id, slot.id)
    booking_engine.book_slot(students[1].id, slot.id)

    hook_calls = []
    hooks.register_post_cancel(lambda ctx: hook_calls.append(ctx.booking_id))

    cancelled_count = booking_engine.cancel_slot(slot.id, examiner.id, "Examiner medical emergency")
    assert cancelled_count == 2
    assert len(hook_calls) == 2

    db_session.refresh(slot)
    assert slot.status == "cancelled"
    assert slot.booked_count == 0
    _assert_slot_invariants(db_session)


def test_change_examiner_delegation_and_rules(
    app, db_session, admin, make_open_booking_setup, freeze_now
):
    exam, slot, examiner1, students = make_open_booking_setup(student_count=1, capacity=2)
    freeze_now(exam.booking_start + timedelta(hours=1))

    examiner2 = User(
        email="ex2@test.local",
        password_hash="hash",
        full_name="Examiner Two",
        role="examiner",
        approval_status="approved",
        is_active=True,
    )
    db_session.add(examiner2)
    db_session.flush()
    db_session.add(
        ExaminationExaminer(
            examination_id=exam.id,
            examiner_id=examiner2.id,
            assigned_by=admin.id,
            assigned_at=exam.booking_start,
        )
    )
    db_session.commit()

    updated = admin_service.change_slot_examiner(admin.id, slot.id, examiner2.id)
    assert updated.examiner_id == examiner2.id
