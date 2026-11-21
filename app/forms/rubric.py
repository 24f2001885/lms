"""
app/forms/rubric.py - WTForms for adding and editing rubric criteria (ADM-07).
"""

from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class RubricForm(FlaskForm):
    """Form for adding and editing scoring criteria."""

    criterion_name = StringField(
        "Criterion",
        validators=[
            DataRequired(message="Criterion name is required."),
            Length(min=2, max=100, message="Criterion name must be between 2 and 100 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=500)],
        filters=[lambda x: x.strip() if x else ""],
    )
    weightage = DecimalField(
        "Weightage (%)",
        places=2,
        validators=[
            DataRequired(message="Weightage is required."),
            NumberRange(
                min=Decimal("0.00"),
                max=Decimal("100.00"),
                message="Weightage must be between 0 and 100%.",
            ),
        ],
    )
    max_score = DecimalField(
        "Maximum score",
        places=2,
        validators=[
            DataRequired(message="Maximum score is required."),
            NumberRange(min=Decimal("0.01"), message="Maximum score must be greater than 0."),
        ],
    )
    position = IntegerField("Order", validators=[Optional()])
    submit = SubmitField("Save criterion")
