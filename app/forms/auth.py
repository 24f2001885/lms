"""
WTForms for login, registration, and change-password using app.validation.
"""

from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import PasswordField, RadioField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.models.user import User
from app.validation import (
    MatchesField,
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


class LoginForm(FlaskForm):
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
            autocomplete="username",
            field_type="email",
        ),
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message=msg("required")),
            Length(
                max=limits.PASSWORD_MAX,
                message=msg("max_length", max=limits.PASSWORD_MAX),
            ),
        ],
        render_kw=html_attrs(
            max_len=limits.PASSWORD_MAX,
            autocomplete="current-password",
        ),
    )
    submit = SubmitField("Log in")


class RegisterForm(FlaskForm):
    role = RadioField(
        "Role",
        choices=[("student", "Student"), ("examiner", "Examiner")],
        validators=[DataRequired(message=msg("required"))],
    )
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
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message=msg("required")),
            StrongPassword(limits.PASSWORD_MIN, limits.PASSWORD_MAX),
        ],
        render_kw=html_attrs(
            min_len=limits.PASSWORD_MIN,
            max_len=limits.PASSWORD_MAX,
            autocomplete="new-password",
            strength_target="password-strength-hint",
        ),
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message=msg("required")),
            MatchesField("password", message=msg("passwords_mismatch")),
        ],
        render_kw=html_attrs(
            min_len=limits.PASSWORD_MIN,
            max_len=limits.PASSWORD_MAX,
            autocomplete="new-password",
            rule="match:password",
        ),
    )
    department = StringField(
        "Department (examiners)",
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
    contact_phone = StringField(
        "Phone (examiners)",
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
    submit = SubmitField("Register")

    def validate_role(self, field) -> None:
        if field.data not in ("student", "examiner"):
            raise ValidationError("Invalid role selection.")

    def validate_email(self, field) -> None:
        if not field.data:
            return
        existing = User.query.filter(func.lower(User.email) == field.data.lower()).first()
        if existing is not None:
            raise ValidationError(msg("email_taken"))


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Current password",
        validators=[
            DataRequired(message=msg("required")),
            Length(
                max=limits.PASSWORD_MAX,
                message=msg("max_length", max=limits.PASSWORD_MAX),
            ),
        ],
        render_kw=html_attrs(
            max_len=limits.PASSWORD_MAX,
            autocomplete="current-password",
        ),
    )
    new_password = PasswordField(
        "New password",
        validators=[
            DataRequired(message=msg("required")),
            StrongPassword(limits.PASSWORD_MIN, limits.PASSWORD_MAX),
        ],
        render_kw=html_attrs(
            min_len=limits.PASSWORD_MIN,
            max_len=limits.PASSWORD_MAX,
            autocomplete="new-password",
            rule="different:current_password",
            strength_target="password-strength-hint",
        ),
    )
    confirm_new_password = PasswordField(
        "Confirm new password",
        validators=[
            DataRequired(message=msg("required")),
            MatchesField("new_password", message=msg("passwords_mismatch")),
        ],
        render_kw=html_attrs(
            min_len=limits.PASSWORD_MIN,
            max_len=limits.PASSWORD_MAX,
            autocomplete="new-password",
            rule="match:new_password",
        ),
    )
    submit = SubmitField("Update password")

    def validate_new_password(self, field) -> None:
        if field.data and self.current_password.data and field.data == self.current_password.data:
            raise ValidationError(msg("password_same_as_current"))
