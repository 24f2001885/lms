"""
FILE PURPOSE: WTForms for Admin booking reschedule and reason-required cancellations.
"""
from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField
from wtforms.validators import DataRequired, Length


class RescheduleForm(FlaskForm):
    new_slot_id = SelectField("New slot", coerce=int, validators=[DataRequired()])


class ReasonForm(FlaskForm):
    reason = TextAreaField(
        "Reason (kept in the audit history)",
        validators=[DataRequired(), Length(min=3, max=200)],
        filters=[lambda x: x.strip() if isinstance(x, str) else x],
    )
