"""
FILE PURPOSE: EXM-07, EXM-08, EXM-09 pending evaluations, evaluation form, submitted evaluations.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.examiner import examiner_bp
from app.errors import AppError
from app.forms.evaluation import build_evaluation_form, extract_scores
from app.models import Evaluation, ExaminationRubric
from app.security.decorators import approved_examiner_required
from app.services import evaluation_service, slot_service


@examiner_bp.route("/evaluations")
@approved_examiner_required
def evaluations_pending():
    examiner_id = g.user.id
    examination_id = request.args.get("examination_id", type=int)
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = evaluation_service.pending_bookings(
        examiner_id, examination_id=examination_id, q=q or None, page=page
    )
    assigned_exams = slot_service.list_assigned_examinations(examiner_id)

    return render_template(
        "examiner/evaluations_pending.html",
        pagination=pagination,
        assigned_exams=assigned_exams,
        selected_exam=examination_id,
        q=q,
    )


@examiner_bp.route("/evaluations/submitted")
@approved_examiner_required
def evaluations_submitted():
    examiner_id = g.user.id
    status = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = evaluation_service.submitted_evaluations(
        examiner_id, status=status or None, page=page
    )

    return render_template(
        "examiner/evaluations_submitted.html", pagination=pagination, selected_status=status
    )


@examiner_bp.route("/bookings/<int:booking_id>/evaluate", methods=["GET", "POST"])
@approved_examiner_required
def evaluate_booking(booking_id):
    examiner_id = g.user.id
    booking = evaluation_service.get_owned_booking(examiner_id, booking_id)
    if not booking:
        abort(404)

    exam = booking.slot.examination
    rubrics = (
        ExaminationRubric.query.filter_by(examination_id=exam.id)
        .order_by(ExaminationRubric.position.asc())
        .all()
    )

    form_class = build_evaluation_form(rubrics)
    form = form_class()

    evaluation = Evaluation.query.filter_by(booking_id=booking_id).first()

    if request.method == "GET":
        ctx = evaluation_service.form_context(booking)
        form.remarks.data = ctx["remarks"]
        for r in rubrics:
            if r.id in ctx["scores_map"]:
                getattr(form, f"score_{r.id}").data = ctx["scores_map"][r.id]
            if r.id in ctx["comments_map"]:
                getattr(form, f"comment_{r.id}").data = ctx["comments_map"][r.id]

    if request.method == "POST":
        action = request.form.get("action")
        if action not in ["save_draft", "submit", "publish"]:
            return "Bad Action", 400

        if form.validate():
            scores, comments = extract_scores(form, rubrics)
            remarks = form.remarks.data
            try:
                evaluation_service.save_evaluation(
                    examiner_id, booking_id, scores, comments, remarks, action
                )
                if action == "save_draft":
                    flash("Draft saved.", "success")
                    return redirect(url_for("examiner.evaluate_booking", booking_id=booking_id))
                elif action == "submit":
                    flash("Evaluation submitted.", "success")
                elif action == "publish":
                    flash("Evaluation published to the student.", "success")
                return redirect(url_for("examiner.evaluations_pending"))
            except AppError as e:
                flash(str(e), "danger")

    ctx = evaluation_service.form_context(booking)
    return render_template(
        "examiner/evaluation_form.html",
        booking=booking,
        examination=exam,
        rubrics=rubrics,
        form=form,
        evaluation=evaluation,
        ctx=ctx,
    )
