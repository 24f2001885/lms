"""
FILE PURPOSE: Small Admin-only forms (assign examiner, change slot examiner, create examiner, temporary password, search).
DEPENDS ON: flask_wtf, wtforms, app/security/auth_helpers.py (validate_password_strength).
PROMPT FOR LLM IMPLEMENTATION:
1. AssignExaminerForm: examiner_id SelectField (coerce int) filled by the view with approved, active, not-yet-assigned examiners.
2. ChangeSlotExaminerForm: examiner_id SelectField filled by the view with approved, active examiners assigned to the slot's examination, excluding the current one.
3. ExaminerCreateForm: full_name, email (Email, lowercase), contact_phone Optional, department Optional, designation Optional, temporary_password (PasswordField with strength validation; label "Temporary password (the examiner must change it)").
4. TemporaryPasswordForm: new_password Optional (blank means "generate one"); when given, it must pass validate_password_strength.
5. AdminSearchForm (GET, csrf disabled): q (StringField, Length max 100), kind (SelectField student/examiner/examination/booking, default student).
6. All forms inherit from FlaskForm; none echo password values back.
DEBUGGING:
# print(f"[DEBUG] admin form {type(form).__name__} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- ExaminerCreateForm rejects a weak temporary password and an invalid email.
- AdminSearchForm rejects kind="invoice".
- ChangeSlotExaminerForm choices never include the slot's current examiner.

app/forms/admin.py - Administrator control panel WTForms for LMS.

Defines forms for courses, examinations, timeline windows, rubrics,
examiner assignments, booking rescheduling, and slot examiner changes.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from app.models.course import Course
from app.security.auth_helpers import validate_password_strength


class CourseForm(FlaskForm):
    """Form for creating and editing academic courses."""

    code = StringField(
        "Course Code",
        validators=[
            DataRequired(message="Course code is required."),
            Length(min=2, max=30, message="Course code must be between 2 and 30 characters."),
        ],
        filters=[lambda x: x.strip().upper() if x else ""],
    )
    name = StringField(
        "Course Name",
        validators=[
            DataRequired(message="Course name is required."),
            Length(min=2, max=150, message="Course name must be between 2 and 150 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    description = TextAreaField(
        "Description (Optional)",
        validators=[Optional(), Length(max=500)],
        filters=[lambda x: x.strip() if x else ""],
    )
    status = SelectField(
        "Status",
        choices=[("active", "Active"), ("inactive", "Inactive")],
        default="active",
        validators=[DataRequired()],
    )
    submit = SubmitField("Save Course")

    def __init__(self, original_course_id: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_course_id = original_course_id

    def validate_code(self, field):
        """Enforce case-insensitive course code uniqueness."""
        clean_code = field.data.strip().upper()
        existing = Course.query.filter(Course.code.ilike(clean_code)).first()
        if existing and existing.id != self.original_course_id:
            raise ValidationError(f"Course code '{clean_code}' is already in use.")


class ExaminationForm(FlaskForm):
    """Form for configuring examinations and dual timeline windows."""

    course_id = SelectField(
        "Course",
        coerce=int,
        validators=[DataRequired(message="Please select a course.")],
    )
    name = StringField(
        "Examination Name",
        validators=[
            DataRequired(message="Examination name is required."),
            Length(min=2, max=150, message="Name must be between 2 and 150 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    description = TextAreaField(
        "Description / Instructions",
        validators=[Optional(), Length(max=500)],
        filters=[lambda x: x.strip() if x else ""],
    )
    exam_type = SelectField(
        "Examination Type",
        choices=[
            ("viva", "Viva"),
            ("practical", "Practical"),
            ("project_demo", "Project Demo"),
            ("assessment", "Assessment"),
        ],
        validators=[DataRequired()],
    )
    duration_minutes = IntegerField(
        "Duration per Slot (Minutes)",
        validators=[
            DataRequired(message="Duration is required."),
            NumberRange(min=5, max=480, message="Duration must be between 5 and 480 minutes."),
        ],
        default=30,
    )
    max_marks = IntegerField(
        "Maximum Marks",
        validators=[
            DataRequired(message="Maximum marks is required."),
            NumberRange(min=1, max=1000, message="Maximum marks must be between 1 and 1000."),
        ],
        default=100,
    )

    # Window 1: Slot Creation Period
    slot_creation_start = DateTimeLocalField(
        "Slot Creation Start",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Slot creation start date/time is required.")],
    )
    slot_creation_end = DateTimeLocalField(
        "Slot Creation End",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Slot creation end date/time is required.")],
    )

    # Window 2: Student Booking Period
    booking_start = DateTimeLocalField(
        "Booking Start",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Booking start date/time is required.")],
    )
    booking_end = DateTimeLocalField(
        "Booking End",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Booking end date/time is required.")],
    )
    cancellation_deadline = DateTimeLocalField(
        "Cancellation Deadline",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )

    # Admin Control Switches
    slot_creation_open = BooleanField("Open Slot Creation Immediately")
    booking_open = BooleanField("Open Student Booking Immediately")

    submit = SubmitField("Save Examination")

    def validate_slot_creation_end(self, field):
        """Ensure slot creation start is earlier than slot creation end."""
        if self.slot_creation_start.data and field.data:
            if field.data <= self.slot_creation_start.data:
                raise ValidationError("Slot creation end must be strictly after slot creation start.")

    def validate_booking_start(self, field):
        """Ensure slot creation period ends before or when student booking begins."""
        if self.slot_creation_end.data and field.data:
            if field.data < self.slot_creation_end.data:
                raise ValidationError("Booking start cannot be earlier than slot creation end.")

    def validate_booking_end(self, field):
        """Ensure booking start is earlier than booking end."""
        if self.booking_start.data and field.data:
            if field.data <= self.booking_start.data:
                raise ValidationError("Booking end must be strictly after booking start.")

    def validate_cancellation_deadline(self, field):
        """Ensure cancellation deadline does not exceed booking end."""
        if field.data and self.booking_end.data:
            if field.data > self.booking_end.data:
                raise ValidationError("Cancellation deadline cannot exceed the booking end deadline.")


class RubricForm(FlaskForm):
    """Form for adding and editing rubric criteria."""

    criterion_name = StringField(
        "Criterion Name",
        validators=[
            DataRequired(message="Criterion name is required."),
            Length(min=2, max=120, message="Name must be between 2 and 120 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    description = TextAreaField(
        "Description / Scoring Guidelines",
        validators=[Optional(), Length(max=500)],
        filters=[lambda x: x.strip() if x else ""],
    )
    weightage = DecimalField(
        "Weightage (%)",
        places=2,
        validators=[
            DataRequired(message="Weightage is required."),
            NumberRange(min=0.01, max=100.0, message="Weightage must be between 0.01% and 100%."),
        ],
    )
    max_score = DecimalField(
        "Maximum Score",
        places=2,
        validators=[
            DataRequired(message="Max score is required."),
            NumberRange(min=0.5, max=1000.0, message="Maximum score must be greater than 0."),
        ],
    )
    submit = SubmitField("Save Criterion")


class AssignExaminerForm(FlaskForm):
    """Form for assigning an approved faculty examiner to an examination."""

    examiner_id = SelectField(
        "Select Approved Examiner",
        coerce=int,
        validators=[DataRequired(message="Please select an examiner.")],
    )
    submit = SubmitField("Assign Examiner")


class RescheduleBookingForm(FlaskForm):
    """Form for reassigning a student booking to another slot of the same exam."""

    new_slot_id = SelectField(
        "Select Target Slot",
        coerce=int,
        validators=[DataRequired(message="Please choose a target slot.")],
    )
    submit = SubmitField("Reschedule Booking")


class ChangeSlotExaminerForm(FlaskForm):
    """Form for reassigning a slot to a different assigned examiner."""

    new_examiner_id = SelectField(
        "Select New Examiner",
        coerce=int,
        validators=[DataRequired(message="Please choose an examiner.")],
    )
    submit = SubmitField("Change Slot Examiner")


class SetTemporaryPasswordForm(FlaskForm):
    """Form for Admin-assisted temporary password resets (Design Plan 4.1)."""

    temporary_password = PasswordField(
        "Temporary Password",
        validators=[DataRequired(message="Temporary password is required.")],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm password."),
            EqualTo("temporary_password", message="Passwords do not match."),
        ],
    )
    submit = SubmitField("Set Temporary Password")

    def validate_temporary_password(self, field):
        problems = validate_password_strength(field.data)
        if problems:
            raise ValidationError(problems[0])