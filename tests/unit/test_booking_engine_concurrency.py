"""
FILE PURPOSE: Concurrency acceptance tests for booking_engine (Gate A, TDR 10).
"""
from datetime import timedelta

import pytest

from app.errors import BookingError, WindowError
from app.extensions import db, write_lock_enabled
from app.models import Booking, ExaminationSlot
from app.services import booking_engine
from tests.conftest_p6_additions import run_in_threads


def _assert_slot_invariants(session):
    slots = session.query(ExaminationSlot).all()
    for slot in slots:
        active_bookings = (
            session.query(Booking)
            .filter(
                Booking.slot_id == slot.id,
                Booking.status.in_(["booked", "completed"]),
            )
            .count()
        )
        assert 0 <= slot.booked_count <= slot.max_capacity
        assert slot.booked_count == active_bookings
        if slot.status in ("available", "full"):
            if slot.booked_count == slot.max_capacity:
                assert slot.status == "full"
            else:
                assert slot.status == "available"


@pytest.mark.concurrency
def test_write_lock_listener_attached(app):
    with app.app_context():
        assert write_lock_enabled() is True
        timeout = db.session.execute(db.text("PRAGMA busy_timeout")).scalar()
        assert timeout == 5000


@pytest.mark.concurrency
@pytest.mark.parametrize("round_num", [1, 2, 3])
def test_twenty_students_five_seats(app, db_session, make_open_booking_setup, freeze_now, round_num):
    exam, slot, examiner, students = make_open_booking_setup(student_count=20, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    slot_id = slot.id
    student_ids = [s.id for s in students]

    tasks = [lambda sid=sid: booking_engine.book_slot(sid, slot_id) for sid in student_ids]
    results = run_in_threads(app, tasks, barrier=True)

    successes = [r for r in results if isinstance(r, Booking)]
    slot_full_errors = [
        r for r in results if isinstance(r, BookingError) and r.code == "slot_full"
    ]
    other_errors = [
        r for r in results if not isinstance(r, Booking) and not (isinstance(r, BookingError) and r.code == "slot_full")
    ]

    assert len(other_errors) == 0
    assert len(successes) == 5
    assert len(slot_full_errors) == 15

    db_session.expire_all()
    refreshed_slot = db.session.get(ExaminationSlot, slot_id)
    assert refreshed_slot.booked_count == 5
    assert refreshed_slot.status == "full"
    _assert_slot_invariants(db_session)


@pytest.mark.concurrency
@pytest.mark.parametrize("round_num", [1, 2, 3])
def test_same_student_many_threads(app, db_session, make_open_booking_setup, freeze_now, round_num):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    student_id = students[0].id
    slot_id = slot.id

    tasks = [lambda: booking_engine.book_slot(student_id, slot_id) for _ in range(10)]
    results = run_in_threads(app, tasks, barrier=True)

    successes = [r for r in results if isinstance(r, Booking)]
    dup_errors = [
        r for r in results if isinstance(r, BookingError) and r.code == "duplicate_booking"
    ]

    assert len(successes) == 1
    assert len(dup_errors) == 9
    _assert_slot_invariants(db_session)


@pytest.mark.concurrency
@pytest.mark.parametrize("round_num", [1, 2, 3])
def test_cancel_and_book_race(app, db_session, make_open_booking_setup, freeze_now, round_num):
    exam, slot, examiner, students = make_open_booking_setup(student_count=15, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    initial_bookings = []
    for idx in range(5):
        initial_bookings.append(booking_engine.book_slot(students[idx].id, slot.id))

    slot_id = slot.id
    cancel_tasks = [
        lambda sid=students[idx].id, bid=initial_bookings[idx].id: booking_engine.cancel_booking(sid, bid)
        for idx in range(5)
    ]
    book_tasks = [
        lambda sid=students[idx].id: booking_engine.book_slot(sid, slot_id)
        for idx in range(5, 15)
    ]

    results = run_in_threads(app, cancel_tasks + book_tasks, barrier=True)
    unexpected = [
        r for r in results if isinstance(r, Exception) and not isinstance(r, BookingError)
    ]
    assert len(unexpected) == 0

    db_session.expire_all()
    _assert_slot_invariants(db_session)


@pytest.mark.concurrency
def test_booking_close_boundary_race(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=6, capacity=3)

    # 1 second after booking_end -> all must fail with booking_closed
    freeze_now(exam.booking_end + timedelta(seconds=1))
    slot_id = slot.id
    tasks = [lambda sid=s.id, sl_id=slot_id: booking_engine.book_slot(sid, sl_id) for s in students]
    results = run_in_threads(app, tasks, barrier=True)

    assert all(isinstance(r, BookingError | WindowError) and r.code == "booking_closed" for r in results)
    db_session.expire_all()
    assert db.session.get(ExaminationSlot, slot_id).booked_count == 0
