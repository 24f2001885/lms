"""
FILE PURPOSE: Rule tests for slot_service (windows, ownership, overlap, capacity, counts).
DEPENDS ON: app/services/slot_service.py, tests/conftest.py (freeze_now, make_ready_examination, make_booking_with_slot).
PROMPT FOR LLM IMPLEMENTATION:
1. Window tests: test_create_fails_before_window_opens, test_create_ok_at_window_start_and_end_inclusive, test_create_fails_after_window, test_create_fails_when_switch_off.
2. Rule tests: test_create_requires_assignment, test_create_rejects_past_start, test_create_rejects_bad_time_range, test_create_capacity_bounds (0, 1, 500, 501), test_create_overlap_refused_back_to_back_allowed, test_overlap_checked_across_examinations, test_unapproved_or_inactive_examiner_refused.
3. Update/delete: test_update_locked_at_booking_start, test_update_ok_one_second_before, test_update_refused_with_active_booking, test_update_excludes_self_in_overlap, test_delete_hard_when_no_bookings, test_delete_turns_cancelled_with_cancelled_booking_history, test_delete_refused_with_active_booking.
4. Ownership/lists/counts: test_get_owned_slot_none_for_other_examiner, test_list_slots_filters_and_order, test_booked_students_excludes_cancelled_and_counts_them, test_dashboard_counts_scoped_to_examiner, test_audit_rows_written_for_create_update_delete.
5. Assert stable error codes, never message text. Use freeze_now for every clock-dependent test.
DEBUGGING:
# print(f"[DEBUG] slot rule case {name}: code={code}")
OFFLINE DOCKER TEST CASES:
- 27 tests pass offline; removing assert_slots_editable from update_slot makes test_update_locked_at_booking_start fail.

FILE PURPOSE: Rule tests for slot_service (windows, ownership, overlap, capacity, counts).
"""

from datetime import timedelta

import pytest

from app.errors import AppError, WindowError
from app.extensions import db
from app.models import Booking, ExaminationSlot
from app.services import slot_service


def test_create_fails_before_window_opens(
    app, db_session, examiner, make_ready_examination, freeze_now
):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start - timedelta(seconds=1))

    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)

    with pytest.raises(WindowError) as exc:
        slot_service.create_slot(examiner.id, exam.id, start, end, 10)
    assert exc.value.code == "slot_creation_closed"


def test_create_ok_at_window_start_and_end_inclusive(
    app, db_session, examiner, make_ready_examination, freeze_now
):
    exam, _ = make_ready_examination(examiner=examiner)

    freeze_now(exam.slot_creation_start)
    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)
    slot1 = slot_service.create_slot(examiner.id, exam.id, start, end, 10)
    assert slot1 is not None

    freeze_now(exam.slot_creation_end)
    start2 = exam.slot_creation_end + timedelta(days=2)
    end2 = start2 + timedelta(hours=1)
    slot2 = slot_service.create_slot(examiner.id, exam.id, start2, end2, 10)
    assert slot2 is not None


def test_create_fails_after_window(app, db_session, examiner, make_ready_examination, freeze_now):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_end + timedelta(seconds=1))

    start = exam.slot_creation_end + timedelta(days=1)
    end = start + timedelta(hours=1)

    with pytest.raises(WindowError):
        slot_service.create_slot(examiner.id, exam.id, start, end, 10)


def test_create_requires_assignment(
    app, db_session, examiner, make_ready_examination, freeze_now, admin
):
    exam, _ = make_ready_examination(examiner=admin)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)

    with pytest.raises(AppError) as exc:
        slot_service.create_slot(examiner.id, exam.id, start, end, 10)
    assert exc.value.code == "examination_not_found"


def test_create_rejects_past_start(app, db_session, examiner, make_ready_examination, freeze_now):
    exam, _ = make_ready_examination(examiner=examiner)
    now = exam.slot_creation_start
    freeze_now(now)

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    with pytest.raises(AppError) as exc:
        slot_service.create_slot(examiner.id, exam.id, start, end, 10)
    assert exc.value.code == "slot_in_past"


