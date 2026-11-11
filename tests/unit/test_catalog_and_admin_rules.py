"""
tests/unit/test_catalog_and_admin_rules.py - Service-level unit tests for catalog and admin rules.
"""

from decimal import Decimal

import pytest

from app.errors import AppError
from app.services import admin_service, catalog_service


def test_course_code_uppercased_and_unique(app, make_admin):
    admin = make_admin()
    c1 = catalog_service.create_course(admin.id, "cs100", "Course 100", None)
    assert c1.code == "CS100"

    with pytest.raises(AppError) as exc:
        catalog_service.create_course(admin.id, "CS100", "Duplicate", None)
    assert exc.value.code == "duplicate_course_code"


def test_delete_course_blocked_when_in_use(app, make_admin, make_examination):
    admin = make_admin()
    exam = make_examination()
    with pytest.raises(AppError) as exc:
        catalog_service.delete_course(admin.id, exam.course_id)
    assert exc.value.code == "course_in_use"


def test_toggle_slot_creation_needs_approved_examiner(app, make_admin, make_examination):
    admin = make_admin()
    exam = make_examination()

    with pytest.raises(AppError) as exc:
        catalog_service.toggle_slot_creation(admin.id, exam.id, open_state=True)
    assert exc.value.code == "no_examiner_assigned"


def test_toggle_booking_needs_rubric_total_100(app, make_admin, make_examination, make_rubric):
    admin = make_admin()
    exam = make_examination()
    make_rubric(exam, name="Criterion 1", weightage=60.0)
    make_rubric(exam, name="Criterion 2", weightage=30.0)  # Total 90%

    with pytest.raises(AppError) as exc:
        catalog_service.toggle_booking(admin.id, exam.id, open_state=True)
    assert exc.value.code == "rubric_total_not_100"


def test_closing_switches_has_no_preconditions(app, make_admin, make_examination):
    admin = make_admin()
    exam = make_examination()
    # Can freely close even with zero rubrics or examiners
    exam_closed = catalog_service.toggle_booking(admin.id, exam.id, open_state=False)
    assert exam_closed.booking_open is False


def test_rubric_over_100_rejected(app, make_admin, make_examination, make_rubric):
    admin = make_admin()
    exam = make_examination()
    make_rubric(exam, name="Part 1", weightage=80.0)

    with pytest.raises(AppError) as exc:
        catalog_service.add_rubric(admin.id, exam.id, "Part 2", None, Decimal("30.00"), Decimal("30.00"))
    assert exc.value.code == "weightage_over_100"


def test_approve_reject_deactivate_activate_cycle(app, make_admin, make_examiner):
    admin = make_admin()
    examiner = make_examiner(approved=False)
    assert examiner.approval_status == "pending"

    # 1. Approve
    admin_service.approve_examiner(admin.id, examiner.id)
    assert examiner.approval_status == "approved"

    # 2. Deactivate
    admin_service.deactivate_user(admin.id, examiner.id)
    assert examiner.is_active is False

    # 3. Activate
    admin_service.activate_user(admin.id, examiner.id)
    assert examiner.is_active is True


def test_cannot_deactivate_self(app, make_admin):
    admin = make_admin()
    with pytest.raises(AppError) as exc:
        admin_service.deactivate_user(admin.id, admin.id)
    assert exc.value.code == "cannot_deactivate_self"


def test_temp_password_generated_and_hash_verifies(app, make_admin, make_student):
    admin = make_admin()
    student = make_student()

    temp_pass = admin_service.set_temporary_password(admin.id, student.id)
    assert len(temp_pass) >= 12
    assert student.check_password(temp_pass) is True
    assert student.must_change_password is True