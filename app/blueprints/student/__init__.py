"""
FILE PURPOSE: STUB of the "student" blueprint so role redirects work in P2. P5 replaces the dashboard with STU-01 onward.
DEPENDS ON: app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create student_bp = Blueprint("student", __name__, url_prefix="/student").
2. One stub route GET "/dashboard" (endpoint dashboard) protected by student_required, rendering auth/role_landing_stub.html with role="Student" and phase="P5".
3. Top comment "STUB: replaced in P5". No other routes, no queries.
DEBUGGING:
# print(f"[DEBUG] student stub dashboard served to user_id={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Student gets 200; examiner and admin get 403; anonymous gets 302 to /login.

app/blueprints/student/__init__.py - Student blueprint stub for Phase P2.

STUB: Replaced in Phase P5 by slot booking and result views (STU-01 onward).
Enforces @student_required to validate student role security.
"""

from flask import Blueprint, render_template

from app.security.decorators import student_required

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/dashboard", methods=["GET"])
@student_required
def dashboard():
    """Stub student dashboard view for Phase P2."""
    return render_template("auth/role_landing_stub.html", role="Student", phase="P5")