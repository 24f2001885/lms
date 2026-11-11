"""
FILE PURPOSE: ADM-09 and ADM-10 examiner list and detail, approval lifecycle, creating examiners and setting temporary passwords (also for students).
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py, app/forms/common.py, app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examiners (filters status = pending/approved/inactive/rejected and q; pagination), GET /admin/examiners/<id> (detail), GET /admin/examiners/new and POST /admin/examiners (create approved examiner), POST /admin/examiners/<id>/approve, /reject, /deactivate, /activate, and POST /admin/users/<id>/temporary-password (works for examiners and students).
2. Filter semantics: pending = approval_status pending; approved = approved and is_active; inactive = is_active False; rejected = approval_status rejected.
3. Detail shows profile data, assigned examinations, number of slots and of booked students (counts only), the audit history of that user, and the action buttons that apply to the current state (Approve/Reject only when pending; Deactivate when active; Activate when inactive).
4. The temporary password is shown ONCE: store it in flash with category warning and a "copy now" text ("Temporary password for <name>: <password>. It will not be shown again.") and never log it.
5. Error messages from AppError are flashed; all POSTs are CSRF-protected forms.
DEBUGGING:
# print(f"[DEBUG] examiners {request.method} {request.path} target={user_id}")
OFFLINE DOCKER TEST CASES:
- Pending examiner appears under ?status=pending; Approve moves them to approved and the audit history shows the action.
- Deactivate then next request by that examiner lands on /account-inactive; Activate restores access.
- Temp password flash appears once and the user is forced to /change-password on next login.
- POST approve on a student id returns the not_an_examiner message and changes nothing.

app/blueprints/admin/examiners.py - ADM-09, 10 examiner management, approval, temp passwords.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.errors import AppError
from app.extensions import db
from app.forms.admin_actions import ExaminerCreateForm, TemporaryPasswordForm
from app.forms.common import ConfirmForm, parse_page
from app.models.booking import Booking
from app.models.examiner_profile import ExaminerProfile
from app.models.slot import ExaminationSlot
from app.models.user import User
from app.security.decorators import admin_required
from app.services import admin_service, audit_service


@admin_bp.route("/examiners", methods=["GET"])
@admin_required
def examiners():
    """List examiners with status filter (ADM-09)."""
    page, per_page = parse_page(request.args)
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all").strip().lower()

    query = User.query.filter_by(role="examiner")
    if status_filter == "pending":
        query = query.filter_by(approval_status="pending")
    elif status_filter == "approved":
        query = query.filter_by(approval_status="approved", is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)
    elif status_filter == "rejected":
        query = query.filter_by(approval_status="rejected")

    if q:
        query = query.filter(User.full_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))

    examiners_page = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    # Status counts for filter pills
    counts = {
        "all": User.query.filter_by(role="examiner").count(),
        "pending": User.query.filter_by(role="examiner", approval_status="pending").count(),
        "approved": User.query.filter_by(role="examiner", approval_status="approved", is_active=True).count(),
        "inactive": User.query.filter_by(role="examiner", is_active=False).count(),
        "rejected": User.query.filter_by(role="examiner", approval_status="rejected").count(),
    }

    confirm_form = ConfirmForm()
    return render_template(
        "admin/examiners_list.html",
        page=examiners_page,
        counts=counts,
        status=status_filter,
        q=q,
        confirm_form=confirm_form,
    )


@admin_bp.route("/examiners/new", methods=["GET", "POST"])
@admin_required
def new_examiner():
    """Directly create an approved examiner account."""
    form = ExaminerCreateForm()
    if form.validate_on_submit():
        clean_email = form.email.data.strip().lower()
        if User.query.filter_by(email=clean_email).first() is not None:
            form.email.errors.append("An account with this email already exists.")
        else:
            new_user = User(
                email=clean_email,
                full_name=form.full_name.data.strip(),
                role="examiner",
                approval_status="approved",
                is_active=True,
                must_change_password=True,
            )
            new_user.set_password(form.temporary_password.data)
            db.session.add(new_user)
            db.session.flush()

            profile = ExaminerProfile(
                user_id=new_user.id,
                contact_phone=form.contact_phone.data.strip() if form.contact_phone.data else None,
                department=form.department.data.strip() if form.department.data else None,
                designation=form.designation.data.strip() if form.designation.data else None,
                status="active",
            )
            db.session.add(profile)
            audit_service.log_action(g.user.id, audit_service.USER_EXAMINER_CREATE, "user", new_user.id, {"email": new_user.email})
            db.session.commit()
            flash(f"Examiner '{new_user.full_name}' created.", "success")
            return redirect(url_for("admin.examiner_detail", examiner_id=new_user.id))

    return render_template("admin/examiner_form.html", form=form)


@admin_bp.route("/examiners/<int:examiner_id>", methods=["GET"])
@admin_required
def examiner_detail(examiner_id: int):
    """View examiner profile, slots, and audit history (ADM-10)."""
    user = db.session.get(User, examiner_id)
    if not user or user.role != "examiner":
        abort(404)

    slots_count = ExaminationSlot.query.filter_by(examiner_id=user.id).count()
    booked_count = (
        db.session.query(Booking)
        .join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
        .filter(ExaminationSlot.examiner_id == user.id, Booking.status == "booked")
        .count()
    )
    audit_history = audit_service.history_for("user", user.id)

    temp_password_form = TemporaryPasswordForm()
    confirm_form = ConfirmForm()

    return render_template(
        "admin/examiner_detail.html",
        user=user,
        slots_count=slots_count,
        booked_count=booked_count,
        history=audit_history,
        temp_password_form=temp_password_form,
        confirm_form=confirm_form,
    )


@admin_bp.route("/examiners/<int:examiner_id>/approve", methods=["POST"])
@admin_required
def approve_examiner(examiner_id: int):
    """Approve a pending examiner."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            admin_service.approve_examiner(actor_id=g.user.id, user_id=examiner_id)
            flash("Examiner approved.", "success")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(request.referrer or url_for("admin.examiners"))


