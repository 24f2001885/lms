"""
FILE PURPOSE: ADM-13 slots overview and ADM-14 change slot examiner.
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py, app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/slots (filters examination_id, examiner_id, status, date_from, date_to; pagination; columns: examination, examiner, start, end, seats booked/capacity, status badge), GET /admin/slots/<id> (detail with the list of booked students), GET /admin/slots/<id>/examiner (change form) and POST /admin/slots/<id>/examiner (TDR 5.1).
2. Change form lists only eligible examiners (assigned, approved, active, not the current one). POST calls admin_service.change_slot_examiner; flash AppError messages (examiner_overlap, examiner_not_eligible, slot_not_changeable) or "Examiner changed."; redirect to the slot detail.
3. Reschedule and cancel controls are NOT here (ADM-16 and admin cancel arrive in P6).
DEBUGGING:
# print(f"[DEBUG] slot {slot.id} examiner {slot.examiner_id} -> {new_id}")
OFFLINE DOCKER TEST CASES:
- Filtering by status "full" shows only full slots; date filters use local dates converted to UTC.
- Changing to an unassigned examiner is impossible (not in the select) and a forged POST is refused with examiner_not_eligible.
- After a successful change the slot detail shows the new examiner and the audit history contains slot.examiner_change.

app/blueprints/admin/slots.py - ADM-13 slots overview and ADM-14 change slot examiner.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.errors import AppError
from app.extensions import db
from app.forms.admin_actions import ChangeSlotExaminerForm
from app.forms.common import parse_page
from app.models.examination import Examination
from app.models.examination_examiner import ExaminationExaminer
from app.models.slot import ExaminationSlot
from app.models.user import User
from app.security.decorators import admin_required
from app.services import admin_service, audit_service


@admin_bp.route("/slots", methods=["GET"])
@admin_required
def slots():
    """List all scheduled examination slots with filters (ADM-13)."""
    page, per_page = parse_page(request.args)
    exam_id = request.args.get("examination_id", type=int)
    examiner_id = request.args.get("examiner_id", type=int)
    status_filter = request.args.get("status", "").strip()

    query = ExaminationSlot.query.join(Examination)
    if exam_id:
        query = query.filter(ExaminationSlot.examination_id == exam_id)
    if examiner_id:
        query = query.filter(ExaminationSlot.examiner_id == examiner_id)
    if status_filter:
        query = query.filter(ExaminationSlot.status == status_filter)

    slots_page = query.order_by(ExaminationSlot.start_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    exams_list = Examination.query.filter_by(is_deleted=False).order_by(Examination.name.asc()).all()
    examiners_list = User.query.filter_by(role="examiner", approval_status="approved", is_active=True).all()

    return render_template(
        "admin/slots_list.html",
        page=slots_page,
        exams=exams_list,
        examiners=examiners_list,
        selected_exam=exam_id,
        selected_examiner=examiner_id,
        selected_status=status_filter,
    )


@admin_bp.route("/slots/<int:slot_id>", methods=["GET"])
@admin_required
def slot_detail(slot_id: int):
    """View slot details and booked students."""
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        abort(404)

    audit_history = audit_service.history_for("examination_slot", slot.id)
    return render_template("admin/slot_detail.html", slot=slot, history=audit_history)


@admin_bp.route("/slots/<int:slot_id>/examiner", methods=["GET", "POST"])
@admin_required
def change_slot_examiner(slot_id: int):
    """Change the assigned examiner for a slot (ADM-14)."""
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        abort(404)

    # Eligible examiners: assigned to this exam, approved, active, not the current one
    assigned_examiners = (
        User.query.join(ExaminationExaminer, User.id == ExaminationExaminer.examiner_id)
        .filter(
            ExaminationExaminer.examination_id == slot.examination_id,
            User.approval_status == "approved",
            User.is_active.is_(True),
            User.id != slot.examiner_id,
        )
        .all()
    )

    form = ChangeSlotExaminerForm()
    form.examiner_id.choices = [(e.id, f"{e.full_name} ({e.email})") for e in assigned_examiners]

    if form.validate_on_submit():
        try:
            admin_service.change_slot_examiner(actor_id=g.user.id, slot_id=slot.id, new_examiner_id=form.examiner_id.data)
            flash("Examiner changed.", "success")
            return redirect(url_for("admin.slot_detail", slot_id=slot.id))
        except AppError as e:
            flash(e.message, "danger")

    return render_template("admin/slot_change_examiner.html", slot=slot, form=form)