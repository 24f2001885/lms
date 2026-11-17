"""
FILE PURPOSE: Admin evaluation tracking list (oversight of pending, draft, submitted and published evaluations).
"""
from flask import render_template, request

from app.blueprints.admin import admin_bp
from app.forms.common import ConfirmForm
from app.models import Examination, User
from app.security.decorators import admin_required
from app.services import evaluation_service


@admin_bp.route("/evaluations")
@admin_required
def evaluations_list():
    state = request.args.get("state", "").strip()
    examiner_id = request.args.get("examiner_id", type=int)
    examination_id = request.args.get("examination_id", type=int)
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = evaluation_service.list_evaluation_tracking(
        status=state or None,
        examiner_id=examiner_id,
        examination_id=examination_id,
        q=q or None,
        page=page,
    )
    pending_strip = evaluation_service.pending_by_examiner()
    examinations = Examination.query.filter_by(is_deleted=False).order_by(Examination.name.asc()).all()
    examiners = User.query.filter_by(role="examiner").order_by(User.full_name.asc()).all()

    return render_template(
        "admin/evaluations_list.html",
        page=pagination,
        state=state,
        examiner_id=examiner_id,
        examination_id=examination_id,
        q=q,
        pending_strip=pending_strip,
        examinations=examinations,
        examiners=examiners,
        confirm_form=ConfirmForm(),
    )
