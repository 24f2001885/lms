"""
WTForms for editing the signed-in user's own profile (PUB-06, route /profile).
"""

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.models.student_profile import StudentProfile
from app.validation import (
    PhoneChars,
    RollNumber,
    SafeText,
    html_attrs,
    limits,
    msg,
    strip_filter,
    upper_strip_filter,
)


def fields_for_role(role: str) -> list[str]:
    """Return the editable profile field names for a given user role."""
    if role == "admin":
        return ["full_name"]
    if role == "examiner":
        return ["full_name", "contact_phone", "department", "designation"]
    if role == "student":
        return ["full_name", "contact_phone", "roll_number", "program"]
    return []


class ProfileForm(FlaskForm):
    full_name = StringField(
        "Full name",
        filters=[strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            Length(
                min=limits.NAME_MIN,
                max=limits.NAME_MAX,
                message=msg("between_length", min=limits.NAME_MIN, max=limits.NAME_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(
            min_len=limits.NAME_MIN,
            max_len=limits.NAME_MAX,
            autocomplete="name",
        ),
    )
    contact_phone = StringField(
        "Phone",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.PHONE_MAX,
                message=msg("max_length", max=limits.PHONE_MAX),
            ),
            PhoneChars(),
        ],
        render_kw=html_attrs(
            max_len=limits.PHONE_MAX,
            pattern=limits.PHONE_PATTERN,
            title=limits.PHONE_TITLE,
            autocomplete="tel",
            field_type="tel",
        ),
    )
    department = StringField(
        "Department",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.DEPARTMENT_MAX,
                message=msg("max_length", max=limits.DEPARTMENT_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(max_len=limits.DEPARTMENT_MAX),
    )
    designation = StringField(
        "Designation",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.DESIGNATION_MAX,
                message=msg("max_length", max=limits.DESIGNATION_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(max_len=limits.DESIGNATION_MAX),
    )
    roll_number = StringField(
        "Roll number",
        filters=[upper_strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.ROLL_MAX,
                message=msg("max_length", max=limits.ROLL_MAX),
            ),
            RollNumber(),
        ],
        render_kw=html_attrs(
            max_len=limits.ROLL_MAX,
            pattern=limits.ROLL_PATTERN,
            title=limits.ROLL_TITLE,
        ),
    )
    program = StringField(
        "Program",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.PROGRAM_MAX,
                message=msg("max_length", max=limits.PROGRAM_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(max_len=limits.PROGRAM_MAX),
    )
    submit = SubmitField("Save changes")

    def __init__(self, user_id: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id

    @classmethod
    def fields_for_role(cls, role: str) -> list[str]:
        return fields_for_role(role)

    def validate_roll_number(self, field) -> None:
        if not field.data:
            return
        q = StudentProfile.query.filter(StudentProfile.roll_number == field.data)
        if self.user_id is not None:
            q = q.filter(StudentProfile.user_id != self.user_id)
        if q.first() is not None:
            raise ValidationError("This roll number is already in use by another student.")
