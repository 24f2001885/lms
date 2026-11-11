"""
FILE PURPOSE: WTForms for login, registration and change-password (server-side validation; no JavaScript, per risk R-8).
DEPENDS ON: flask_wtf.FlaskForm, wtforms, app/security/auth_helpers.py (validate_password_strength), app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. LoginForm: email (StringField, DataRequired, Email, filters strip+lowercase), password (PasswordField, DataRequired), submit. Do not validate password strength at login.
2. RegisterForm: role (RadioField, choices ONLY ("student","Student") and ("examiner","Examiner"), DataRequired; "admin" must be impossible - an extra validate_role method rejects any other value even if the POST is tampered), full_name (DataRequired, Length 2-120, strip), email (DataRequired, Email, Length max 254, lowercased), password (DataRequired), confirm_password (DataRequired, EqualTo password with message "Passwords do not match"), department (Optional, Length max 120, label suffix "(examiners)"), contact_phone (Optional, Length max 20, digits plus + - space only, label suffix "(examiners)"). The extra fields are always rendered; they are stored only when role is examiner.
3. RegisterForm.validate_email: reject when a user with that email already exists (case-insensitive) with the message "An account with this email already exists." ; validate_password uses validate_password_strength and raises ValidationError with the first problem.
4. ChangePasswordForm: current_password (DataRequired), new_password (DataRequired, strength check), confirm_new_password (EqualTo new_password). Extra validation in the form: new_password must differ from current_password. The current-password check against the stored hash is done in the view (needs the logged-in user) and documented here in a comment.
5. All forms inherit FlaskForm so CSRF tokens are included automatically; field labels are plain English and match the Design Plan (section 4.1): "Full name", "Email", "Password", "Confirm password".
6. Each field has an explicit id and the form never echoes the password back into the HTML.
DEBUGGING:
# print(f"[DEBUG] form errors: {form.errors}")
OFFLINE DOCKER TEST CASES:
- RegisterForm with role "admin" is invalid (and no user is created by the view).
- Mismatched confirm_password gives the exact message "Passwords do not match".
- Duplicate email differing only by case is rejected.
- A 7-character password and an all-letters password are rejected; "Passw0rdOK" is accepted.
- ChangePasswordForm rejects new == current.
"""
"""
app/forms/auth.py - WTForms for authentication and account management.

Defines LoginForm, RegisterForm, and ChangePasswordForm with server-side validation.
Admin registration is strictly blocked at the form level.
"""

from email_validator import EmailNotValidError, validate_email
from flask import current_app, has_app_context
from flask_wtf import FlaskForm
from wtforms import PasswordField, RadioField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, Regexp, ValidationError

from app.models.user import User
from app.security.auth_helpers import validate_password_strength


class ValidEmail:
    """Validate email syntax, allowing .test and .local domains during testing."""

    def __init__(self, message: str = "Please enter a valid email address."):
        self.message = message

    def __call__(self, form, field):
        value = (field.data or "").strip()
        is_testing = has_app_context() and bool(current_app.config.get("TESTING", False))
        if is_testing and "@" in value:
            local, domain = value.rsplit("@", 1)
            if domain.lower().endswith(".local"):
                value = f"{local}@{domain[:-6]}.com"
        try:
            validate_email(value, check_deliverability=False, test_environment=is_testing)
        except EmailNotValidError as exc:
            raise ValidationError(self.message) from exc


class LoginForm(FlaskForm):
    """User login form."""

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            ValidEmail(message="Please enter a valid email address."),
            Length(max=254),
        ],
        filters=[lambda x: x.strip().lower() if x else ""],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )
    submit = SubmitField("Log in")


class RegisterForm(FlaskForm):
    """
    Account registration form for Students and Examiners.
    Admin registration is strictly prohibited.
    """

    role = RadioField(
        "Account Type",
        choices=[("student", "Student"), ("examiner", "Examiner")],
        default="student",
        validators=[DataRequired(message="Please select an account type.")],
    )
    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=120, message="Name must be between 2 and 120 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            ValidEmail(message="Please enter a valid email address."),
            Length(max=254),
        ],
        filters=[lambda x: x.strip().lower() if x else ""],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords do not match."),
        ],
    )

    # Optional examiner details (ignored if role is student)
    department = StringField(
        "Department (Examiners)",
        validators=[Optional(), Length(max=120)],
        filters=[lambda x: x.strip() if x else ""],
    )
    contact_phone = StringField(
        "Contact Phone (Examiners)",
        validators=[
            Optional(),
            Length(max=20),
            Regexp(r"^[0-9+\- ]*$", message="Phone number may only contain digits, +, -, and spaces."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )

    submit = SubmitField("Create Account")

    def validate_role(self, field):
        """Hard security guard: Admin role can never be selected through registration."""
        if field.data not in ("student", "examiner"):
            raise ValidationError("Invalid account type selected.")

    def validate_email(self, field):
        """Ensure email is unique across all users (case-insensitive)."""
        clean_email = field.data.strip().lower()
        if User.query.filter_by(email=clean_email).first() is not None:
            raise ValidationError("An account with this email already exists.")

    def validate_password(self, field):
        """Enforce password strength rules."""
        problems = validate_password_strength(field.data)
        if problems:
            raise ValidationError(problems[0])


class ChangePasswordForm(FlaskForm):
    """Change password form for forced first-login updates and regular changes."""

    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired(message="Current password is required.")],
    )
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(message="New password is required.")],
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="Passwords do not match."),
        ],
    )
    submit = SubmitField("Update Password")

    def validate_new_password(self, field):
        """Validate password strength and ensure new password differs from old."""
        problems = validate_password_strength(field.data)
        if problems:
            raise ValidationError(problems[0])
        if self.current_password.data and field.data == self.current_password.data:
            raise ValidationError("New password must be different from current password.")