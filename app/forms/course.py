"""
app/forms/course.py - WTForms for creating and editing a course (ADM-03).
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

from app.models.course import COURSE_STATUSES, Course


class CourseForm(FlaskForm):
    """Form for creating and editing academic courses."""

    code = StringField(
        "Course code",
        validators=[
            DataRequired(message="Course code is required."),
            Length(min=2, max=20, message="Course code must be between 2 and 20 characters."),
            Regexp(
                r"^[A-Za-z0-9\-_]+$",
                message="Course code may only contain letters, numbers, hyphens, and underscores.",
            ),
        ],
        filters=[lambda x: x.strip().upper() if x else ""],
    )
    name = StringField(
        "Course name",
        validators=[
            DataRequired(message="Course name is required."),
            Length(min=2, max=150, message="Course name must be between 2 and 150 characters."),
        ],
        filters=[lambda x: x.strip() if x else ""],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=2000)],
        filters=[lambda x: x.strip() if x else ""],
    )
    status = SelectField(
        "Status",
        choices=[(s, s.capitalize()) for s in COURSE_STATUSES],
        default="active",
        validators=[DataRequired()],
    )
    submit = SubmitField("Save course")

    def __init__(self, course_id: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.course_id = course_id

    def validate_code(self, field):
        """Enforce case-insensitive course code uniqueness excluding current record."""
        clean_code = field.data.strip().upper()
        existing = Course.query.filter(Course.code.ilike(clean_code)).first()
        if existing and existing.id != self.course_id:
            raise ValidationError("A course with this code already exists.")
