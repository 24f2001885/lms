"""
WTForms for creating and editing a slot (EXM-05).
"""

from typing import Any

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange

from app.services import windows
from app.validation import (
    DateTimeLocal,
    EndAfterStart,
    html_attrs,
    limits,
    msg,
    strip_filter,
)


class SlotForm(FlaskForm):
    examination_id = SelectField(
        "Examination",
        coerce=int,
        choices=(),
        validate_choice=False,
        validators=[DataRequired(message=msg("required"))],
    )
    start_at = StringField(
        "Start time",
        filters=[strip_filter],
        validators=[DataRequired(message=msg("required")), DateTimeLocal()],
        render_kw=html_attrs(field_type="datetime-local"),
    )
    end_at = StringField(
        "End time",
        filters=[strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            DateTimeLocal(),
            EndAfterStart("start_at", message=msg("end_after_start")),
        ],
        render_kw=html_attrs(
            field_type="datetime-local",
            rule="after:start_at",
        ),
    )
    max_capacity = IntegerField(
        "Maximum capacity",
        default=1,
        validators=[
            InputRequired(message=msg("required")),
            NumberRange(
                min=limits.CAPACITY_MIN,
                max=limits.CAPACITY_MAX,
                message=msg("between_value", min=limits.CAPACITY_MIN, max=limits.CAPACITY_MAX),
            ),
        ],
        render_kw=html_attrs(
            minimum=limits.CAPACITY_MIN,
            maximum=limits.CAPACITY_MAX,
            inputmode="numeric",
            field_type="number",
        ),
    )
    submit = SubmitField("Save")

    def to_service_data(self) -> tuple[int, Any, Any, int]:
        start_utc = windows.from_local_input(self.start_at.data)
        end_utc = windows.from_local_input(self.end_at.data)
        return (self.examination_id.data, start_utc, end_utc, self.max_capacity.data)

    def populate_from(self, slot: Any) -> None:
        self.examination_id.data = slot.examination_id
        self.start_at.data = windows.to_input_value(slot.start_at)
        self.end_at.data = windows.to_input_value(slot.end_at)
        self.max_capacity.data = slot.max_capacity
