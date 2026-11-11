"""
FILE PURPOSE: ADM-11 and ADM-12 student list and detail (read-only plus temporary password).
DEPENDS ON: admin_bp, admin_required, app/forms/common.py, app/forms/admin_actions.py, app/services/search_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/students (q filter by name, email, roll number or id; pagination) and GET /admin/students/<id> (detail, 404 if the user is not a student).
2. Detail shows profile data, all bookings of the student with status badges (any status), examination history and the audit history; empty states say "No bookings yet." (bookings appear from P5 on).
3. The temporary-password form posts to /admin/users/<id>/temporary-password (route lives in examiners.py).
4. Read-only otherwise: Admin cannot edit or delete students in this milestone.
DEBUGGING:
# print(f"[DEBUG] students list q={q!r} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Searching by roll number finds the student; paging works with 25 students.
- Detail of an examiner id returns 404.
- Detail lists cancelled and completed bookings too.

app/blueprints/admin/students.py - ADM-11 and ADM-12 student list and detail.
"""

from flask import abort, render_template, request

from app.blueprints.admin import admin_bp
from app.extensions import db
from app.forms.admin_actions import TemporaryPasswordForm
from app.forms.common import parse_page
from app.models.booking import Booking
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.security.decorators import admin_required
from app.services import audit_service


@admin_bp.route("/students", methods=["GET"])
@admin_required
def students():
    """List students with search filter (ADM-11)."""
    page, per_page = parse_page(request.args)
    q = request.args.get("q", "").strip()

    query = User.query.filter_by(role="student").outerjoin(StudentProfile)
    if q:
        query = query.filter(
            User.full_name.ilike(f"%{q}%")
            | User.email.ilike(f"%{q}%")
            | StudentProfile.roll_number.ilike(f"%{q}%")
        )

    students_page = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template("admin/students_list.html", page=students_page, q=q)


@admin_bp.route("/students/<int:student_id>", methods=["GET"])
@admin_required
def student_detail(student_id: int):
    """View student profile, booking history, and audit records (ADM-12)."""
    student = db.session.get(User, student_id)
    if not student or student.role != "student":
        abort(404)

    bookings_list = Booking.query.filter_by(student_id=student.id).order_by(Booking.id.desc()).all()
    audit_history = audit_service.history_for("user", student.id)
    temp_password_form = TemporaryPasswordForm()

    return render_template(
        "admin/student_detail.html",
        user=student,
        bookings=bookings_list,
        history=audit_history,
        temp_password_form=temp_password_form,
    )