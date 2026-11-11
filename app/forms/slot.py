"""
FILE PURPOSE: WTForms for creating and editing a slot (EXM-05).
"""
from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, ValidationError
from wtforms.validators import DataRequired, NumberRange

from app.services import windows


class SlotForm(FlaskForm):
    examination_id = SelectField("Examination", coerce=int, validators=[DataRequired()])
    start_at = StringField("Start Time", validators=[DataRequired()])
    end_at = StringField("End Time", validators=[DataRequired()])
    max_capacity = IntegerField("Max Capacity", validators=[DataRequired(), NumberRange(min=1, max=500)], default=1)

    def to_service_data(self):
        try:
            start_utc = windows.from_local_input(self.start_at.data)
            end_utc = windows.from_local_input(self.end_at.data)
        except Exception as err:
            raise ValidationError("Enter a valid date and time.") from err
        return self.examination_id.data, start_utc, end_utc, self.max_capacity.data

    def populate_from(self, slot, tz_name="Asia/Kolkata"):
        self.examination_id.data = slot.examination_id
        self.start_at.data = windows.to_input_value(slot.start_at)
        self.end_at.data = windows.to_input_value(slot.end_at)
        self.max_capacity.data = slot.max_capacity

    def validate(self, extra_validators=None):
        rv = super().validate(extra_validators=extra_validators)
        if not rv:
            return False
        try:
            start_utc = windows.from_local_input(self.start_at.data)
            end_utc = windows.from_local_input(self.end_at.data)
            if start_utc >= end_utc:
                self.end_at.errors.append("End time must be after start time.")
                return False
        except Exception:
            self.start_at.errors.append("Enter a valid date and time.")
            return False
        return True