"""
Admin-only forms (assign examiner, change slot examiner, create examiner,
temporary password, search).
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.forms.common import FilterForm
from app.validation import (
    PhoneChars,
    SafeText,
    StrongPassword,
    ValidEmail,
    html_attrs,
    limits,
    lower_strip_filter,
    msg,
    strip_filter,
)


class AssignExaminerForm(FlaskForm):
    examiner_id = SelectField(
        "Examiner",
        coerce=int,
        validators=[DataRequired(message=msg("required"))],
    )
    submit = SubmitField("Assign")


class ChangeSlotExaminerForm(FlaskForm):
    examiner_id = SelectField(
        "New examiner",
        coerce=int,
        validators=[DataRequired(message=msg("required"))],
    )
    submit = SubmitField("Change examiner")


class ExaminerCreateForm(FlaskForm):
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
    email = StringField(
        "Email",
        filters=[lower_strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            ValidEmail(message=msg("invalid_email")),
            Length(
                max=limits.EMAIL_MAX,
                message=msg("max_length", max=limits.EMAIL_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(
            max_len=limits.EMAIL_MAX,
            autocomplete="email",
            field_type="email",
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
    temporary_password = PasswordField(
        "Temporary password (the examiner must change it)",
        validators=[
            DataRequired(message=msg("required")),
            StrongPassword(limits.PASSWORD_MIN, limits.PASSWORD_MAX),
        ],
        render_kw=html_attrs(
            min_len=limits.PASSWORD_MIN,
            max_len=limits.PASSWORD_MAX,
            autocomplete="new-password",
            strength_target="temp-password-strength-hint",
        ),
    )
    submit = SubmitField("Save")


class TemporaryPasswordForm(FlaskForm):
    new_password = PasswordField(
        "Temporary password",
        validators=[
            Optional(),
            StrongPassword(limits.PASSWORD_MIN, limits.PASSWORD_MAX),
        ],
        render_kw=html_attrs(
            min_len=limits.PASSWORD_MIN,
            max_len=limits.PASSWORD_MAX,
            autocomplete="new-password",
            strength_target="temp-password-strength-hint",
        ),
    )
    submit = SubmitField("Set temporary password")


class AdminSearchForm(FilterForm):
    kind = SelectField(
        "Search in",
        choices=[
            ("student", "Students"),
            ("examiner", "Examiners"),
            ("examination", "Examinations"),
            ("booking", "Bookings"),
        ],
        default="student",
        validators=[DataRequired(message=msg("required"))],
    )
    q = StringField(
        "Query",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.SEARCH_Q_MAX,
                message=msg("max_length", max=limits.SEARCH_Q_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(max_len=limits.SEARCH_Q_MAX),
    )
    submit = SubmitField("Search")
