"""
app/forms/admin_actions.py - Admin action forms for examiners, slots, and search.
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

from app.forms.auth import ValidEmail
from app.security.auth_helpers import validate_password_strength


class AssignExaminerForm(FlaskForm):
    """Form for assigning an approved examiner to an examination."""

    examiner_id = SelectField(
        "Examiner",
        coerce=int,
        validators=[DataRequired(message="Please select an examiner.")],
    )
    submit = SubmitField("Assign examiner")


class ChangeSlotExaminerForm(FlaskForm):
    """Form for reassigning a slot's examiner."""

    examiner_id = SelectField(
        "New examiner",
        coerce=int,
        validators=[DataRequired(message="Please select an examiner.")],
    )
    submit = SubmitField("Change examiner")


class ExaminerCreateForm(FlaskForm):
    """Form for an administrator to directly create an approved examiner."""

    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(min=2, max=120)],
        filters=[lambda x: x.strip() if x else ""],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), ValidEmail(), Length(max=254)],
        filters=[lambda x: x.strip().lower() if x else ""],
    )
    contact_phone = StringField(
        "Phone number",
        validators=[Optional(), Length(max=20), Regexp(r"^[0-9+\- ]*$", message="Invalid phone number format.")],
        filters=[lambda x: x.strip() if x else ""],
    )
    department = StringField("Department", validators=[Optional(), Length(max=120)])
    designation = StringField("Designation", validators=[Optional(), Length(max=120)])
    temporary_password = PasswordField(
        "Temporary password (the examiner must change it)",
        validators=[DataRequired()],
    )
    submit = SubmitField("Create examiner")

    def validate_temporary_password(self, field):
        problems = validate_password_strength(field.data)
        if problems:
            raise ValidationError(problems[0])


class TemporaryPasswordForm(FlaskForm):
    """Form for generating or setting a temporary password for a user."""

    new_password = PasswordField(
        "New password (leave blank to generate)",
        validators=[Optional()],
    )
    submit = SubmitField("Set temporary password")

    def validate_new_password(self, field):
        if field.data and field.data.strip():
            problems = validate_password_strength(field.data.strip())
            if problems:
                raise ValidationError(problems[0])


class AdminSearchForm(FlaskForm):
    """Form for GET search bar (CSRF disabled)."""

    class Meta:
        csrf = False

    q = StringField("Search query", validators=[Optional(), Length(max=100)])
    kind = SelectField(
        "Search in",
        choices=[
            ("student", "Students"),
            ("examiner", "Examiners"),
            ("examination", "Examinations"),
            ("booking", "Bookings"),
        ],
        default="student",
    )
    submit = SubmitField("Search")