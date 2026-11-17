"""
WTForms for creating and editing a course (ADM-03).
"""

from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.models.course import COURSE_STATUSES, Course
from app.validation import (
    CourseCodeChars,
    SafeText,
    html_attrs,
    limits,
    msg,
    strip_filter,
    upper_strip_filter,
)


class CourseForm(FlaskForm):
    code = StringField(
        "Course code",
        filters=[upper_strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            Length(
                min=limits.COURSE_CODE_MIN,
                max=limits.COURSE_CODE_MAX,
                message=msg(
                    "between_length", min=limits.COURSE_CODE_MIN, max=limits.COURSE_CODE_MAX
                ),
            ),
            CourseCodeChars(),
        ],
        render_kw=html_attrs(
            min_len=limits.COURSE_CODE_MIN,
            max_len=limits.COURSE_CODE_MAX,
            pattern=limits.COURSE_CODE_PATTERN,
            title=limits.COURSE_CODE_TITLE,
        ),
    )
    name = StringField(
        "Course name",
        filters=[strip_filter],
        validators=[
            DataRequired(message=msg("required")),
            Length(
                min=limits.COURSE_NAME_MIN,
                max=limits.COURSE_NAME_MAX,
                message=msg(
                    "between_length", min=limits.COURSE_NAME_MIN, max=limits.COURSE_NAME_MAX
                ),
            ),
            SafeText(),
        ],
        render_kw=html_attrs(
            min_len=limits.COURSE_NAME_MIN,
            max_len=limits.COURSE_NAME_MAX,
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
    status = SelectField(
        "Status",
        choices=[(s, s.capitalize()) for s in COURSE_STATUSES],
        default="active",
        validators=[DataRequired(message=msg("required"))],
    )
    submit = SubmitField("Save")

    def __init__(self, course_id: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.course_id = course_id

    def validate_code(self, field) -> None:
        if not field.data:
            return
        q = Course.query.filter(func.upper(Course.code) == field.data.upper())
        if self.course_id is not None:
            q = q.filter(Course.id != self.course_id)
        if q.first() is not None:
            raise ValidationError(msg("course_code_taken"))
