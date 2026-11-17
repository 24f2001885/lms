"""
Proves HTML5 attributes rendered by forms match describe(field) and that
the validation matrix documentation matches the form/schema fields.
"""

import pathlib
import re

import pytest

from app.blueprints.api_v1.validation import CANCEL_SCHEMA, EXAMINATION_SCHEMA, SLOT_SCHEMA
from app.forms.admin_actions import AdminSearchForm, ExaminerCreateForm
from app.forms.auth import ChangePasswordForm, LoginForm, RegisterForm
from app.forms.booking_actions import ReasonForm
from app.forms.course import CourseForm
from app.forms.examination import ExaminationForm
from app.forms.profile import ProfileForm
from app.forms.rubric import RubricForm
from app.forms.slot import SlotForm
from app.validation import describe

pytestmark = pytest.mark.validation


@pytest.mark.parametrize(
    "form_cls",
    [
        LoginForm,
        RegisterForm,
        ChangePasswordForm,
        ProfileForm,
        CourseForm,
        ExaminationForm,
        RubricForm,
        SlotForm,
        ReasonForm,
        ExaminerCreateForm,
        AdminSearchForm,
    ],
)
def test_form_render_kw_matches_describe(app, form_cls):
    """Every bound field's render_kw attributes agree with its server validators."""
    with app.test_request_context():
        form = form_cls()
        for field in form:
            if field.type in ("CSRFTokenField", "SubmitField", "RadioField", "SelectField"):
                continue
            d = describe(field)
            rkw = d["render_kw"]
            if d["minlength"] is not None:
                assert (
                    rkw.get("minlength") == d["minlength"]
                ), f"{form_cls.__name__}.{field.name} minlength mismatch"
            if d["maxlength"] is not None:
                assert (
                    rkw.get("maxlength") == d["maxlength"]
                ), f"{form_cls.__name__}.{field.name} maxlength mismatch"
            if d["min"] is not None:
                assert rkw.get("min") == d["min"], f"{form_cls.__name__}.{field.name} min mismatch"
            if d["max"] is not None:
                assert rkw.get("max") == d["max"], f"{form_cls.__name__}.{field.name} max mismatch"


def test_validation_matrix_fields_exist_in_code(app):
    """Every field listed in docs/validation_matrix.md exists in a form or API schema."""
    matrix_path = pathlib.Path("docs/validation_matrix.md")
    if not matrix_path.exists():
        pytest.skip("docs/validation_matrix.md not found")

    all_field_names = (
        set(EXAMINATION_SCHEMA)
        | set(SLOT_SCHEMA)
        | set(CANCEL_SCHEMA)
        | {"score_<id>", "comment_<id>", "remarks"}
    )
    with app.test_request_context():
        for cls in (
            LoginForm,
            RegisterForm,
            ChangePasswordForm,
            ProfileForm,
            CourseForm,
            ExaminationForm,
            RubricForm,
            SlotForm,
            ReasonForm,
            ExaminerCreateForm,
            AdminSearchForm,
        ):
            f = cls()
            all_field_names.update(f._fields.keys())

    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    checked = 0
    for line in lines:
        if line.startswith("| `"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 2:
                field_col = cols[1]
                for token in re.findall(r"`([^`]+)`", field_col):
                    assert (
                        token in all_field_names
                    ), f"Matrix field {token!r} not found in forms/schemas"
                    checked += 1
    assert checked >= 20
