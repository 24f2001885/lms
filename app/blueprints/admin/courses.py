"""
FILE PURPOSE: ADM-02 and ADM-03 course list, create, edit, delete.
DEPENDS ON: admin_bp, admin_required, app/forms/course.py, app/forms/common.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes (TDR 5.1): GET /admin/courses (list; filters q and status from query string; pagination), GET /admin/courses/new (empty form), POST /admin/courses (create), GET /admin/courses/<id>/edit, POST /admin/courses/<id>/update, POST /admin/courses/<id>/delete. Unknown id -> 404.
2. Each POST validates the form (or ConfirmForm for delete), calls catalog_service, flashes success ("Course created.") or the AppError message (category danger) and redirects (post/redirect/get). On form errors re-render the form with status 200.
3. Delete is offered as a danger button that opens a confirm modal (macro in macros/modals.html); the list shows an "Examinations" count column.
4. Pass actor_id=g.user.id to every service call. No rule logic in this file.
DEBUGGING:
# print(f"[DEBUG] courses {request.method} {request.path} user={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Create, edit and delete a course through the client; each step flashes the right message.
- Deleting a course with an examination flashes "Set it to inactive instead." and the course remains.
- Duplicate code shows "A course with this code already exists." on the form.
- Non-admin POSTs are rejected with 403 and change nothing.

app/blueprints/admin/courses.py - ADM-02 and ADM-03 course list, create, edit, delete.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.errors import AppError
from app.extensions import db
from app.forms.common import ConfirmForm, parse_page
from app.forms.course import CourseForm
from app.models.course import Course
from app.security.decorators import admin_required
from app.services import catalog_service


@admin_bp.route("/courses", methods=["GET"])
@admin_required
def courses():
    """List all courses with pagination and status filter (ADM-02)."""
    page, per_page = parse_page(request.args)
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Course.query
    if q:
        query = query.filter(Course.code.ilike(f"%{q}%") | Course.name.ilike(f"%{q}%"))
    if status_filter:
        query = query.filter_by(status=status_filter)

    courses_page = query.order_by(Course.code.asc()).paginate(page=page, per_page=per_page, error_out=False)
    confirm_form = ConfirmForm()
    return render_template(
        "admin/courses_list.html",
        page=courses_page,
        q=q,
        status_filter=status_filter,
        confirm_form=confirm_form,
    )


@admin_bp.route("/courses/new", methods=["GET"])
@admin_required
def new_course():
    """Display empty course creation form (ADM-03)."""
    form = CourseForm()
    return render_template("admin/course_form.html", form=form, course=None)


@admin_bp.route("/courses", methods=["POST"])
@admin_required
def create_course():
    """Handle course creation POST."""
    form = CourseForm()
    if form.validate_on_submit():
        try:
            catalog_service.create_course(
                actor_id=g.user.id,
                code=form.code.data,
                name=form.name.data,
                description=form.description.data,
                status=form.status.data,
            )
            flash("Course created.", "success")
            return redirect(url_for("admin.courses"))
        except AppError as e:
            flash(e.message, "danger")

    return render_template("admin/course_form.html", form=form, course=None), 200


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET"])
@admin_required
def edit_course(course_id: int):
    """Display course edit form."""
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)
    form = CourseForm(course_id=course.id, obj=course)
    return render_template("admin/course_form.html", form=form, course=course)


@admin_bp.route("/courses/<int:course_id>/update", methods=["POST"])
@admin_required
def update_course(course_id: int):
    """Handle course update POST."""
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)

    form = CourseForm(course_id=course.id)
    if form.validate_on_submit():
        try:
            catalog_service.update_course(
                actor_id=g.user.id,
                course_id=course.id,
                code=form.code.data,
                name=form.name.data,
                description=form.description.data,
                status=form.status.data,
            )
            flash("Course updated.", "success")
            return redirect(url_for("admin.courses"))
        except AppError as e:
            flash(e.message, "danger")

    return render_template("admin/course_form.html", form=form, course=course), 200


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@admin_required
def delete_course(course_id: int):
    """Handle course delete via ConfirmForm."""
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            catalog_service.delete_course(actor_id=g.user.id, course_id=course_id)
            flash("Course deleted.", "info")
        except AppError as e:
            flash(e.message, "danger")
    return redirect(url_for("admin.courses"))