@admin_bp.route("/examiners/<int:examiner_id>/reject", methods=["POST"])
@admin_required
def reject_examiner(examiner_id: int):
    """Reject a pending examiner registration."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            admin_service.reject_examiner(actor_id=g.user.id, user_id=examiner_id)
            flash("Examiner registration rejected.", "info")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(request.referrer or url_for("admin.examiners"))


@admin_bp.route("/examiners/<int:examiner_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_examiner(examiner_id: int):
    """Deactivate an active examiner."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            admin_service.deactivate_user(actor_id=g.user.id, user_id=examiner_id)
            flash("Examiner deactivated.", "warning")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(request.referrer or url_for("admin.examiner_detail", examiner_id=examiner_id))


@admin_bp.route("/examiners/<int:examiner_id>/activate", methods=["POST"])
@admin_required
def activate_examiner(examiner_id: int):
    """Activate an inactive examiner."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            admin_service.activate_user(actor_id=g.user.id, user_id=examiner_id)
            flash("Examiner activated.", "success")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(request.referrer or url_for("admin.examiner_detail", examiner_id=examiner_id))


@admin_bp.route("/users/<int:user_id>/temporary-password", methods=["POST"])
@admin_required
def set_temporary_password(user_id: int):
    """Generate or set a temporary password for an examiner or student."""
    form = TemporaryPasswordForm()
    if form.validate_on_submit():
        try:
            target_user = db.session.get(User, user_id)
            plain_pass = admin_service.set_temporary_password(actor_id=g.user.id, user_id=user_id, new_password=form.new_password.data)
            # Displayed once in flash message
            flash(f"Temporary password for {target_user.full_name}: {plain_pass} (Copy now; it will not be shown again).", "warning")
        except AppError as e:
            flash(e.message, "danger")

    return redirect(request.referrer or url_for("admin.dashboard"))