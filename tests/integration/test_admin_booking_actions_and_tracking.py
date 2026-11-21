"""
FILE PURPOSE: HTTP integration tests for reschedule, admin cancel, admin publish, slot cancel, and tracking.
"""

from datetime import timedelta

from app.extensions import db
from app.models import Evaluation
from app.services import booking_engine


def test_admin_evaluations_tracking_and_publish(admin_client, make_open_booking_setup, freeze_now):
    client = admin_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=2)
    freeze_now(exam.booking_start + timedelta(hours=1))

    booking = booking_engine.book_slot(students[0].id, slot.id)
    ev = Evaluation(
        booking_id=booking.id, examiner_id=examiner.id, total_marks=88, status="submitted"
    )
    db.session.add(ev)
    db.session.commit()

    res = client.get("/admin/evaluations?state=submitted")
    assert res.status_code == 200
    assert students[0].full_name.encode() in res.data

    pub_res = client.post(f"/admin/evaluations/{ev.id}/publish", follow_redirects=True)
    assert pub_res.status_code == 200
    assert b"Evaluation published." in pub_res.data
