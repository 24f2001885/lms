"""
Acceptance test for backend validation: forms and API endpoints reject invalid
inputs directly (no browser, no JS) with catalogue messages and leave DB state unchanged.
"""

import pytest

from app.blueprints.api_v1.validation import (
    CANCEL_SCHEMA,
    EXAMINATION_SCHEMA,
    SLOT_SCHEMA,
    ApiValidationError,
    validate,
)
from app.forms.admin_actions import AdminSearchForm, ExaminerCreateForm
from app.forms.auth import RegisterForm
from app.forms.booking_actions import ReasonForm
from app.forms.course import CourseForm
from app.forms.profile import ProfileForm
from app.forms.rubric import RubricForm
from app.forms.slot import SlotForm
from app.validation import limits, msg

pytestmark = pytest.mark.validation


@pytest.mark.parametrize(
    "form_cls,field_name,bad_value,expected_msg",
    [
        (
            RegisterForm,
            "full_name",
            "A",
            msg("between_length", min=limits.NAME_MIN, max=limits.NAME_MAX),
        ),
        (
            RegisterForm,
            "full_name",
            "A" * (limits.NAME_MAX + 1),
            msg("between_length", min=limits.NAME_MIN, max=limits.NAME_MAX),
        ),
        (RegisterForm, "full_name", "Bad\x00Name", msg("unsafe_characters")),
        (RegisterForm, "email", "not-an-email", msg("invalid_email")),
        (RegisterForm, "password", "short1", msg("password_too_short", min=limits.PASSWORD_MIN)),
        (
            RegisterForm,
            "password",
            "A" * (limits.PASSWORD_MAX + 1) + "1",
            msg("password_too_long", max=limits.PASSWORD_MAX),
        ),
        (RegisterForm, "password", "onlyletters", msg("password_no_digit")),
        (RegisterForm, "password", "123456789", msg("password_no_letter")),
        (RegisterForm, "contact_phone", "12345abc", msg("phone_chars")),
        (
            RegisterForm,
            "department",
            "D" * (limits.DEPARTMENT_MAX + 1),
            msg("max_length", max=limits.DEPARTMENT_MAX),
        ),
        (ProfileForm, "roll_number", "BAD ROLL!", msg("pattern_mismatch", title=limits.ROLL_TITLE)),
        (
            ProfileForm,
            "program",
            "P" * (limits.PROGRAM_MAX + 1),
            msg("max_length", max=limits.PROGRAM_MAX),
        ),
        (
            ProfileForm,
            "designation",
            "D" * (limits.DESIGNATION_MAX + 1),
            msg("max_length", max=limits.DESIGNATION_MAX),
        ),
        (
            CourseForm,
            "code",
            "A",
            msg("between_length", min=limits.COURSE_CODE_MIN, max=limits.COURSE_CODE_MAX),
        ),
        (
            CourseForm,
            "code",
            "A" * (limits.COURSE_CODE_MAX + 1),
            msg("between_length", min=limits.COURSE_CODE_MIN, max=limits.COURSE_CODE_MAX),
        ),
        (CourseForm, "code", "CS 101", msg("pattern_mismatch", title=limits.COURSE_CODE_TITLE)),
        (
            CourseForm,
            "name",
            "X",
            msg("between_length", min=limits.COURSE_NAME_MIN, max=limits.COURSE_NAME_MAX),
        ),
        (
            CourseForm,
            "name",
            "X" * (limits.COURSE_NAME_MAX + 1),
            msg("between_length", min=limits.COURSE_NAME_MIN, max=limits.COURSE_NAME_MAX),
        ),
        (
            CourseForm,
            "description",
            "D" * (limits.DESCRIPTION_MAX + 1),
            msg("max_length", max=limits.DESCRIPTION_MAX),
        ),
        (
            RubricForm,
            "criterion_name",
            "C",
            msg("between_length", min=limits.CRITERION_MIN, max=limits.CRITERION_MAX),
        ),
        (
            RubricForm,
            "criterion_name",
            "C" * (limits.CRITERION_MAX + 1),
            msg("between_length", min=limits.CRITERION_MIN, max=limits.CRITERION_MAX),
        ),
        (
            RubricForm,
            "description",
            "D" * (limits.RUBRIC_DESCRIPTION_MAX + 1),
            msg("max_length", max=limits.RUBRIC_DESCRIPTION_MAX),
        ),
        (
            RubricForm,
            "weightage",
            "-1",
            msg("between_value", min=limits.WEIGHTAGE_MIN, max=limits.WEIGHTAGE_MAX),
        ),
        (
            RubricForm,
            "weightage",
            "100.01",
            msg("between_value", min=limits.WEIGHTAGE_MIN, max=limits.WEIGHTAGE_MAX),
        ),
        (RubricForm, "weightage", "10.123", msg("too_many_decimals", places=limits.DECIMAL_PLACES)),
        (RubricForm, "max_score", "0", msg("min_value", min=limits.MAX_SCORE_MIN)),
        (
            SlotForm,
            "max_capacity",
            "0",
            msg("between_value", min=limits.CAPACITY_MIN, max=limits.CAPACITY_MAX),
        ),
        (
            SlotForm,
            "max_capacity",
            str(limits.CAPACITY_MAX + 1),
            msg("between_value", min=limits.CAPACITY_MIN, max=limits.CAPACITY_MAX),
        ),
        (
            ReasonForm,
            "reason",
            "ab",
            msg("between_length", min=limits.REASON_MIN, max=limits.REASON_MAX),
        ),
        (
            ReasonForm,
            "reason",
            "r" * (limits.REASON_MAX + 1),
            msg("between_length", min=limits.REASON_MIN, max=limits.REASON_MAX),
        ),
        (
            AdminSearchForm,
            "q",
            "q" * (limits.SEARCH_Q_MAX + 1),
            msg("max_length", max=limits.SEARCH_Q_MAX),
        ),
        (
            ExaminerCreateForm,
            "temporary_password",
            "weak",
            msg("password_too_short", min=limits.PASSWORD_MIN),
        ),
    ],
)
def test_form_boundary_rejections(app, form_cls, field_name, bad_value, expected_msg):
    """Every form rejects invalid boundary values with the exact catalogue message."""
    with app.test_request_context(method="POST", data={field_name: bad_value}):
        form = form_cls()
        form.validate()
        field = getattr(form, field_name)
        assert expected_msg in field.errors


