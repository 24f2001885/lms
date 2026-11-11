"""
FILE PURPOSE: ADM-18 historical data view (PDR: Admin can view all historical data).
DEPENDS ON: admin_bp, admin_required, app/services/audit_service.py, app/models.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/history with query parameter tab = examinations | bookings | evaluations | audit (default examinations) plus filters (examination_id, student q, date range) and pagination.
2. Tabs: examinations (all, INCLUDING soft-deleted with a Deleted badge, with status and window dates); bookings (all statuses with booked_at, cancelled_at, cancelled_by, rescheduled_from); evaluations (status, total, examiner, submitted/published times); audit (action, entity, actor, time, details formatted from the JSON, newest first).
3. Read-only; no export in this milestone. Never display password hashes or temporary passwords (they are never stored in audit details anyway).
DEBUGGING:
# print(f"[DEBUG] history tab={tab} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Each of the four tabs returns 200 for Admin and 403 for other roles.
- A soft-deleted examination appears on the examinations tab with a Deleted badge.
- Audit tab shows the course.create row written during the same test.
- An unknown tab value falls back to examinations.

app/blueprints/admin/history.py - ADM-18 historical data view with four tabs.
"""

from flask import render_template, request
from sqlalchemy.orm import joinedload

from app.blueprints.admin import admin_bp
from app.forms.common import parse_page
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.evaluation import Evaluation
from app.models.examination import Examination
from app.security.decorators import admin_required


@admin_bp.route("/history", methods=["GET"])
@admin_required
def history():
    """Browse historical examinations, bookings, evaluations, and audit logs."""
    tab = request.args.get("tab", "examinations").strip().lower()
    if tab not in ("examinations", "bookings", "evaluations", "audit"):
        tab = "examinations"

    page, per_page = parse_page(request.args)

    if tab == "examinations":
        # All examinations including soft-deleted ones
        page_data = (
            Examination.query.options(joinedload(Examination.course))
            .order_by(Examination.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif tab == "bookings":
        page_data = (
            Booking.query.options(
                joinedload(Booking.student),
                joinedload(Booking.slot),
                joinedload(Booking.examination),
            )
            .order_by(Booking.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif tab == "evaluations":
        page_data = (
            Evaluation.query.options(
                joinedload(Evaluation.booking),
                joinedload(Evaluation.examiner),
            )
            .order_by(Evaluation.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:  # tab == 'audit'
        page_data = AuditLog.query.order_by(AuditLog.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return render_template("admin/history.html", tab=tab, page=page_data)