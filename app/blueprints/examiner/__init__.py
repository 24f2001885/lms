"""
FILE PURPOSE: STUB of the "examiner" blueprint so the pending-approval gate and 403 tests work in P2. P4 replaces the dashboard with EXM-01 onward.
DEPENDS ON: app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner").
2. One stub route GET "/dashboard" (endpoint dashboard) protected by approved_examiner_required, rendering auth/role_landing_stub.html with role="Examiner" and phase="P4".
3. Top comment "STUB: replaced in P4". No other routes, no queries.
DEBUGGING:
# print(f"[DEBUG] examiner stub dashboard served to user_id={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Approved examiner gets 200; pending examiner is redirected to /pending-approval; rejected examiner too; student and admin get 403.
- Deactivated (is_active False) examiner is redirected to /account-inactive on the next request.

app/blueprints/examiner/__init__.py - Examiner blueprint stub for Phase P2.

STUB: Replaced in Phase P4 by slot management and evaluation views (EXM-01 onward).
Enforces @approved_examiner_required to test pending approval locks.
"""

from flask import Blueprint, render_template

from app.security.decorators import approved_examiner_required

examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner")


@examiner_bp.route("/dashboard", methods=["GET"])
@approved_examiner_required
def dashboard():
    """Stub examiner dashboard view for Phase P2."""
    return render_template("auth/role_landing_stub.html", role="Examiner", phase="P4")