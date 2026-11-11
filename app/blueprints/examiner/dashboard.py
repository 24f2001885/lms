"""
FILE PURPOSE: EXM-01 Examiner dashboard (assigned examinations, created slots, students booked, pending evaluations).
DEPENDS ON: examiner_bp (app/blueprints/examiner/__init__.py), approved_examiner_required, app/services/slot_service.py, app/services/evaluation_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /examiner/dashboard (endpoint dashboard) decorated with approved_examiner_required. Build the four counters from slot_service.examiner_dashboard_counts and evaluation_service.pending_evaluations_count for g.user.id.
2. Render examiner/dashboard.html with the four counter cards, the next five upcoming slots, and the first five pending evaluations (links to the evaluation form).
3. No queries or rules in the route beyond calling the services. Charts are added in P8.
DEBUGGING:
# print(f"[DEBUG] examiner dashboard user={g.user.id} counts={counts} pending={pending}")
OFFLINE DOCKER TEST CASES:
- The four counters match fixtures; another examiner's data never changes them.
- Pending examiner is redirected to /pending-approval; student and admin get 403.

FILE PURPOSE: EXM-01 Examiner dashboard (assigned examinations, created slots, students booked, pending evaluations).
"""
from flask import g, render_template

from app.blueprints.examiner import examiner_bp
from app.security.decorators import approved_examiner_required
from app.services import evaluation_service, slot_service


@examiner_bp.route("/dashboard")
@approved_examiner_required
def dashboard():
    examiner_id = g.user.id
    counts = slot_service.examiner_dashboard_counts(examiner_id)
    pending_count = evaluation_service.pending_evaluations_count(examiner_id)
    
    # Get first 5 pending evaluations for the list
    pending_pagination = evaluation_service.pending_bookings(examiner_id, page=1, per_page=5)
    pending_bookings_list = pending_pagination.items

    return render_template(
        "examiner/dashboard.html",
        counts=counts,
        pending_count=pending_count,
        pending_bookings=pending_bookings_list
    )