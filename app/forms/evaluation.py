"""
Dynamic WTForms for the rubric evaluation page (EXM-08): one score and one
comment per rubric criterion.
"""

from decimal import Decimal
from typing import Any

from flask_wtf import FlaskForm
from wtforms import DecimalField, StringField, TextAreaField
from wtforms.validators import Length, Optional

from app.validation import (
    DecimalPlaces,
    SafeText,
    ScoreRange,
    html_attrs,
    limits,
    msg,
    strip_filter,
)


def build_evaluation_form(rubrics: list[Any]) -> type[FlaskForm]:
    """Build a dynamic FlaskForm class with score_<id> and comment_<id> fields."""
    attrs: dict[str, Any] = {}
    for crit in rubrics:
        max_s = Decimal(str(crit.max_score))
        max_disp = f"{max_s.normalize():f}" if max_s == max_s.to_integral() else f"{max_s:.2f}"
        score_field = DecimalField(
            f"{crit.criterion_name} (max {max_disp})",
            places=limits.DECIMAL_PLACES,
            validators=[
                Optional(),
                ScoreRange(max_s, criterion_name=crit.criterion_name),
                DecimalPlaces(limits.DECIMAL_PLACES),
            ],
            render_kw=html_attrs(
                minimum=0,
                maximum=max_disp,
                step="0.01",
                inputmode="decimal",
                field_type="number",
            ),
        )
        comment_field = StringField(
            f"Comment for {crit.criterion_name}",
            filters=[strip_filter],
            validators=[
                Optional(),
                Length(
                    max=limits.COMMENT_MAX,
                    message=msg("max_length", max=limits.COMMENT_MAX),
                ),
                SafeText(),
            ],
            render_kw=html_attrs(max_len=limits.COMMENT_MAX),
        )
        attrs[f"score_{crit.id}"] = score_field
        attrs[f"comment_{crit.id}"] = comment_field

    attrs["remarks"] = TextAreaField(
        "Remarks for the student",
        filters=[strip_filter],
        validators=[
            Optional(),
            Length(
                max=limits.REMARKS_MAX,
                message=msg("max_length", max=limits.REMARKS_MAX),
            ),
            SafeText(multiline=True),
        ],
        render_kw=html_attrs(max_len=limits.REMARKS_MAX),
    )

    return type("DynamicEvaluationForm", (FlaskForm,), attrs)


def extract_scores(
    form: FlaskForm, rubrics: list[Any]
) -> tuple[dict[int, Decimal | None], dict[int, str]]:
    """Extract (scores, comments) dicts keyed by rubric_id from a validated form."""
    scores: dict[int, Decimal | None] = {}
    comments: dict[int, str] = {}
    for crit in rubrics:
        s_field = getattr(form, f"score_{crit.id}", None)
        c_field = getattr(form, f"comment_{crit.id}", None)
        if s_field is not None and s_field.data is not None and s_field.data != "":
            scores[crit.id] = Decimal(str(s_field.data)).quantize(Decimal("0.01"))
        else:
            scores[crit.id] = None
        comments[crit.id] = (c_field.data or "").strip() if c_field is not None else ""
    return scores, comments
