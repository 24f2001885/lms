"""
FILE PURPOSE: Tests for booking_timeline role-based redaction and student examination history.
"""
from datetime import timedelta

from app.services import booking_engine, history_service


def test_timeline_redaction_by_role(app, db_session, admin, student, make_open_booking_setup, freeze_now):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=2)
    freeze_now(exam.booking_start + timedelta(hours=1))

    owner_student = students[0]
    booking = booking_engine.book_slot(owner_student.id, slot.id)
    booking_engine.admin_cancel_booking(booking.id, admin.id, "Internal administrative audit reason")

    # Foreign student gets None
    assert history_service.booking_timeline(booking.id, "student", student.id) is None

    # Owner student sees redacted timeline without internal reason
    st_timeline = history_service.booking_timeline(booking.id, "student", owner_student.id)
    assert len(st_timeline) == 2
    assert "Internal administrative audit reason" not in str(st_timeline)
    assert st_timeline[1]["detail"] == "Cancelled by the administration"

    # Admin sees full reason
    adm_timeline = history_service.booking_timeline(booking.id, "admin", admin.id)
    assert "Internal administrative audit reason" in adm_timeline[1]["detail"]
