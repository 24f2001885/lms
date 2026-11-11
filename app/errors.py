"""
FILE PURPOSE: Domain exception classes with stable error codes, plus HTML error handlers for 403, 404, 500 and CSRF failures (screen PUB-07).
DEPENDS ON: app/templates/errors/*.html, flask.
PROMPT FOR LLM IMPLEMENTATION:
1. Define a base class AppError(Exception) with attributes code (str), message (str), http_status (int, default 400). Subclasses: BookingError, WindowError, PermissionDenied (http_status 403), plus AttemptError and PaymentError are NOT created now (Tier 3). Each subclass accepts code and message in its constructor and keeps the code stable for later API use.
2. Define the Tier 1 error code constants as module-level strings (TDR section 12): BOOKING_CLOSED, SLOT_FULL, DUPLICATE_BOOKING, SLOT_NOT_AVAILABLE, CANCEL_DEADLINE_PASSED, NOT_APPROVED. Do NOT define revisit_not_allowed, answer_locked, attempt_*, payment_required, invalid_signature or hold_expired (Tier 3).
3. register_error_handlers(app): handlers for 403, 404, 500 render errors/403.html, errors/404.html, errors/500.html with the correct status code. The 500 page shows only a reference id (g.request_id) and a friendly sentence, never a stack trace or exception text. Log the 500 with logger.exception including request_id.
4. Handler for AppError: flash(error.message, "danger") and redirect back to request.referrer when it is a same-host URL, otherwise to the role dashboard (or /login when anonymous); keep the HTTP status semantic by using 302. (JSON error shape arrives in P7 for /api/ paths; leave a comment where that branch will go.)
5. Handler for flask_wtf.csrf.CSRFError: flash("Your form expired. Please try again.", "warning") and redirect to a safe same-host referrer or to /login; log WARNING without the token value.
6. Handlers must be safe for anonymous users (no attribute errors when g.user is None) and must work even if the database is unavailable (do not query inside the 500 handler).
DEBUGGING:
# print(f"[DEBUG] error handler status={status} path={request.path} request_id={getattr(g, 'request_id', '-')}")
OFFLINE DOCKER TEST CASES:
- GET /no-such-page returns 404 with the custom page (contains "Page not found") and still renders the base layout.
- A student requesting /admin/dashboard gets the custom 403 page (contains "permission").
- A route that raises RuntimeError returns 500 whose body contains the request id but NOT the word "Traceback" or the exception message.
- Raising BookingError("slot_full", "This slot is full.") inside a test route flashes that message and redirects.
- Anonymous 404 and 403 pages render without a logout button.

app/errors.py - Domain exceptions and HTTP error handlers for LMS.

Defines AppError base exception and subclasses with stable error codes,
and registers custom handlers for 403, 404, 500, and CSRF token errors (PUB-07).
"""

import logging

from flask import Flask, flash, g, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

logger = logging.getLogger("lms")

# Stable Tier 1 error codes (TDR Section 12)
BOOKING_CLOSED = "booking_closed"
SLOT_FULL = "slot_full"
DUPLICATE_BOOKING = "duplicate_booking"
SLOT_NOT_AVAILABLE = "slot_not_available"
CANCEL_DEADLINE_PASSED = "cancel_deadline_passed"
NOT_APPROVED = "not_approved"


class AppError(Exception):
    """Base application exception with error code and HTTP status."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


class BookingError(AppError):
    """Raised when slot booking or cancellation rules are violated."""

    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, http_status=400)


class WindowError(AppError):
    """Raised when slot creation or booking window constraints are violated."""

    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, http_status=400)


class PermissionDenied(AppError):  # noqa: N818
    """Raised when a user lacks required role permissions for an action."""

    def __init__(self, code: str = "permission_denied", message: str = "Access denied."):
        super().__init__(code=code, message=message, http_status=403)


def register_error_handlers(app: Flask) -> None:
    """Register custom HTTP status and exception handlers on the Flask app."""

    @app.errorhandler(403)
    def handle_forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        request_id = getattr(g, "request_id", "-")
        logger.exception("Internal Server Error (500) request_id=%s: %s", request_id, e)
        # Never leak traceback or internal variables to the user
        return render_template("errors/500.html", request_id=request_id), 500

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        """Handle domain application errors by flashing message and redirecting."""
        logger.warning("Application error [%s]: %s (path=%s)", e.code, e.message, request.path)
        flash(e.message, "danger")

        # Redirect back to safe referrer or fallback to role dashboard
        from app.security.auth_helpers import get_current_user, role_dashboard_url

        user = get_current_user()
        fallback_url = role_dashboard_url(user) if user else url_for("auth.login")
        return redirect(fallback_url)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e: CSRFError):
        """Handle expired or missing CSRF tokens gracefully."""
        logger.warning("CSRF validation failure on path=%s: %s", request.path, e.description)
        flash("Your form session expired. Please try submitting again.", "warning")
        return redirect(request.referrer or url_for("auth.login"))