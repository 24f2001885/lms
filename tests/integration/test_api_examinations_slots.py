"""
FILE PURPOSE: Integration tests for /api/v1/examinations and /api/v1/slots CRUD and conflict mapping.
"""

from datetime import timedelta

import pytest

from app.models import Course, ExaminationExaminer
from app.services import windows


@pytest.mark.api
def test_admin_examination_crud_and_conflicts(api, db_session):
    admin = api("admin")
    student = api("student")

    course = Course(code="API101", name="API Design", status="active", created_by=admin.user.id)
    db_session.add(course)
    db_session.commit()

    base = windows.now_utc() + timedelta(days=5)
    payload = {
        "course_id": course.id,
        "name": "API Midterm Viva",
        "description": "Oral assessment",
        "exam_type": "viva",
        "duration_minutes": 30,
        "max_marks": 100,
        "slot_creation_start": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "slot_creation_end": (base + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "booking_start": (base + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "booking_end": (base + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    res_create = admin.post("/api/v1/examinations", data=payload)
    assert res_create.status_code == 201
    assert "Location" in res_create.headers
    created_exam = res_create.get_json()
    exam_id = created_exam["id"]

    # Student sees examination
    res_st = student.get(f"/api/v1/examinations/{exam_id}")
    assert res_st.status_code == 200
    assert "is_deleted" not in res_st.get_json()

    # Partial update
    res_put = admin.put(f"/api/v1/examinations/{exam_id}", data={"name": "Updated API Viva"})
    assert res_put.status_code == 200
    assert res_put.get_json()["name"] == "Updated API Viva"

    # Soft delete twice: 204 then 404
    assert admin.delete(f"/api/v1/examinations/{exam_id}").status_code == 204
    assert admin.delete(f"/api/v1/examinations/{exam_id}").status_code == 404


@pytest.mark.api
def test_examiner_slot_crud_and_ownership_isolation(
    api, db_session, make_open_booking_setup, freeze_now
):
    exam, existing_slot, examiner1, _ = make_open_booking_setup(student_count=1, capacity=2)
    exam.slot_creation_open = True
    exam.booking_open = False
    db_session.commit()
    freeze_now(exam.slot_creation_start + timedelta(hours=1))

    ex1 = api("examiner")
    ex2 = api("examiner")
    db_session.add(
        ExaminationExaminer(
            examination_id=exam.id,
            examiner_id=ex1.user.id,
            assigned_by=1,
            assigned_at=exam.slot_creation_start,
        )
    )
    db_session.commit()

    start_dt = exam.booking_end + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=1)
    res_c = ex1.post(
        "/api/v1/slots",
        data={
            "examination_id": exam.id,
            "start_at": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_at": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "max_capacity": 4,
        },
    )
    assert res_c.status_code == 201
    slot_id = res_c.get_json()["id"]

    # Another examiner gets 404 (not 403)
    assert ex2.get(f"/api/v1/slots/{slot_id}").status_code == 404
    assert ex2.put(f"/api/v1/slots/{slot_id}", data={"max_capacity": 6}).status_code == 404
    assert ex2.delete(f"/api/v1/slots/{slot_id}").status_code == 404

    # Owner updates and deletes
    assert ex1.put(f"/api/v1/slots/{slot_id}", data={"max_capacity": 6}).status_code == 200
    assert ex1.delete(f"/api/v1/slots/{slot_id}").status_code == 204
