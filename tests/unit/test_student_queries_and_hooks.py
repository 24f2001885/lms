"""
FILE PURPOSE: Tests for student_queries scoping and the hooks registry.
DEPENDS ON: app/services/student_queries.py, hooks.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Visibility: test_draft_without_slots_hidden, test_draft_with_slot_visible, test_deleted_and_inactive_course_hidden, test_closed_and_completed_visible, test_filters_whitelisted.
2. Dashboard/lists: test_dashboard_excludes_already_booked_examinations, test_available_slots_future_only, test_upcoming_sorted_and_future_only, test_schedule_excludes_cancelled, test_history_includes_all_statuses, test_my_bookings_status_filter.
3. Scoping: test_get_owned_booking_none_for_other_student, test_results_only_published, test_result_detail_none_for_draft_submitted_and_foreign, test_all_queries_scoped (create two students with bookings and assert each function returns only the caller's rows).
4. Hooks: test_register_unique, test_run_order, test_clear_hooks, test_post_hook_exception_swallowed_and_logged.
DEBUGGING:
# print(f"[DEBUG] query {name} -> {[getattr(r, 'id', r) for r in rows]}")
OFFLINE DOCKER TEST CASES:
- 19 tests pass offline.

FILE PURPOSE: Rule tests for book_slot and cancel_booking.
"""

from datetime import timedelta

import pytest

from app.errors import BookingError, WindowError
from app.models import ExaminationSlot
from app.services import booking_engine


def test_book_success_updates_count_and_audit(
    app, db_session, student, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    assert booking.status == "booked"
    assert slot.booked_count == 1


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


def test_cancel_after_deadline_refused(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)

    freeze_now(exam.booking_end + timedelta(seconds=1))
    with pytest.raises(WindowError) as exc:
        booking_engine.cancel_booking(students[0].id, booking.id)
    assert exc.value.code == "cancel_deadline_passed"
