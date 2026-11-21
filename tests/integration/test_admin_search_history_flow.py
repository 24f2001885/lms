"""
tests/integration/test_admin_search_history_flow.py - Full Admin Setup Flow Acceptance Test (Design Plan 4.4).
"""

from datetime import datetime

from app.models.audit_log import AuditLog
from app.models.course import Course
from app.models.examination import Examination
from app.models.user import User


def test_admin_setup_flow_end_to_end(admin_client, freeze_now):
    """
    Milestone Acceptance Test: Execute full admin setup workflow:
    1. Create course
    2. Create examination
    3. Add rubric criteria totaling 100%
    4. Register and approve examiner
    5. Assign examiner to examination
    6. Open slot creation switch -> close slot creation
    7. Open booking switch -> close booking
    8. Verify audit history log
    """
    freeze_now(datetime(2030, 1, 1, 12, 0))

    # 1. Create Course
    admin_client.post(
        "/admin/courses",
        data={
            "code": "MAD101",
            "name": "Web Applications",
            "description": "Flask LMS",
            "status": "active",
        },
        follow_redirects=True,
    )
    course = Course.query.filter_by(code="MAD101").first()
    assert course is not None

    # 2. Create Examination
    admin_client.post(
        "/admin/examinations",
        data={
            "course_id": course.id,
            "name": "Midterm Practical",
            "description": "Lab test",
            "exam_type": "practical",
            "duration_minutes": 30,
            "max_marks": 100,
            "slot_creation_start": "2030-01-01T10:00",
            "slot_creation_end": "2030-01-05T18:00",
            "booking_start": "2030-01-05T18:00",
            "booking_end": "2030-01-15T18:00",
            "cancellation_deadline": "2030-01-15T18:00",
        },
        follow_redirects=True,
    )
    exam = Examination.query.filter_by(name="Midterm Practical").first()
    assert exam is not None

    # 3. Add Rubric criteria totaling 100% (60 + 40)
    admin_client.post(
        f"/admin/examinations/{exam.id}/rubrics",
        data={"criterion_name": "Part A", "weightage": "60.00", "max_score": "60.00"},
        follow_redirects=True,
    )
    admin_client.post(
        f"/admin/examinations/{exam.id}/rubrics",
        data={"criterion_name": "Part B", "weightage": "40.00", "max_score": "40.00"},
        follow_redirects=True,
    )
    assert len(exam.rubrics) == 2

    # 4. Create and Approve Examiner
    admin_client.post(
        "/admin/examiners/new",
        data={
            "full_name": "Dr. Smith",
            "email": "smith@faculty.test",
            "department": "Computer Science",
            "temporary_password": "Passw0rdSmith1!",
        },
        follow_redirects=True,
    )
    examiner = User.query.filter_by(email="smith@faculty.test").first()
    assert examiner is not None
    assert examiner.approval_status == "approved"

    # 5. Assign Examiner
    admin_client.post(
        f"/admin/examinations/{exam.id}/examiners",
        data={"examiner_id": examiner.id},
        follow_redirects=True,
    )
    assert len(exam.examiner_links) == 1

    # 6. Open Slot Creation Switch -> Verify status -> Close it
    admin_client.post(
        f"/admin/examinations/{exam.id}/slot-creation/toggle",
        data={"open": "1"},
        follow_redirects=True,
    )
    assert exam.slot_creation_open is True

    admin_client.post(
        f"/admin/examinations/{exam.id}/slot-creation/toggle",
        data={"open": "0"},
        follow_redirects=True,
    )
    assert exam.slot_creation_open is False

    # 7. Open Booking Switch (rubric is 100%, so succeeds) -> Close it
    admin_client.post(
        f"/admin/examinations/{exam.id}/booking/toggle", data={"open": "1"}, follow_redirects=True
    )
    assert exam.booking_open is True

    admin_client.post(
        f"/admin/examinations/{exam.id}/booking/toggle", data={"open": "0"}, follow_redirects=True
    )
    assert exam.booking_open is False

    # 8. Verify Audit Log contains all actions
    audits = AuditLog.query.order_by(AuditLog.id.desc()).all()
    assert len(audits) >= 7
