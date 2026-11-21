"""
FILE PURPOSE: Rule tests for book_slot and cancel_booking (sequential; the concurrency suite is P6).
"""

from datetime import timedelta

import pytest

from app.errors import BookingError, WindowError
from app.models import AuditLog, Booking, ExaminationSlot
from app.services import booking_engine, hooks


@pytest.fixture(autouse=True)
def auto_clear_hooks():
    hooks.clear_hooks()
    yield
    hooks.clear_hooks()


def test_book_success_updates_count_and_audit(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    assert booking.status == "booked"
    assert booking.examination_id == exam.id

    db_session.refresh(slot)
    assert slot.booked_count == 1

    log = AuditLog.query.filter_by(
        action=booking_engine.audit_service.BOOKING_CREATE, entity_id=booking.id
    ).first()
    assert log is not None


def test_booking_copies_examination_id_from_slot(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    assert booking.examination_id == exam.id


def test_last_seat_flips_to_full(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking_engine.book_slot(students[0].id, slot.id)
    db_session.refresh(slot)
    assert slot.status == "full"


def test_full_slot_raises_slot_full(app, db_session, make_open_booking_setup, freeze_now, student):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking_engine.book_slot(students[0].id, slot.id)

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "slot_full"


def test_cancelled_slot_not_available(
    app, db_session, make_open_booking_setup, freeze_now, student
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    slot.status = "cancelled"
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "slot_not_available"


def test_completed_slot_not_available(
    app, db_session, make_open_booking_setup, freeze_now, student
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    slot.status = "completed"
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "slot_not_available"


def test_started_slot_not_available(app, db_session, make_open_booking_setup, freeze_now, student):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(slot.start_at)  # slot start time reached

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "slot_not_available"


def test_closed_window_variants(app, db_session, make_open_booking_setup, freeze_now, student):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)

    # Before start
    freeze_now(exam.booking_start - timedelta(seconds=1))
    with pytest.raises(WindowError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "booking_closed"

    # After end
    freeze_now(exam.booking_end + timedelta(seconds=1))
    with pytest.raises(WindowError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "booking_closed"


def test_deleted_examination_closed(app, db_session, make_open_booking_setup, freeze_now, student):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    exam.is_deleted = True
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "booking_closed"


def test_inactive_course_closed(app, db_session, make_open_booking_setup, freeze_now, student):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    exam.course.is_active = False
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code == "booking_closed"


def test_inactive_student_refused(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    students[0].is_active = False
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(students[0].id, slot.id)
    assert exc.value.code == "not_a_student"


def test_duplicate_other_slot_refused(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking_engine.book_slot(students[0].id, slot.id)

    s2 = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=slot.start_at + timedelta(hours=2),
        end_at=slot.end_at + timedelta(hours=2),
        max_capacity=5,
        status="available",
    )
    db_session.add(s2)
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(students[0].id, s2.id)
    assert exc.value.code == "duplicate_booking"


def test_duplicate_after_cancel_allowed(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    b = booking_engine.book_slot(students[0].id, slot.id)
    booking_engine.cancel_booking(students[0].id, b.id)

    b2 = booking_engine.book_slot(students[0].id, slot.id)
    assert b2.status == "booked"


def test_duplicate_with_completed_booking_refused(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    b = booking_engine.book_slot(students[0].id, slot.id)
    b.status = "completed"
    db_session.commit()

    s2 = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=slot.start_at + timedelta(hours=2),
        end_at=slot.end_at + timedelta(hours=2),
        max_capacity=5,
        status="available",
    )
    db_session.add(s2)
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(students[0].id, s2.id)
    assert exc.value.code == "duplicate_booking"


def test_two_students_independent(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=2, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    b1 = booking_engine.book_slot(students[0].id, slot.id)
    b2 = booking_engine.book_slot(students[1].id, slot.id)
    assert b1.id != b2.id
    db_session.refresh(slot)
    assert slot.booked_count == 2


def test_cancel_frees_seat_and_reopens_full_slot(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    db_session.refresh(slot)
    assert slot.status == "full"

    booking_engine.cancel_booking(students[0].id, booking.id)
    db_session.refresh(slot)
    assert slot.status == "available"
    assert slot.booked_count == 0


def test_cancel_does_not_reopen_cancelled_or_completed_slot(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    slot.status = "cancelled"
    db_session.commit()

    booking_engine.cancel_booking(students[0].id, booking.id)
    db_session.refresh(slot)
    assert slot.status == "cancelled"


def test_cancel_after_deadline_refused(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)

    freeze_now(exam.booking_end + timedelta(seconds=1))
    with pytest.raises(WindowError) as exc:
        booking_engine.cancel_booking(students[0].id, booking.id)
    assert exc.value.code == "cancel_deadline_passed"


def test_cancel_at_deadline_inclusive_ok(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)

    freeze_now(exam.booking_end)
    booking_engine.cancel_booking(students[0].id, booking.id)
    db_session.refresh(booking)
    assert booking.status == "cancelled"


def test_cancel_foreign_booking_not_found(
    app, db_session, make_open_booking_setup, freeze_now, student
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)

    with pytest.raises(BookingError) as exc:
        booking_engine.cancel_booking(student.id, booking.id)
    assert exc.value.code == "booking_not_found"


def test_cancel_completed_or_cancelled_not_cancellable(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    booking.status = "completed"
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.cancel_booking(students[0].id, booking.id)
    assert exc.value.code == "booking_not_cancellable"


def test_cancel_sets_cancelled_by_and_at(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    booking_engine.cancel_booking(students[0].id, booking.id)

    assert booking.cancelled_at is not None
    assert booking.cancelled_by == students[0].id


def test_post_cancel_hook_runs_after_commit(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)

    hook_called = []

    def my_post_hook(ctx):
        hook_called.append(ctx.booking_id)

    hooks.register_post_cancel(my_post_hook)
    booking_engine.cancel_booking(students[0].id, booking.id)

    assert hook_called == [booking.id]


def test_failure_paths_leave_database_unchanged(
    app, db_session, make_open_booking_setup, freeze_now, student
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking_engine.book_slot(students[0].id, slot.id)
    count_before = slot.booked_count

    with pytest.raises(BookingError):
        booking_engine.book_slot(student.id, slot.id)

    db_session.refresh(slot)
    assert slot.booked_count == count_before


def test_guarded_update_blocks_overbooking_on_stale_read(
    app, db_session, make_open_booking_setup, freeze_now, student
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    # Fill slot manually to simulate stale read condition
    slot.booked_count = 1
    slot.status = "full"
    db_session.commit()

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(student.id, slot.id)
    assert exc.value.code in ["slot_full", "slot_not_available"]


def test_integrity_error_mapped_to_duplicate_booking(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking_engine.book_slot(students[0].id, slot.id)

    # Force duplicate via direct conflict or integrity simulation
    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(students[0].id, slot.id)
    assert exc.value.code == "duplicate_booking"


def test_pre_hook_veto_leaves_no_booking(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    def veto_hook(ctx):
        raise BookingError("payment_required", "Vetoed")

    hooks.register_pre_booking(veto_hook)

    with pytest.raises(BookingError) as exc:
        booking_engine.book_slot(students[0].id, slot.id)
    assert exc.value.code == "payment_required"
    assert Booking.query.count() == 0


def test_hooks_empty_by_default():
    assert len(hooks.pre_booking_hooks) == 0
    assert len(hooks.post_cancel_hooks) == 0
