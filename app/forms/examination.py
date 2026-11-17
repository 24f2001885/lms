"""
app/forms/examination.py - WTForms for creating and editing examinations (ADM-05).
"""

from typing import Any

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models.course import Course
from app.models.examination import Examination
from app.services import windows


class ExaminationForm(FlaskForm):
    """Form for configuring examinations and dual timeline windows."""

    course_id = SelectField(
        "Course",
        coerce=int,
        validators=[DataRequired(message="Please select a course.")],
    )
    name = StringField(
        "Examination name",
        validators=[
            DataRequired(message="Examination name is required."),
            Length(min=2, max=150, message="Name must be between 2 and 150 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=2000)],
        filters=[lambda x: x.strip() if x else ""],
    )
    exam_type = SelectField(
        "Examination type",
        choices=[
            ("viva", "Viva"),
            ("practical", "Practical"),
            ("project_demo", "Project demo"),
            ("assessment", "Assessment"),
        ],
        validators=[DataRequired()],
    )
    duration_minutes = IntegerField(
        "Duration (minutes)",
        validators=[
            DataRequired(message="Duration is required."),
            NumberRange(min=1, max=1440, message="Duration must be between 1 and 1440 minutes."),
        ],
        default=30,
    )
    max_marks = IntegerField(
        "Maximum marks",
        validators=[
            DataRequired(message="Maximum marks is required."),
            NumberRange(min=1, max=1000, message="Maximum marks must be between 1 and 1000."),
        ],
        default=100,
    )

    # HTML datetime-local inputs
    slot_creation_start = StringField(
        "Slot creation start",
        validators=[DataRequired(message="Slot creation start date and time is required.")],
    )
    slot_creation_end = StringField(
        "Slot creation end",
        validators=[DataRequired(message="Slot creation end date and time is required.")],
    )
    booking_start = StringField(
        "Booking start",
        validators=[DataRequired(message="Booking start date and time is required.")],
    )
    booking_end = StringField(
        "Booking end",
        validators=[DataRequired(message="Booking end date and time is required.")],
    )
    cancellation_deadline = StringField(
        "Cancellation deadline (optional)",
        validators=[Optional()],
    )

    submit = SubmitField("Save examination")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate active courses
        self.course_id.choices = [
            (c.id, f"{c.code} - {c.name}")
            for c in Course.query.filter_by(status="active").order_by(Course.code.asc()).all()
        ]

    def populate_from(self, exam: Examination) -> None:
        """Pre-fill form fields from an existing Examination model using local time."""
        self.course_id.data = exam.course_id
        self.name.data = exam.name
        self.description.data = exam.description
        self.exam_type.data = exam.exam_type
        self.duration_minutes.data = exam.duration_minutes
        self.max_marks.data = exam.max_marks
        self.slot_creation_start.data = windows.to_input_value(exam.slot_creation_start)
        self.slot_creation_end.data = windows.to_input_value(exam.slot_creation_end)
        self.booking_start.data = windows.to_input_value(exam.booking_start)
        self.booking_end.data = windows.to_input_value(exam.booking_end)
        self.cancellation_deadline.data = windows.to_input_value(exam.cancellation_deadline)

    def to_service_data(self) -> dict[str, Any]:
        """Convert form inputs and parse datetime strings to naive UTC."""
        try:
            sc_start = windows.from_local_input(self.slot_creation_start.data)
        except ValueError:
            self.slot_creation_start.errors.append("Enter a valid date and time.")
            sc_start = None

        try:
            sc_end = windows.from_local_input(self.slot_creation_end.data)
        except ValueError:
            self.slot_creation_end.errors.append("Enter a valid date and time.")
            sc_end = None

        try:
            bk_start = windows.from_local_input(self.booking_start.data)
        except ValueError:
            self.booking_start.errors.append("Enter a valid date and time.")
            bk_start = None

        try:
            bk_end = windows.from_local_input(self.booking_end.data)
        except ValueError:
            self.booking_end.errors.append("Enter a valid date and time.")
            bk_end = None

        cancel_dl = None
        if self.cancellation_deadline.data and self.cancellation_deadline.data.strip():
            try:
                cancel_dl = windows.from_local_input(self.cancellation_deadline.data)
            except ValueError:
                self.cancellation_deadline.errors.append("Enter a valid date and time.")

        # Cross-field validations
        if sc_start and sc_end and sc_end <= sc_start:
            self.slot_creation_end.errors.append(
                "Slot creation end must be strictly after slot creation start."
            )
        if bk_start and bk_end and bk_end <= bk_start:
            self.booking_end.errors.append("Booking end must be strictly after booking start.")
        if sc_end and bk_start and bk_start < sc_end:
            self.booking_start.errors.append(
                "Booking start cannot be earlier than slot creation end."
            )
        if cancel_dl and bk_start and cancel_dl < bk_start:
            self.cancellation_deadline.errors.append(
                "Cancellation deadline cannot be earlier than booking start."
            )

        return {
            "course_id": self.course_id.data,
            "name": self.name.data,
            "description": self.description.data,
            "exam_type": self.exam_type.data,
            "duration_minutes": self.duration_minutes.data,
            "max_marks": self.max_marks.data,
            "slot_creation_start": sc_start,
            "slot_creation_end": sc_end,
            "booking_start": bk_start,
            "booking_end": bk_end,
            "cancellation_deadline": cancel_dl,
        }
