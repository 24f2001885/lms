"""
FILE PURPOSE: STU-01 student dashboard.
DEPENDS ON: student_bp (app/blueprints/student/__init__.py), student_required, app/services/student_queries.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/dashboard (endpoint dashboard) with student_required. Call student_queries.dashboard_data(g.user.id) and render student/dashboard.html. No other logic.
2. Charts are added in P8; leave nothing in the route for them.
DEBUGGING:
# print(f"[DEBUG] student dashboard user={g.user.id} sections={ {k: len(v) for k, v in data.items() if hasattr(v, '__len__')} }")
OFFLINE DOCKER TEST CASES:
- A new student sees five sections with empty states; after booking, Upcoming and Booked show the booking.
- Examiner and Admin get 403.

FILE PURPOSE: STU-01 student dashboard route.
"""

from flask import g, render_template

from app.blueprints.student import student_bp
from app.security.decorators import student_required
from app.services import student_queries


@student_bp.route("/dashboard")
@student_required
def dashboard():
    data = student_queries.dashboard_data(g.user.id)
    return render_template("student/dashboard.html", data=data)
