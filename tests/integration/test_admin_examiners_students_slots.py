"""
tests/integration/test_admin_examiners_students_slots.py - Tests for examiner/student management, slots, and bookings.
"""

from app.extensions import db


def test_pending_filter_and_approve(admin_client, make_examiner):
    examiner = make_examiner(approved=False)
    res = admin_client.get("/admin/examiners?status=pending")
    assert res.status_code == 200
    assert examiner.full_name.encode() in res.data

    # Approve
    app_res = admin_client.post(f"/admin/examiners/{examiner.id}/approve", follow_redirects=True)
    assert app_res.status_code == 200
    assert examiner.approval_status == "approved"


def test_students_search_by_roll_number(admin_client, make_student):
    student = make_student(full_name="RollStudent")
    student.student_profile.roll_number = "ROLL9999"
    db.session.commit()

    res = admin_client.get("/admin/students?q=ROLL9999")
    assert res.status_code == 200
    assert b"RollStudent" in res.data


def test_booking_detail_no_action_buttons_in_p3(
    admin_client, make_examination, make_examiner, make_student, make_slot, make_booking
):
    exam = make_examination()
    examiner = make_examiner()
    student = make_student()
    slot = make_slot(exam, examiner)
    booking = make_booking(student, slot)

    res = admin_client.get(f"/admin/bookings/{booking.id}")
    assert res.status_code == 200
    assert booking.student.full_name.encode() in res.data
    # Reschedule button belongs to P6 and must NOT be in P3
    assert b"reschedule" not in res.data.lower()
