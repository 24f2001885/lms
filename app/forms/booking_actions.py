"""
Small forms for Admin booking actions (reschedule, cancel with reason) and
slot cancellation with reason.
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from app.validation import SafeText, html_attrs, limits, msg, strip_filter


class RescheduleForm(FlaskForm):
    new_slot_id = SelectField(
        "New slot",
        coerce=int,
        validators=[DataRequired(message=msg("required"))],
    )
    submit = SubmitField("Move booking")


class ReasonForm(FlaskForm):
    reason = TextAreaField(
        "Reason (kept in the audit history)",
        filters=[strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            Length(
                min=limits.REASON_MIN,
                max=limits.REASON_MAX,
                message=msg("between_length", min=limits.REASON_MIN, max=limits.REASON_MAX),
            ),
            SafeText(multiline=True),
        ],
        render_kw=html_attrs(
            min_len=limits.REASON_MIN,
            max_len=limits.REASON_MAX,
        ),
    )
    submit = SubmitField("Confirm cancellation")
