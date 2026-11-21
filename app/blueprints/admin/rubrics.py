"""
FILE PURPOSE: ADM-07 rubric management for one examination.
DEPENDS ON: admin_bp, admin_required, app/forms/rubric.py, app/forms/common.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examinations/<id>/rubrics (list + add form + running total), POST /admin/examinations/<id>/rubrics (add), GET /admin/examinations/<id>/rubrics/<rid>/edit, POST /admin/examinations/<id>/rubrics/<rid>/update, POST /admin/examinations/<id>/rubrics/<rid>/delete.
2. The page shows a progress bar of the weightage total toward 100 (text "Total 90 of 100: add 10 more" or "Total 100: ready"), the sum of max scores with the informational warning when it differs from the examination's maximum marks, and a lock notice when rubric_locked applies (evaluations exist).
3. All rules come from catalog_service; flash AppError messages; a rubric id that does not belong to the examination in the URL is a 404.
DEBUGGING:
# print(f"[DEBUG] rubrics exam={exam_id} total={total} max_total={max_total}")
OFFLINE DOCKER TEST CASES:
- Adding criteria 60 and 40 shows "Total 100: ready"; adding another 10 is rejected with weightage_over_100.
- Duplicate criterion name shows the friendly message.
- After an evaluation exists the add/edit/delete forms are hidden and POSTs are refused.
- Mismatch between sum of max scores and max marks shows a warning but does not block anything.

app/blueprints/admin/rubrics.py - ADM-07 rubric management for one examination.
"""

from decimal import Decimal

from flask import abort, flash, g, redirect, render_template, url_for

from app.blueprints.admin import admin_bp
from app.errors import AppError
from app.extensions import db
from app.forms.common import ConfirmForm
from app.forms.rubric import RubricForm
from app.models.booking import Booking
from app.models.evaluation import Evaluation
from app.models.examination import Examination
from app.models.rubric import ExaminationRubric
from app.security.decorators import admin_required
from app.services import catalog_service


@admin_bp.route("/examinations/<int:exam_id>/rubrics", methods=["GET"])
@admin_required
def rubrics(exam_id: int):
    """List rubrics for an examination and show add form (ADM-07)."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    total_weight = catalog_service.rubric_weightage_total(exam.id)
    total_max_score = sum(r.max_score for r in exam.rubrics)
    has_evaluations = (
        db.session.query(Evaluation).join(Booking).filter(Booking.examination_id == exam.id).count()
        > 0
    )

    form = RubricForm()
    confirm_form = ConfirmForm()

    return render_template(
        "admin/rubrics.html",
        exam=exam,
        rubrics=exam.rubrics,
        total=total_weight,
        total_max_score=total_max_score,
        locked=has_evaluations,
        form=form,
        confirm_form=confirm_form,
    )


@admin_bp.route("/examinations/<int:exam_id>/rubrics", methods=["POST"])
@admin_required
def add_rubric(exam_id: int):
    """Add a rubric criterion to an examination."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    form = RubricForm()
    if form.validate_on_submit():
        try:
            catalog_service.add_rubric(
                actor_id=g.user.id,
                exam_id=exam.id,
                criterion_name=form.criterion_name.data,
                description=form.description.data,
                weightage=Decimal(str(form.weightage.data)),
                max_score=Decimal(str(form.max_score.data)),
            )
            flash("Rubric criterion added.", "success")
            return redirect(url_for("admin.rubrics", exam_id=exam.id))
        except AppError as e:
            flash(e.message, "danger")

    total_weight = catalog_service.rubric_weightage_total(exam.id)
    total_max_score = sum(r.max_score for r in exam.rubrics)
    has_evaluations = (
        db.session.query(Evaluation).join(Booking).filter(Booking.examination_id == exam.id).count()
        > 0
    )

    return (
        render_template(
            "admin/rubrics.html",
            exam=exam,
            rubrics=exam.rubrics,
            total=total_weight,
            total_max_score=total_max_score,
            locked=has_evaluations,
            form=form,
            confirm_form=ConfirmForm(),
        ),
        200,
    )


@admin_bp.route("/examinations/<int:exam_id>/rubrics/<int:rubric_id>/delete", methods=["POST"])
@admin_required
def delete_rubric(exam_id: int, rubric_id: int):
    """Delete a rubric criterion."""
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if not rubric or rubric.examination_id != exam_id:
        abort(404)

    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            catalog_service.delete_rubric(actor_id=g.user.id, rubric_id=rubric.id)
            flash("Rubric criterion deleted.", "info")
        except AppError as e:
            flash(e.message, "danger")

    return redirect(url_for("admin.rubrics", exam_id=exam_id))
