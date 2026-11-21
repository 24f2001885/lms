"""
FILE PURPOSE: Tests for exam_status.sync_all, maintenance.purge_soft_deleted, and CLI jobs.
"""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import AuditLog, Examination
from app.services import audit_service, booking_engine, exam_status, maintenance


def test_sync_all_completes_past_slots_and_is_idempotent(
    app, db_session, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=2)
    freeze_now(exam.booking_start + timedelta(hours=1))
    booking = booking_engine.book_slot(students[0].id, slot.id)

    after_slot = slot.end_at + timedelta(minutes=5)
    summary1 = exam_status.sync_all(now=after_slot)
    assert summary1["slots_completed"] == 1
    assert summary1["bookings_completed"] == 1

    db_session.refresh(slot)
    db_session.refresh(booking)
    assert slot.status == "completed"
    assert booking.status == "completed"

    # Second run with same clock is idempotent
    summary2 = exam_status.sync_all(now=after_slot)
    assert summary2["slots_completed"] == 0
    assert summary2["bookings_completed"] == 0
    assert summary2["status_changes"] == 0


def test_purge_soft_deleted_rules(app, db_session, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=2)
    now = exam.booking_start + timedelta(hours=1)
    freeze_now(now)

    with pytest.raises(ValueError):
        maintenance.purge_soft_deleted(older_than_days=0)

    exam.is_deleted = True
    exam.updated_at = now - timedelta(days=95)
    db_session.commit()

    purged = maintenance.purge_soft_deleted(older_than_days=90, now=now)
    assert purged == 1
    assert db.session.get(Examination, exam.id) is None
    assert AuditLog.query.filter_by(action=audit_service.SYSTEM_PURGE).count() == 1
    assert maintenance.purge_soft_deleted(older_than_days=90, now=now) == 0
