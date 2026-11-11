"""
FILE PURPOSE: WTForms for editing the signed-in user's own profile (screen PUB-06, route /profile).
DEPENDS ON: flask_wtf, wtforms, app/models (User, ExaminerProfile, StudentProfile).
PROMPT FOR LLM IMPLEMENTATION:
1. Build ONE form class ProfileForm with these fields: full_name (DataRequired, Length 2-120), contact_phone (Optional, Length max 20, digits plus + - space), department (Optional, Length max 120), designation (Optional, Length max 120), roll_number (Optional, Length max 30), program (Optional, Length max 120).
2. Which fields are shown/used depends on the role, decided in the view/template: admin uses full_name only; examiner uses full_name, contact_phone, department, designation; student uses full_name, contact_phone, roll_number, program. Provide a classmethod or helper fields_for_role(role) returning the list of field names so the view and the template share the same rule.
3. roll_number uniqueness: validate_roll_number rejects a roll number already used by ANOTHER student (compare profile ids; the user's own current value is allowed). Normalise to uppercase and strip.
4. Email is NOT editable here (it is the login identity); role and approval status are never editable through this form (mass-assignment protection: the view copies only whitelisted fields).
DEBUGGING:
# print(f"[DEBUG] profile form role_fields={fields_for_role(role)} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- fields_for_role("admin") == ["full_name"]; examiner and student lists match item 2.
- A student cannot take another student's roll_number but can resubmit their own.
- A forged POST containing role=admin or approval_status=approved does not change those columns.

app/forms/profile.py - WTForms for editing user profile information (PUB-06).

Provides role-aware profile field resolution and uniqueness validation.
"""


from flask import g
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

from app.models.student_profile import StudentProfile


class ProfileForm(FlaskForm):
    """Unified user profile form with role-scoped field support."""

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=120, message="Name must be between 2 and 120 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )

    contact_phone = StringField(
        "Contact Phone",
        validators=[
            Optional(),
            Length(max=20),
            Regexp(r"^[0-9+\- ]*$", message="Phone number may only contain digits, +, -, and spaces."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )

    # Examiner fields
    department = StringField("Department", validators=[Optional(), Length(max=120)])
    designation = StringField("Designation", validators=[Optional(), Length(max=120)])

    # Student fields
    roll_number = StringField("Roll Number", validators=[Optional(), Length(max=30)])
    program = StringField("Academic Program", validators=[Optional(), Length(max=120)])

    submit = SubmitField("Save Changes")

    @classmethod
    def fields_for_role(cls, role: str) -> list[str]:
        """Return the list of form field names applicable to a specific user role."""
        if role == "admin":
            return ["full_name"]
        if role == "examiner":
            return ["full_name", "contact_phone", "department", "designation"]
        if role == "student":
            return ["full_name", "contact_phone", "roll_number", "program"]
        return ["full_name"]

    def validate_roll_number(self, field):
        """Ensure roll number is unique across students (excluding the current user)."""
        if not field.data or not field.data.strip():
            return

        clean_roll = field.data.strip().upper()
        current_user = getattr(g, "user", None)
        current_user_id = current_user.id if current_user else None

        existing = StudentProfile.query.filter_by(roll_number=clean_roll).first()
        if existing and existing.user_id != current_user_id:
            raise ValidationError("This roll number is already assigned to another student.")