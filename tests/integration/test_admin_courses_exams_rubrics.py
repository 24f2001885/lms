"""
tests/integration/test_admin_courses_exams_rubrics.py - HTTP integration tests for ADM-01 to ADM-08.
"""

from app.models.course import Course


def test_dashboard_six_totals_values(admin_client, make_course, make_examination, make_student):
    c = make_course(code="CS8001")
    make_examination(course=c)
    make_student()

    res = admin_client.get("/admin/dashboard")
    assert res.status_code == 200
    assert b"Dashboard" in res.data
    for label in (b"Courses", b"Examinations", b"Examiners", b"Students", b"Slots", b"Bookings"):
        assert label in res.data
    assert b">1<" in res.data


def test_course_create_edit_delete_flow(admin_client):
    # 1. Create
    res = admin_client.post(
        "/admin/courses",
        data={
            "code": "CS7001",
            "name": "Software Engineering",
            "description": "Agile & DevOps",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    course = Course.query.filter_by(code="CS7001").first()
    assert course is not None

    # 2. Edit
    edit_res = admin_client.post(
        f"/admin/courses/{course.id}/update",
        data={
            "code": "CS7001",
            "name": "Advanced Software Engineering",
            "description": "DevOps",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert edit_res.status_code == 302
    assert course.name == "Advanced Software Engineering"

    # 3. Delete
    del_res = admin_client.post(f"/admin/courses/{course.id}/delete", follow_redirects=False)
    assert del_res.status_code == 302
    assert Course.query.filter_by(code="CS7001").first() is None


def test_rubric_over_100_flash(admin_client, make_examination, make_rubric):
    exam = make_examination()
    make_rubric(exam, name="Viva Part 1", weightage=70.0)

    res = admin_client.post(
        f"/admin/examinations/{exam.id}/rubrics",
        data={"criterion_name": "Viva Part 2", "weightage": "40.00", "max_score": "40.00"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"exceed 100%" in res.data
