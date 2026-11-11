"""
FILE PURPOSE: STUB of the "admin" blueprint so role redirects and 403 tests work in P2. P3 replaces this file's dashboard with the real Admin panel (ADM-01 onward).
DEPENDS ON: app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create admin_bp = Blueprint("admin", __name__, url_prefix="/admin") in this file (the factory imports admin_bp from here; P3 keeps this name).
2. One stub route GET "/dashboard" (endpoint dashboard) protected by admin_required, rendering auth/role_landing_stub.html with role="Admin" and phase="P3".
3. Add the comment "STUB: replaced in P3 by the real dashboard, CRUD and oversight views" at the top. No other routes, no queries.
DEBUGGING:
# print(f"[DEBUG] admin stub dashboard served to user_id={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Admin (password already changed) gets 200 from /admin/dashboard; student and examiner get 403; anonymous gets 302 to /login.

app/blueprints/admin/__init__.py - Admin blueprint stub for Phase P2.

STUB: Replaced in Phase P3 by the full administrator control panel (ADM-01 onward).
Enforces @admin_required to validate RBAC 403 matrix tests.
"""

from flask import Blueprint, render_template

from app.security.decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    """Stub admin dashboard view for Phase P2."""
    return render_template("auth/role_landing_stub.html", role="Admin", phase="P3")