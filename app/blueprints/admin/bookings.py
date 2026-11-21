"""
FILE PURPOSE: ADM-15 bookings overview (read-only in P3).
DEPENDS ON: admin_bp, admin_required, app/forms/common.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/bookings (filters status, examination_id, student q, slot_id, date range; pagination; columns: booking id, student, examination, slot time, examiner, status badge, booked_at, cancelled_at) and GET /admin/bookings/<id> (detail: all fields, evaluation status if any, audit history for the booking).
2. Read-only: the reschedule and cancel buttons are added in P6. Leave a visible but empty "Actions" area only when P6 lands; do not render placeholders now.
3. Use eager loading (joinedload/selectinload) for student, slot, examination to avoid N+1 queries; cap per_page at 100.
DEBUGGING:
# print(f"[DEBUG] bookings list filters={filters} total={page.total}")
OFFLINE DOCKER TEST CASES:
- With 30 fixtures the list pages correctly and the status filter returns only matching rows.
- Booking detail of a missing id returns 404.
- The list view issues a bounded number of SQL queries (assert with a query counter: fewer than 8 for 20 rows).

app/blueprints/admin/bookings.py - ADM-15 bookings overview (read-only in Phase P3).
"""

from flask import abort, render_template, request
from sqlalchemy.orm import joinedload

from app.blueprints.admin import admin_bp
from app.forms.common import parse_page
from app.models.booking import Booking
from app.models.examination import Examination
from app.security.decorators import admin_required
from app.services import audit_service


@admin_bp.route("/bookings", methods=["GET"])
@admin_required
def bookings():
    """List all student bookings with status filters (ADM-15)."""
    page, per_page = parse_page(request.args)
    status_filter = request.args.get("status", "").strip()
    exam_id = request.args.get("examination_id", type=int)

    # Use joinedload to prevent N+1 queries
    query = Booking.query.options(
        joinedload(Booking.student),
        joinedload(Booking.slot),
        joinedload(Booking.examination),
    )

    if status_filter:
        query = query.filter_by(status=status_filter)
    if exam_id:
        query = query.filter_by(examination_id=exam_id)

    bookings_page = query.order_by(Booking.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    exams_list = Examination.query.filter_by(is_deleted=False).all()

    return render_template(
        "admin/bookings_list.html",
        page=bookings_page,
        exams=exams_list,
        selected_status=status_filter,
        selected_exam=exam_id,
    )


@admin_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@admin_required
def booking_detail(booking_id: int):
    """View booking reservation details (read-only in P3)."""
    booking = (
        Booking.query.options(
            joinedload(Booking.student),
            joinedload(Booking.slot),
            joinedload(Booking.examination),
            joinedload(Booking.evaluation),
        )
        .filter_by(id=booking_id)
        .first()
    )
    if not booking:
        abort(404)

    audit_history = audit_service.history_for("booking", booking.id)
    return render_template("admin/booking_detail.html", booking=booking, history=audit_history)
