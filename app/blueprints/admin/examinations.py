"""
FILE PURPOSE: ADM-04, ADM-05, ADM-06, ADM-08 examination list, create/edit, detail with timeline switches and the assigned-examiners panel.
DEPENDS ON: admin_bp, admin_required, app/forms/examination.py, app/forms/admin_actions.py, app/forms/common.py, app/services/catalog_service.py, app/services/windows.py, app/services/exam_status.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examinations (list; filters q, course_id, exam_type, status, show_deleted; pagination), GET /admin/examinations/new, POST /admin/examinations (create), GET /admin/examinations/<id> (detail), GET /admin/examinations/<id>/edit, POST /admin/examinations/<id>/update, POST /admin/examinations/<id>/delete, POST /admin/examinations/<id>/slot-creation/toggle, POST /admin/examinations/<id>/booking/toggle, POST /admin/examinations/<id>/examiners (assign), POST /admin/examinations/<id>/examiners/<examiner_id>/remove.
2. Detail page (ADM-06) loads: the examination with course, rubric summary (total weightage with an OK / needs-100 indicator), assigned examiners panel (ADM-08), slot count and booking counts, and windows.window_state(exam) to render the TWO timeline switches with their status text and the reason line. Call exam_status.refresh_status(exam) and commit before rendering so the badge is current (lazy status).
3. Toggle routes read the desired state from a hidden field "open" ("1" or "0") inside a ConfirmForm-style form, call catalog_service.toggle_*; errors (no_examiner_assigned, rubric_total_not_100) are flashed and the page redirects back to the detail view.
4. Assign form (AssignExaminerForm) is populated in the view with approved, active, not-yet-assigned examiners; if there are none show a muted message and a link to /admin/examiners?status=pending.
5. Datetimes shown with the localdt filter; forms pre-filled via populate_from.
6. Edit/delete errors are flashed with the AppError message; no rule logic in the route.
DEBUGGING:
# print(f"[DEBUG] exam {exam.id} status={exam.status} state={windows.window_state(exam)}")
OFFLINE DOCKER TEST CASES:
- Admin setup flow: create exam -> add rubric -> assign examiner -> open slot creation -> page shows "Open" with the dates; closing sets it back to "Closed".
- Opening booking with rubrics totalling 90 flashes the rubric_total_not_100 message and the switch stays closed.
- Detail page for a soft-deleted examination is reachable by Admin and shows a "Deleted" badge; the list hides it unless show_deleted is on.
- Remove-examiner refused while the examiner has a slot, with the examiner_has_slots message.

app/blueprints/admin/examinations.py - ADM-04, 05, 06, 08 examination management.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.errors import AppError
from app.extensions import db
from app.forms.admin_actions import AssignExaminerForm
from app.forms.common import ConfirmForm, parse_page
from app.forms.examination import ExaminationForm
from app.forms.rubric import RubricForm
from app.models.course import Course
from app.models.examination import Examination
from app.models.user import User
from app.security.decorators import admin_required
from app.services import catalog_service, exam_status, windows


@admin_bp.route("/examinations", methods=["GET"])
@admin_required
def examinations():
    """List examinations with filters (ADM-04)."""
    page, per_page = parse_page(request.args)
    q = request.args.get("q", "").strip()
    course_id = request.args.get("course_id", type=int)
    exam_type = request.args.get("exam_type", "").strip()
    status_filter = request.args.get("status", "").strip()
    show_deleted = request.args.get("show_deleted") == "1"

    query = Examination.query
    if not show_deleted:
        query = query.filter_by(is_deleted=False)
    if q:
        query = query.filter(Examination.name.ilike(f"%{q}%"))
    if course_id:
        query = query.filter_by(course_id=course_id)
    if exam_type:
        query = query.filter_by(exam_type=exam_type)
    if status_filter:
        query = query.filter_by(status=status_filter)

    exams_page = query.order_by(Examination.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Compute window_state for each exam in page
    now = windows.now_utc()
    window_states = {exam.id: windows.window_state(exam, now) for exam in exams_page.items}

    courses_list = Course.query.filter_by(status="active").order_by(Course.code.asc()).all()
    confirm_form = ConfirmForm()

    return render_template(
        "admin/examinations_list.html",
        page=exams_page,
        courses=courses_list,
        window_states=window_states,
        confirm_form=confirm_form,
        show_deleted=show_deleted,
    )


@admin_bp.route("/examinations/new", methods=["GET"])
@admin_required
def new_examination():
    """Render empty examination creation form (ADM-05)."""
    form = ExaminationForm()
    return render_template("admin/examination_form.html", form=form, exam=None)


@admin_bp.route("/examinations", methods=["POST"])
@admin_required
def create_examination():
    """Handle examination creation POST."""
    form = ExaminationForm()
    if form.validate_on_submit():
        data = form.to_service_data()
        if not any(field.errors for field in form):
            try:
                exam = catalog_service.create_examination(actor_id=g.user.id, data=data)
                flash(f"Examination '{exam.name}' created.", "success")
                return redirect(url_for("admin.examination_detail", exam_id=exam.id))
            except AppError as e:
                flash(e.message, "danger")

    return render_template("admin/examination_form.html", form=form, exam=None), 200


@admin_bp.route("/examinations/<int:exam_id>", methods=["GET"])
@admin_required
def examination_detail(exam_id: int):
    """Examination detail view with timeline switches and rubrics (ADM-06)."""
    exam = db.session.get(Examination, exam_id)
    if not exam:
        abort(404)

    # Lazy status refresh on view
    now = windows.now_utc()
    if exam_status.refresh_status(exam, actor_id=g.user.id, now=now):
        db.session.commit()

    w_state = windows.window_state(exam, now)
    total_weightage = catalog_service.rubric_weightage_total(exam.id)

    # Prepare examiner assign form
    assigned_ids = [a.examiner_id for a in exam.examiner_links]
    available_examiners = (
        User.query.filter(
            User.role == "examiner",
            User.approval_status == "approved",
            User.is_active.is_(True),
            ~User.id.in_(assigned_ids) if assigned_ids else True,
        )
        .order_by(User.full_name.asc())
        .all()
    )
    assign_form = AssignExaminerForm()
    assign_form.examiner_id.choices = [
        (e.id, f"{e.full_name} ({e.email})") for e in available_examiners
    ]

    confirm_form = ConfirmForm()
    rubric_form = RubricForm()

    return render_template(
        "admin/examination_detail.html",
        exam=exam,
        window_state=w_state,
        total_weightage=total_weightage,
        assign_form=assign_form,
        confirm_form=confirm_form,
        rubric_form=rubric_form,
    )


@admin_bp.route("/examinations/<int:exam_id>/edit", methods=["GET"])
@admin_required
def edit_examination(exam_id: int):
    """Render examination edit form."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)
    form = ExaminationForm()
    form.populate_from(exam)
    return render_template("admin/examination_form.html", form=form, exam=exam)


