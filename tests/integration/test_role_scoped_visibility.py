"""
FILE PURPOSE: Proves strict role-scoped data isolation and secret hygiene across pages.
"""

from datetime import timedelta

from app.services import booking_engine


def test_student_pages_do_not_leak_other_students_or_secrets(
    student_client, make_open_booking_setup, freeze_now
):
    client, signed_in_student = student_client
    exam, slot, examiner, other_students = make_open_booking_setup(student_count=2, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    other_students[0].full_name = "DistinctiveOtherStudentXYZ"
    other_students[0].email = "distinctive.other@secret.local"
    booking_engine.book_slot(other_students[0].id, slot.id)

    for url in [
        "/student/dashboard",
        "/student/bookings",
        "/student/history",
        "/student/schedule",
        "/student/results",
    ]:
        resp = client.get(url)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "DistinctiveOtherStudentXYZ" not in body
        assert "distinctive.other@secret.local" not in body
        assert "scrypt:" not in body
        assert "pbkdf2:" not in body
        assert "password_hash" not in body