@pytest.mark.parametrize(
    "schema,payload,field_name,expected_msg",
    [
        (
            EXAMINATION_SCHEMA,
            {"name": "A"},
            "name",
            msg("between_length", min=limits.EXAM_NAME_MIN, max=limits.EXAM_NAME_MAX),
        ),
        (
            EXAMINATION_SCHEMA,
            {"name": "A" * (limits.EXAM_NAME_MAX + 1)},
            "name",
            msg("between_length", min=limits.EXAM_NAME_MIN, max=limits.EXAM_NAME_MAX),
        ),
        (
            EXAMINATION_SCHEMA,
            {"duration_minutes": 0},
            "duration_minutes",
            msg("between_value", min=limits.DURATION_MIN, max=limits.DURATION_MAX),
        ),
        (
            EXAMINATION_SCHEMA,
            {"duration_minutes": limits.DURATION_MAX + 1},
            "duration_minutes",
            msg("between_value", min=limits.DURATION_MIN, max=limits.DURATION_MAX),
        ),
        (
            EXAMINATION_SCHEMA,
            {"max_marks": 0},
            "max_marks",
            msg("between_value", min=limits.MAX_MARKS_MIN, max=limits.MAX_MARKS_MAX),
        ),
        (
            EXAMINATION_SCHEMA,
            {"max_marks": limits.MAX_MARKS_MAX + 1},
            "max_marks",
            msg("between_value", min=limits.MAX_MARKS_MIN, max=limits.MAX_MARKS_MAX),
        ),
        (
            SLOT_SCHEMA,
            {"max_capacity": 0},
            "max_capacity",
            msg("between_value", min=limits.CAPACITY_MIN, max=limits.CAPACITY_MAX),
        ),
        (
            SLOT_SCHEMA,
            {"max_capacity": limits.CAPACITY_MAX + 1},
            "max_capacity",
            msg("between_value", min=limits.CAPACITY_MIN, max=limits.CAPACITY_MAX),
        ),
        (
            CANCEL_SCHEMA,
            {"reason": "ab"},
            "reason",
            msg("between_length", min=limits.REASON_MIN, max=limits.REASON_MAX),
        ),
        (
            CANCEL_SCHEMA,
            {"reason": "x" * (limits.REASON_MAX + 1)},
            "reason",
            msg("between_length", min=limits.REASON_MIN, max=limits.REASON_MAX),
        ),
    ],
)
def test_api_schema_parity(schema, payload, field_name, expected_msg):
    """JSON API schemas enforce identical boundary values and messages as WTForms."""
    with pytest.raises(ApiValidationError) as exc_info:
        validate(payload, schema, partial=True)
    assert field_name in exc_info.value.fields
    assert expected_msg in exc_info.value.fields[field_name]
