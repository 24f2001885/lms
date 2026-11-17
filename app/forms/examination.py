"""
WTForms for creating and editing an examination (ADM-05) with datetime-local inputs.
"""

from typing import Any

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

from app.models.course import Course
from app.models.examination import EXAM_TYPES
from app.services import windows
from app.validation import (
    DateTimeLocal,
    ExaminationWindows,
    SafeText,
    html_attrs,
    limits,
    msg,
    strip_filter,
)

EXAM_TYPE_LABELS = {
    "viva": "Viva",
    "practical": "Practical",
    "project_demo": "Project demo",
    "assessment": "Assessment",
}


class ExaminationForm(FlaskForm):
    course_id = SelectField(
        "Course",
        coerce=int,
        validators=[DataRequired(message=msg("required"))],
    )
    name = StringField(
        "Examination name",
        filters=[strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            Length(
                min=limits.EXAM_NAME_MIN,
                max=limits.EXAM_NAME_MAX,
                message=msg("between_length", min=limits.EXAM_NAME_MIN, max=limits.EXAM_NAME_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(
            min_len=limits.EXAM_NAME_MIN,
            max_len=limits.EXAM_NAME_MAX,
        ),
    )
    description = TextAreaField(
        "Description",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.DESCRIPTION_MAX,
                message=msg("max_length", max=limits.DESCRIPTION_MAX),
            ),
            SafeText(multiline=True),
        ],
        render_kw=html_attrs(max_len=limits.DESCRIPTION_MAX),
    )
    exam_type = SelectField(
        "Examination type",
        choices=[(t, EXAM_TYPE_LABELS.get(t, t)) for t in EXAM_TYPES],
        validators=[DataRequired(message=msg("required"))],
    )
    duration_minutes = IntegerField(
        "Duration (minutes)",
        validators=[
            InputRequired(message=msg("required")),
            NumberRange(
                min=limits.DURATION_MIN,
                max=limits.DURATION_MAX,
                message=msg("between_value", min=limits.DURATION_MIN, max=limits.DURATION_MAX),
            ),
        ],
        render_kw=html_attrs(
            minimum=limits.DURATION_MIN,
            maximum=limits.DURATION_MAX,
            inputmode="numeric",
            field_type="number",
        ),
    )
    max_marks = IntegerField(
        "Maximum marks",
        validators=[
            InputRequired(message=msg("required")),
            NumberRange(
                min=limits.MAX_MARKS_MIN,
                max=limits.MAX_MARKS_MAX,
                message=msg("between_value", min=limits.MAX_MARKS_MIN, max=limits.MAX_MARKS_MAX),
            ),
        ],
        render_kw=html_attrs(
            minimum=limits.MAX_MARKS_MIN,
            maximum=limits.MAX_MARKS_MAX,
            inputmode="numeric",
            field_type="number",
        ),
    )
    slot_creation_start = StringField(
        "Slot creation start",
        filters=[strip_filter],
        validators=[DataRequired(message=msg("required")), DateTimeLocal()],
        render_kw=html_attrs(field_type="datetime-local"),
    )
    slot_creation_end = StringField(
        "Slot creation end",
        filters=[strip_filter],
        validators=[DataRequired(message=msg("required")), DateTimeLocal()],
        render_kw=html_attrs(
            field_type="datetime-local",
            rule="after:slot_creation_start|not-after:booking_start",
        ),
    )
    booking_start = StringField(
        "Booking start",
        filters=[strip_filter],
        validators=[DataRequired(message=msg("required")), DateTimeLocal()],
        render_kw=html_attrs(field_type="datetime-local"),
    )
    booking_end = StringField(
        "Booking end",
        filters=[strip_filter],
        validators=[DataRequired(message=msg("required")), DateTimeLocal()],
        render_kw=html_attrs(
            field_type="datetime-local",
            rule="after:booking_start",
        ),
    )
    cancellation_deadline = StringField(
        "Cancellation deadline",
        filters=[strip_filter],
        validators=[Optional(), DateTimeLocal()],
        render_kw=html_attrs(
            field_type="datetime-local",
            rule="not-before:booking_start",
        ),
    )
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_courses = Course.query.filter_by(status="active").order_by(Course.code.asc()).all()
        self.course_id.choices = [(c.id, f"{c.code} - {c.name}") for c in active_courses]

    def validate(self, extra_validators=None) -> bool:
        base_ok = super().validate(extra_validators=extra_validators)
        win_ok = ExaminationWindows()(self)
        return base_ok and win_ok

    def to_service_data(self) -> dict[str, Any]:
        bk_end = windows.from_local_input(self.booking_end.data)
        cancel_dl = (
            windows.from_local_input(self.cancellation_deadline.data)
            if self.cancellation_deadline.data
            else bk_end
        )
        return {
            "course_id": self.course_id.data,
            "name": self.name.data,
            "description": self.description.data or None,
            "exam_type": self.exam_type.data,
            "duration_minutes": self.duration_minutes.data,
            "max_marks": self.max_marks.data,
            "slot_creation_start": windows.from_local_input(self.slot_creation_start.data),
            "slot_creation_end": windows.from_local_input(self.slot_creation_end.data),
            "booking_start": windows.from_local_input(self.booking_start.data),
            "booking_end": bk_end,
            "cancellation_deadline": cancel_dl,
        }

    def populate_from(self, exam: Any) -> None:
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
