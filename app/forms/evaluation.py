"""
FILE PURPOSE: Dynamic WTForms for the rubric evaluation page (EXM-08).
"""
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, StringField, TextAreaField
from wtforms.validators import Length, NumberRange, Optional


def build_evaluation_form(rubrics):
    class DynamicEvaluationForm(FlaskForm):
        remarks = TextAreaField("Remarks for the student", validators=[Optional(), Length(max=2000)])

    for r in rubrics:
        score_field = DecimalField(
            f"{r.criterion_name} (max {r.max_score})",
            places=2,
            validators=[Optional(), NumberRange(min=0, max=float(r.max_score), message=f"Score must be between 0 and {r.max_score}")]
        )
        comment_field = StringField("Comment", validators=[Optional(), Length(max=255)])
        setattr(DynamicEvaluationForm, f"score_{r.id}", score_field)
        setattr(DynamicEvaluationForm, f"comment_{r.id}", comment_field)

    return DynamicEvaluationForm


def extract_scores(form, rubrics):
    scores = {}
    comments = {}
    for r in rubrics:
        score_val = getattr(form, f"score_{r.id}").data
        comment_val = getattr(form, f"comment_{r.id}").data
        scores[r.id] = Decimal(str(score_val)) if score_val is not None and score_val != "" else None
        comments[r.id] = comment_val or ""
    return scores, comments