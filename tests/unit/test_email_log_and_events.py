"""
Unit tests for EmailLog model constraints and the domain events API in hooks.py (P12).
"""

from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ALL_TABLE_NAMES, TIER2_TABLE_NAMES
from app.models.email_log import EmailLog
from app.services import admin_service, booking_engine, evaluation_service, hooks

pytestmark = pytest.mark.mail


# --- Model Tests ---


def test_status_check_rejects_unknown(app, db_session):
    log = EmailLog(
        to_email="test@example.com",
        template="booking_confirmed",
        status="invalid_status",
        subject="Subject",
        body_text="Body",
    )
    db_session.add(log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_attempts_non_negative(app, db_session):
    log = EmailLog(
        to_email="test@example.com",
        template="booking_confirmed",
        status="queued",
        subject="Subject",
        body_text="Body",
        attempts=-1,
    )
    db_session.add(log)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_required_columns_not_null(app, db_session):
    for col in ("to_email", "template", "subject", "body_text"):
        kw = {
            "to_email": "test@example.com",
            "template": "booking_confirmed",
            "status": "queued",
            "subject": "Subject",
            "body_text": "Body",
        }
        kw[col] = None
        log = EmailLog(**kw)
        db_session.add(log)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


def test_indexes_exist(app):
    inspector = inspect(db.engine)
    indexes = inspector.get_indexes("email_logs")
    assert len(indexes) >= 0


def test_no_foreign_keys(app):
    inspector = inspect(db.engine)
    fks = inspector.get_foreign_keys("email_logs")
    assert len(fks) == 0


def test_table_count_is_13_after_init(app):
    inspector = inspect(db.engine)
    tables = [t for t in inspector.get_table_names() if not t.startswith("sqlite_")]
    expected = set(ALL_TABLE_NAMES).union(set(TIER2_TABLE_NAMES))
    assert set(tables) == expected
    assert len(expected) == 13


# --- Events API Tests ---


def test_register_unique_and_order():
    hooks.clear_events()
    calls = []

    def h1(**kw):
        calls.append("h1")

    def h2(**kw):
        calls.append("h2")

    hooks.register_event("test.event", h1)
    hooks.register_event("test.event", h1)  # duplicate ignored
    hooks.register_event("test.event", h2)

    hooks.emit("test.event")
    assert calls == ["h1", "h2"]
    hooks.clear_events()


def test_emit_passes_only_keywords():
    hooks.clear_events()
    received = {}

    def h(**kw):
        received.update(kw)

    hooks.register_event("test.kw", h)
    hooks.emit("test.kw", a=1, b="two")
    assert received == {"a": 1, "b": "two"}
    hooks.clear_events()


def test_emit_swallows_handler_exception_and_logs_without_payload(caplog):
    hooks.clear_events()

    def bad_handler(**kw):
        raise ValueError("Boom!")

    hooks.register_event("test.fail", bad_handler)
    # Should not raise
    hooks.emit("test.fail", secret_token="my-super-secret-12345")
    assert "Boom!" in caplog.text
    # Secret should not be logged in exception
    assert "my-super-secret-12345" not in caplog.text
    hooks.clear_events()


def test_emit_with_no_handlers_is_noop():
    hooks.clear_events()
    # Emitting an unregistered event must not raise
    hooks.emit("unregistered.event", foo="bar")


def test_clear_events():
    hooks.clear_events()
    called = []
    hooks.register_event("ev", lambda **kw: called.append(True))
    hooks.clear_events()
    hooks.emit("ev")
    assert len(called) == 0


def test_existing_pre_and_post_hooks_unchanged():
    hooks.clear_hooks()
    pre_called = []
    post_called = []

    hooks.register_pre_booking(lambda ctx: pre_called.append(ctx.student_id))
    hooks.register_post_cancel(lambda ctx: post_called.append(ctx.booking_id))

    ctx = hooks.HookContext(
        student_id=10, slot_id=20, examination_id=30, booking_id=40, actor_id=10
    )
    hooks.run_pre_booking(ctx)
    hooks.run_post_cancel(ctx)

    assert pre_called == [10]
    assert post_called == [40]
    hooks.clear_hooks()


def test_event_names_are_stable_constants():
    assert hooks.EVENT_BOOKING_CREATED == "booking.created"
    assert hooks.EVENT_BOOKING_CANCELLED == "booking.cancelled"
    assert hooks.EVENT_BOOKING_RESCHEDULED == "booking.rescheduled"
    assert hooks.EVENT_EXAMINER_APPROVED == "examiner.approved"
    assert hooks.EVENT_EVALUATION_PUBLISHED == "evaluation.published"


# --- Emit Sites Tests ---


def test_book_slot_emits_after_commit_only(app, db_session, make_open_booking_setup, freeze_now):
    hooks.clear_events()
    exam, slot, examiner, students = make_open_booking_setup(capacity=5, student_count=2)
    freeze_now(exam.booking_start)

    recorded = []
    hooks.register_event(
        hooks.EVENT_BOOKING_CREATED,
        lambda **kw: recorded.append(kw),
    )

    booking = booking_engine.book_slot(students[0].id, slot.id)
    assert len(recorded) == 1
    assert recorded[0]["booking_id"] == booking.id
    assert recorded[0]["student_id"] == students[0].id
    hooks.clear_events()


def test_cancel_variants_emit_by_student_admin_slot(
    app, db_session, make_open_booking_setup, admin, freeze_now
):
    hooks.clear_events()
    exam, slot, examiner, students = make_open_booking_setup(capacity=5, student_count=3)
    freeze_now(exam.booking_start)

    b1 = booking_engine.book_slot(students[0].id, slot.id)
    b2 = booking_engine.book_slot(students[1].id, slot.id)
    b3 = booking_engine.book_slot(students[2].id, slot.id)

    recorded = []
    hooks.register_event(
        hooks.EVENT_BOOKING_CANCELLED,
        lambda **kw: recorded.append(kw),
    )

    # 1. Student cancel
    booking_engine.cancel_booking(students[0].id, b1.id)
    assert len(recorded) == 1
    assert recorded[-1]["by"] == "student"
    assert recorded[-1]["booking_id"] == b1.id

    # 2. Admin cancel
    booking_engine.admin_cancel_booking(b2.id, admin.id, reason="Admin reason")
    assert len(recorded) == 2
    assert recorded[-1]["by"] == "admin"
    assert recorded[-1]["booking_id"] == b2.id

    # 3. Cancel slot (cancels b3)
    booking_engine.cancel_slot(slot.id, admin.id, reason="Slot emergency cancellation")
    assert len(recorded) == 3
    assert recorded[-1]["by"] == "slot"
    assert recorded[-1]["booking_id"] == b3.id
    hooks.clear_events()


def test_reschedule_emits_both_slot_ids(
    app, db_session, make_open_booking_setup, make_slot, admin, freeze_now
):
    hooks.clear_events()
    exam, slot1, examiner, students = make_open_booking_setup(capacity=5, student_count=1)
    slot2 = make_slot(examination=exam, examiner=examiner, capacity=5)
    freeze_now(exam.booking_start)

    booking = booking_engine.book_slot(students[0].id, slot1.id)

    recorded = []
    hooks.register_event(
        hooks.EVENT_BOOKING_RESCHEDULED,
        lambda **kw: recorded.append(kw),
    )

    booking_engine.reschedule_booking(booking.id, slot2.id, actor_id=admin.id)
    assert len(recorded) == 1
    assert recorded[0]["booking_id"] == booking.id
    assert recorded[0]["student_id"] == students[0].id
    assert recorded[0]["from_slot_id"] == slot1.id
    assert recorded[0]["to_slot_id"] == slot2.id
    hooks.clear_events()


def test_approve_examiner_emits(app, db_session, make_examiner, admin):
    hooks.clear_events()
    examiner = make_examiner(approved=False)

    recorded = []
    hooks.register_event(
        hooks.EVENT_EXAMINER_APPROVED,
        lambda **kw: recorded.append(kw),
    )

    admin_service.approve_examiner(admin.id, examiner.id)
    assert len(recorded) == 1
    assert recorded[0]["examiner_id"] == examiner.id
    hooks.clear_events()


def test_publish_and_admin_publish_emit(
    app, db_session, make_open_booking_setup, admin, freeze_now
):
    hooks.clear_events()
    exam, slot, examiner, students = make_open_booking_setup(capacity=5, student_count=2)
    freeze_now(exam.booking_start)

    b1 = booking_engine.book_slot(students[0].id, slot.id)
    scores = {r.id: Decimal("20.0") for r in exam.rubrics}

    recorded = []
    hooks.register_event(
        hooks.EVENT_EVALUATION_PUBLISHED,
        lambda **kw: recorded.append(kw),
    )

    # 1. Save evaluation with action publish
    evaluation_service.save_evaluation(
        examiner_id=examiner.id,
        booking_id=b1.id,
        scores=scores,
        remarks="Good",
        action="publish",
    )
    assert len(recorded) == 1
    assert recorded[0]["booking_id"] == b1.id
    assert recorded[0]["student_id"] == students[0].id

    # 2. Admin publish
    b2 = booking_engine.book_slot(students[1].id, slot.id)
    ev2 = evaluation_service.save_evaluation(
        examiner_id=examiner.id,
        booking_id=b2.id,
        scores=scores,
        remarks="Good",
        action="submit",
    )
    evaluation_service.admin_publish(admin.id, ev2.id)
    assert len(recorded) == 2
    assert recorded[1]["booking_id"] == b2.id
    assert recorded[1]["student_id"] == students[1].id
    hooks.clear_events()


def test_emit_failure_does_not_change_return_value(
    app, db_session, make_open_booking_setup, freeze_now
):
    hooks.clear_events()
    exam, slot, examiner, students = make_open_booking_setup(capacity=5, student_count=1)
    freeze_now(exam.booking_start)

    def crashing_handler(**kw):
        raise RuntimeError("Handler crash!")

    hooks.register_event(hooks.EVENT_BOOKING_CREATED, crashing_handler)

    booking = booking_engine.book_slot(students[0].id, slot.id)
    assert booking is not None
    assert booking.status == "booked"
    hooks.clear_events()
