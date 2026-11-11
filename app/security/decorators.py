"""
FILE PURPOSE: Route decorators that enforce authentication and role-based access on EVERY request (PDR 5.2, TDR section 6, risks R-4 and R-5).
DEPENDS ON: app/security/auth_helpers.py, app/errors.py (PermissionDenied).
PROMPT FOR LLM IMPLEMENTATION:
1. login_required: if g.user is None, flash("Please log in to continue.", "warning") and redirect to auth.login. Use functools.wraps.
2. role_required(*roles): a decorator factory that first applies the login_required behaviour, then checks IN THIS ORDER: (a) user.is_active False -> redirect to auth.account_inactive; (b) user.must_change_password True -> redirect to auth.change_password; (c) user.role not in roles -> abort(403) (this is what makes "wrong-role URLs return 403"); (d) for role examiner: approval_status "pending" or "rejected" -> redirect to auth.pending_approval. Only then call the view.
3. approved_examiner_required: shortcut equal to role_required("examiner") plus an explicit re-check of approval_status == "approved" and is_active on every request (not just at login). Use it on all examiner routes later.
4. admin_required, student_required: one-line aliases built on role_required for readability.
5. Add a helper owned_or_404(query, **filters) is NOT part of this phase; ownership checks are written inside each query in P4/P5 (document this in a comment).
6. Every denial writes a WARNING log line "access denied user_id=... role=... path=..." (no personal data beyond ids).
7. The decorators must never import blueprint modules (avoid circular imports) and must not touch the database themselves; they read g.user only.
DEBUGGING:
# print(f"[DEBUG] guard path={request.path} user={getattr(g.user, 'id', None)} role={getattr(g.user, 'role', None)} roles_allowed={roles}")
OFFLINE DOCKER TEST CASES:
- Anonymous GET /admin/dashboard -> 302 to /login.
- Student GET /admin/dashboard -> 403; student GET /examiner/dashboard -> 403.
- Examiner (approved) GET /student/dashboard -> 403.
- Pending examiner GET /examiner/dashboard -> 302 to /pending-approval; after setting approval_status "approved" in the database, the very next request succeeds (flag checked per request).
- Approved examiner whose is_active is set False -> next request redirects to /account-inactive.
- Admin with must_change_password True is redirected to /change-password from /admin/dashboard.

app/security/decorators.py - Route protection decorators for RBAC in LMS.

Enforces login requirements, active status, password change mandates,
and role permissions on every protected endpoint.
"""

import logging
from functools import wraps

from flask import abort, flash, g, redirect, request, url_for

logger = logging.getLogger("lms")


def _redirect_to_login():
    flash("Please log in to continue.", "warning")
    return redirect(url_for("auth.login"))


def login_required(f):
    """Ensure user is logged in before accessing the view."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if getattr(g, "user", None) is None:
            return _redirect_to_login()
        return f(*args, **kwargs)

    return decorated_function


def role_required(*roles: str):
    """
    Decorator factory enforcing authentication and role-based access.

    Order of Checks:
    1. User logged in? If not -> redirect to login
    2. User active? If False -> redirect to account_inactive
    3. must_change_password? If True -> redirect to change_password
    4. User role in allowed roles? If not -> abort(403)
    5. Examiner approved? If pending/rejected -> redirect to pending_approval
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(g, "user", None)
            if user is None:
                return _redirect_to_login()

            if not user.is_active:
                logger.warning("Access denied: inactive account user_id=%s path=%s", user.id, request.path)
                return redirect(url_for("auth.account_inactive"))

            if user.must_change_password and request.endpoint != "auth.change_password":
                return redirect(url_for("auth.change_password"))

            if user.role not in roles:
                logger.warning(
                    "Access denied (403): user_id=%s role=%s attempted to access %s (allowed: %s)",
                    user.id,
                    user.role,
                    request.path,
                    roles,
                )
                abort(403)

            if user.role == "examiner" and user.approval_status != "approved":
                logger.info("Redirecting unapproved examiner user_id=%s to pending page", user.id)
                return redirect(url_for("auth.pending_approval"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def approved_examiner_required(f):
    """Shortcut decorator for endpoints restricted to approved examiners."""
    return role_required("examiner")(f)


def admin_required(f):
    """Shortcut decorator for endpoints restricted to administrators."""
    return role_required("admin")(f)


def student_required(f):
    """Shortcut decorator for endpoints restricted to students."""
    return role_required("student")(f)