@admin_bp.route("/examinations/<int:exam_id>/update", methods=["POST"])
@admin_required
def update_examination(exam_id: int):
    """Handle examination update POST."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    form = ExaminationForm()
    if form.validate_on_submit():
        data = form.to_service_data()
        if not any(field.errors for field in form):
            try:
                catalog_service.update_examination(actor_id=g.user.id, exam_id=exam.id, data=data)
                flash(f"Examination '{exam.name}' updated.", "success")
                return redirect(url_for("admin.examination_detail", exam_id=exam.id))
            except AppError as e:
                flash(e.message, "danger")

    return render_template("admin/examination_form.html", form=form, exam=exam), 200


@admin_bp.route("/examinations/<int:exam_id>/delete", methods=["POST"])
@admin_required
def delete_examination(exam_id: int):
    """Handle examination soft-deletion."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            catalog_service.delete_examination(actor_id=g.user.id, exam_id=exam_id)
            flash("Examination deleted.", "info")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(url_for("admin.examinations"))


@admin_bp.route("/examinations/<int:exam_id>/slot-creation/toggle", methods=["POST"])
@admin_required
def toggle_slot_creation(exam_id: int):
    """Toggle slot creation switch."""
    open_state = request.form.get("open") in ("1", "true", "True")
    try:
        catalog_service.toggle_slot_creation(
            actor_id=g.user.id, exam_id=exam_id, open_state=open_state
        )
        flash(f"Slot creation {'opened' if open_state else 'closed'}.", "success")
    except AppError as e:
        flash(e.message, "danger")
    return redirect(url_for("admin.examination_detail", exam_id=exam_id))


@admin_bp.route("/examinations/<int:exam_id>/booking/toggle", methods=["POST"])
@admin_required
def toggle_booking(exam_id: int):
    """Toggle student booking switch."""
    open_state = request.form.get("open") in ("1", "true", "True")
    try:
        catalog_service.toggle_booking(actor_id=g.user.id, exam_id=exam_id, open_state=open_state)
        flash(f"Student booking {'opened' if open_state else 'closed'}.", "success")
    except AppError as e:
        flash(e.message, "danger")
    return redirect(url_for("admin.examination_detail", exam_id=exam_id))


@admin_bp.route("/examinations/<int:exam_id>/examiners", methods=["POST"])
@admin_required
def assign_examiner(exam_id: int):
    """Assign an examiner to an examination."""
    form = AssignExaminerForm()
    # Populate choices dynamically
    available_examiners = User.query.filter_by(
        role="examiner", approval_status="approved", is_active=True
    ).all()
    form.examiner_id.choices = [(e.id, e.full_name) for e in available_examiners]

    if form.validate_on_submit():
        try:
            catalog_service.assign_examiner(
                actor_id=g.user.id, exam_id=exam_id, examiner_id=form.examiner_id.data
            )
            flash("Examiner assigned.", "success")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(url_for("admin.examination_detail", exam_id=exam_id))


@admin_bp.route("/examinations/<int:exam_id>/examiners/<int:examiner_id>/remove", methods=["POST"])
@admin_required
def remove_examiner(exam_id: int, examiner_id: int):
    """Remove assigned examiner from an examination."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            catalog_service.unassign_examiner(
                actor_id=g.user.id, exam_id=exam_id, examiner_id=examiner_id
            )
            flash("Examiner removed from examination.", "info")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(url_for("admin.examination_detail", exam_id=exam_id))
