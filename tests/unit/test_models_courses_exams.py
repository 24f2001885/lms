from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

from app.extensions import db
from app.models import Course, Examination, ExaminationExaminer, ExaminationRubric


def test_course_code_unique(app, make_course):
    """Verify course code uniqueness."""
    make_course(code="CS101")
    course2 = Course(code="CS101", name="Second CS101", created_by=1)
    db.session.add(course2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_course_status_check(app, make_admin):
    """Verify course status check constraint."""
    admin = make_admin()
    course = Course(code="CS102", name="Intro", status="archived", created_by=admin.id)
    db.session.add(course)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_course_delete_with_exam_restricted(app, make_examination):
    """Verify ondelete='RESTRICT' prevents deleting course with exams."""
    exam = make_examination()
    course = exam.course
    db.session.delete(course)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_exam_duration_positive(app, make_course):
    """Verify duration_minutes must be > 0."""
    course = make_course()
    with pytest.raises(IntegrityError):
        exam = Examination(
            course_id=course.id,
            name="Zero Duration",
            exam_type="viva",
            duration_minutes=0,
            max_marks=100,
            slot_creation_start=datetime(2030, 1, 1),
            slot_creation_end=datetime(2030, 1, 5),
            booking_start=datetime(2030, 1, 5),
            booking_end=datetime(2030, 1, 10),
            cancellation_deadline=datetime(2030, 1, 10),
        )
        db.session.add(exam)
        db.session.commit()
    db.session.rollback()


def test_exam_creation_window_order(app, make_course):
    """Verify slot_creation_start must be strictly earlier than slot_creation_end."""
    course = make_course()
    with pytest.raises(IntegrityError):
        exam = Examination(
            course_id=course.id,
            name="Bad Window",
            exam_type="viva",
            duration_minutes=30,
            max_marks=100,
            slot_creation_start=datetime(2030, 1, 10),
            slot_creation_end=datetime(2030, 1, 5),  # End earlier than start
            booking_start=datetime(2030, 1, 15),
            booking_end=datetime(2030, 1, 20),
            cancellation_deadline=datetime(2030, 1, 20),
        )
        db.session.add(exam)
        db.session.commit()
    db.session.rollback()


def test_exam_windows_may_touch(app, make_course):
    """Verify slot_creation_end == booking_start is accepted (they may touch)."""
    course = make_course()
    touch_date = datetime(2030, 1, 10, 0, 0, 0)
    exam = Examination(
        course_id=course.id,
        name="Touching Windows",
        exam_type="viva",
        duration_minutes=30,
        max_marks=100,
        slot_creation_start=datetime(2030, 1, 1),
        slot_creation_end=touch_date,
        booking_start=touch_date,  # Exactly touching
        booking_end=datetime(2030, 1, 20),
        cancellation_deadline=datetime(2030, 1, 20),
    )
    db.session.add(exam)
    db.session.commit()  # Must not raise IntegrityError
    assert exam.id is not None


def test_rubric_unique_name_per_exam(app, make_examination, make_rubric):
    """Verify duplicate criterion name in the same exam is rejected."""
    exam = make_examination()
    make_rubric(exam, name="Code Quality")

    with pytest.raises(IntegrityError):
        rubric2 = ExaminationRubric(
            examination_id=exam.id,
            criterion_name="Code Quality",  # Duplicate name
            weightage=20.0,
            max_score=20.0,
        )
        db.session.add(rubric2)
        db.session.commit()
    db.session.rollback()


def test_rubric_same_name_other_exam_ok(app, make_examination, make_rubric):
    """Verify same criterion name in a different exam is permitted."""
    exam1 = make_examination()
    exam2 = make_examination()

    r1 = make_rubric(exam1, name="Presentation")
    r2 = make_rubric(exam2, name="Presentation")  # Allowed across different exams
    assert r1.id != r2.id


def test_examiner_assignment_unique(app, make_examination, make_examiner, make_admin):
    """Verify an examiner cannot be assigned twice to the same examination."""
    exam = make_examination()
    examiner = make_examiner()
    admin = make_admin()

    a1 = ExaminationExaminer(examination_id=exam.id, examiner_id=examiner.id, assigned_by=admin.id)
    db.session.add(a1)
    db.session.commit()

    a2 = ExaminationExaminer(examination_id=exam.id, examiner_id=examiner.id, assigned_by=admin.id)
    db.session.add(a2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_mapper_configuration_ok(app):
    """Verify configure_mappers raises no ambiguous foreign key errors."""
    configure_mappers()
