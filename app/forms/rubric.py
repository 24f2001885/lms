"""
WTForms for adding and editing a rubric criterion (ADM-07).
"""

from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

from app.validation import (
    DecimalPlaces,
    SafeText,
    html_attrs,
    limits,
    msg,
    strip_filter,
)


class RubricForm(FlaskForm):
    criterion_name = StringField(
        "Criterion",
        filters=[strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            Length(
                min=limits.CRITERION_MIN,
                max=limits.CRITERION_MAX,
                message=msg("between_length", min=limits.CRITERION_MIN, max=limits.CRITERION_MAX),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(
            min_len=limits.CRITERION_MIN,
            max_len=limits.CRITERION_MAX,
        ),
    )
    description = TextAreaField(
        "Description",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.RUBRIC_DESCRIPTION_MAX,
                message=msg("max_length", max=limits.RUBRIC_DESCRIPTION_MAX),
            ),
            SafeText(multiline=True),
        ],
        render_kw=html_attrs(max_len=limits.RUBRIC_DESCRIPTION_MAX),
    )
    weightage = DecimalField(
        "Weightage (%)",
        places=limits.DECIMAL_PLACES,
        validators=[
            InputRequired(message=msg("required")),
            NumberRange(
                min=limits.WEIGHTAGE_MIN,
                max=limits.WEIGHTAGE_MAX,
                message=msg("between_value", min=limits.WEIGHTAGE_MIN, max=limits.WEIGHTAGE_MAX),
            ),
            DecimalPlaces(limits.DECIMAL_PLACES),
        ],
        render_kw=html_attrs(
            minimum=limits.WEIGHTAGE_MIN,
            maximum=limits.WEIGHTAGE_MAX,
            step="0.01",
            inputmode="decimal",
            field_type="number",
        ),
    )
    max_score = DecimalField(
        "Maximum score",
        places=limits.DECIMAL_PLACES,
        validators=[
            InputRequired(message=msg("required")),
            NumberRange(
                min=Decimal(limits.MAX_SCORE_MIN),
                message=msg("min_value", min=limits.MAX_SCORE_MIN),
            ),
            DecimalPlaces(limits.DECIMAL_PLACES),
        ],
        render_kw=html_attrs(
            minimum=limits.MAX_SCORE_MIN,
            step="0.01",
            inputmode="decimal",
            field_type="number",
        ),
    )
    position = IntegerField(
        "Position",
        validators=[
            Optional(),
            NumberRange(min=0, message=msg("min_value", min=0)),
        ],
        render_kw=html_attrs(
            minimum=0,
            inputmode="numeric",
            field_type="number",
        ),
    )
    submit = SubmitField("Save criterion")
