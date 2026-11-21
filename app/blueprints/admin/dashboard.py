"""
FILE PURPOSE: ADM-01 Admin dashboard (six totals; charts are added in P8).
DEPENDS ON: app/blueprints/admin/__init__.py (admin_bp), app/security/decorators.py (admin_required), app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/dashboard (endpoint dashboard), decorated with admin_required. Call admin_service.dashboard_totals() and render admin/dashboard.html with totals plus the five most recent audit rows from audit_service.recent(5).
2. Also compute pending examiner approvals (from totals) for a highlighted call-to-action card linking to /admin/examiners?status=pending.
3. No other routes here. No queries in the route itself.
DEBUGGING:
# print(f"[DEBUG] dashboard totals={totals}")
OFFLINE DOCKER TEST CASES:
- Admin gets 200 with six stat cards labelled Courses, Examinations, Examiners, Students, Slots, Bookings and numbers equal to the fixtures.
- Student and examiner get 403; anonymous 302 to /login.
- Pending approval card shows the right number and links to the filtered examiner list.

app/blueprints/admin/dashboard.py - ADM-01 Admin dashboard with six totals.
"""

from flask import render_template

from app.blueprints.admin import admin_bp
from app.security.decorators import admin_required
from app.services import admin_service, audit_service


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    """Display the 6 main metrics and recent activity."""
    totals = admin_service.dashboard_totals()
    recent_audits = audit_service.recent(limit=5)
    return render_template(
        "admin/dashboard.html",
        totals=totals,
        recent_audits=recent_audits,
    )
