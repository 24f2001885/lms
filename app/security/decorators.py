"""
FILE PURPOSE: Role-based access control decorators supporting both HTML redirects and JSON API responses (TDR 6).
"""

import logging
from functools import wraps

from flask import abort, flash, g, redirect, request, url_for

from app.errors import error_response

logger = logging.getLogger("lms")


def _is_api() -> bool:
    return request.path.startswith("/api/")


def login_required(f):
    """Ensure user is logged in before accessing the view."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = getattr(g, "user", None)
        if user is None:
            if _is_api():
                return error_response(
                    "unauthenticated", "Authentication is required.", status=401
                )
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))

        if not user.is_active:
            if _is_api():
                return error_response(
                    "account_inactive", "Your account has been deactivated.", status=403
                )
            logger.warning(
                "Access denied: inactive account user_id=%s path=%s", user.id, request.path
            )
            return redirect(url_for("auth.account_inactive"))

        if user.must_change_password:
            if _is_api():
                return error_response(
                    "password_change_required",
                    "You must change your temporary password before continuing.",
                    status=403,
                )
            if request.endpoint != "auth.change_password":
                return redirect(url_for("auth.change_password"))

        if user.role == "examiner" and user.approval_status != "approved":
            if _is_api():
                return error_response(
                    "not_approved",
                    "Your examiner account is pending administrator approval.",
                    status=403,
                )
            if request.endpoint != "auth.pending_approval":
                logger.info("Redirecting unapproved examiner user_id=%s to pending page", user.id)
                return redirect(url_for("auth.pending_approval"))

        return f(*args, **kwargs)

    return decorated_function


def role_required(*roles: str):
    """
    Decorator factory enforcing authentication and role-based access.

    Order of Checks (TDR Section 6):
    1. User logged in? If not -> redirect to login (or 401 unauthenticated for API)
    2. User active? If False -> redirect to account_inactive (or 403 account_inactive for API)
    3. User role in allowed roles? If not -> abort(403) (or 403 forbidden for API)
    4. must_change_password? If True -> redirect to change_password (or 403 password_change_required for API)
    5. Examiner approved? If pending/rejected -> redirect to pending_approval (or 403 not_approved for API)
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(g, "user", None)
            if user is None:
                if _is_api():
                    return error_response(
                        "unauthenticated", "Authentication is required.", status=401
                    )
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))

            if not user.is_active:
                if _is_api():
                    return error_response(
                        "account_inactive", "Your account has been deactivated.", status=403
                    )
                logger.warning(
                    "Access denied: inactive account user_id=%s path=%s", user.id, request.path
                )
                return redirect(url_for("auth.account_inactive"))

            # TDR 6: Role check comes BEFORE password change and examiner approval!
            if user.role not in roles:
                if _is_api():
                    return error_response(
                        "forbidden",
                        "You do not have permission to perform this action.",
                        status=403,
                    )
                logger.warning(
                    "Access denied (403): user_id=%s role=%s attempted to access %s (allowed: %s)",
                    user.id,
                    user.role,
                    request.path,
                    roles,
                )
                abort(403)

            if user.must_change_password:
                if _is_api():
                    return error_response(
                        "password_change_required",
                        "You must change your temporary password before continuing.",
                        status=403,
                    )
                if request.endpoint != "auth.change_password":
                    return redirect(url_for("auth.change_password"))

            if user.role == "examiner" and user.approval_status != "approved":
                if _is_api():
                    return error_response(
                        "not_approved",
                        "Your examiner account is pending administrator approval.",
                        status=403,
                    )
                if request.endpoint != "auth.pending_approval":
                    logger.info(
                        "Redirecting unapproved examiner user_id=%s to pending page", user.id
                    )
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