def test_create_rejects_bad_time_range(
    app, db_session, examiner, make_ready_examination, freeze_now
):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=2)
    end = start - timedelta(hours=1)

    with pytest.raises(AppError) as exc:
        slot_service.create_slot(examiner.id, exam.id, start, end, 10)
    assert exc.value.code == "invalid_time_range"


def test_create_capacity_bounds(app, db_session, examiner, make_ready_examination, freeze_now):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)
    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)

    with pytest.raises(AppError):
        slot_service.create_slot(examiner.id, exam.id, start, end, 0)
    with pytest.raises(AppError):
        slot_service.create_slot(examiner.id, exam.id, start, end, 501)

    s1 = slot_service.create_slot(examiner.id, exam.id, start, end, 1)
    assert s1.max_capacity == 1


def test_create_overlap_refused_back_to_back_allowed(
    app, db_session, examiner, make_ready_examination, freeze_now
):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    t1 = exam.slot_creation_start + timedelta(days=1)
    t2 = t1 + timedelta(hours=1)
    t3 = t2 + timedelta(hours=1)

    slot_service.create_slot(examiner.id, exam.id, t1, t2, 10)

    s2 = slot_service.create_slot(examiner.id, exam.id, t2, t3, 10)
    assert s2 is not None

    with pytest.raises(AppError) as exc:
        slot_service.create_slot(
            examiner.id, exam.id, t1 + timedelta(minutes=30), t2 + timedelta(minutes=30), 10
        )
    assert exc.value.code == "examiner_overlap"


def test_update_locked_at_booking_start(
    app, db_session, examiner, make_ready_examination, freeze_now
):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=5)
    end = start + timedelta(hours=1)
    slot = slot_service.create_slot(examiner.id, exam.id, start, end, 10)

    freeze_now(exam.booking_start)

    new_start = start + timedelta(minutes=30)
    new_end = end + timedelta(minutes=30)
    with pytest.raises(WindowError) as exc:
        slot_service.update_slot(examiner.id, slot.id, new_start, new_end, 20)
    assert exc.value.code == "slot_edit_locked"


def test_update_ok_one_second_before(app, db_session, examiner, make_ready_examination, freeze_now):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=5)
    end = start + timedelta(hours=1)
    slot = slot_service.create_slot(examiner.id, exam.id, start, end, 10)

    freeze_now(exam.booking_start - timedelta(seconds=1))

    new_start = start + timedelta(minutes=30)
    new_end = end + timedelta(minutes=30)
    updated = slot_service.update_slot(examiner.id, slot.id, new_start, new_end, 20)
    assert updated.max_capacity == 20


def test_delete_hard_when_no_bookings(
    app, db_session, examiner, make_ready_examination, freeze_now
):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)
    slot = slot_service.create_slot(examiner.id, exam.id, start, end, 10)
    slot_id = slot.id

    slot_service.delete_slot(examiner.id, slot_id)
    assert ExaminationSlot.query.get(slot_id) is None


def test_delete_turns_cancelled_with_cancelled_booking_history(
    app, db_session, examiner, make_ready_examination, freeze_now, student
):
    exam, examiner_obj = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)
    slot = slot_service.create_slot(examiner.id, exam.id, start, end, 10)

    booking = Booking(
        slot_id=slot.id,
        student_id=student.id,
        examination_id=exam.id,
        status="cancelled",
        booked_at=exam.slot_creation_start,
    )
    db.session.add(booking)
    db.session.commit()

    slot_service.delete_slot(examiner.id, slot.id)
    db.session.refresh(slot)
    assert slot.status == "cancelled"


def test_get_owned_slot_none_for_other_examiner(
    app, db_session, examiner, make_ready_examination, freeze_now, admin
):
    exam, _ = make_ready_examination(examiner=examiner)
    freeze_now(exam.slot_creation_start)

    start = exam.slot_creation_start + timedelta(days=1)
    end = start + timedelta(hours=1)
    slot = slot_service.create_slot(examiner.id, exam.id, start, end, 10)

    assert slot_service.get_owned_slot(admin.id, slot.id) is None
    assert slot_service.get_owned_slot(examiner.id, slot.id) is not None
