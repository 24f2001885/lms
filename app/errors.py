"""
FILE PURPOSE: Application error hierarchy, HTTP status policy mapping, and HTML/JSON error handlers.
"""

import logging
from typing import Any

from flask import flash, g, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

logger = logging.getLogger("lms")

# Stable Tier 1 error codes (TDR Section 12)
BOOKING_CLOSED = "booking_closed"
SLOT_FULL = "slot_full"
DUPLICATE_BOOKING = "duplicate_booking"
SLOT_NOT_AVAILABLE = "slot_not_available"
CANCEL_DEADLINE_PASSED = "cancel_deadline_passed"
NOT_APPROVED = "not_approved"
SLOT_CREATION_CLOSED = "slot_creation_closed"
SLOT_HAS_BOOKINGS = "slot_has_bookings"
SLOT_HAS_EVALUATIONS = "slot_has_evaluations"
SLOT_NOT_CANCELLABLE = "slot_not_cancellable"
SLOT_STARTED = "slot_started"
BOOKING_NOT_FOUND = "booking_not_found"
BOOKING_NOT_CANCELLABLE = "booking_not_cancellable"
BOOKING_NOT_RESCHEDULABLE = "booking_not_reschedulable"
BOOKING_HAS_EVALUATION = "booking_has_evaluation"
SAME_SLOT = "same_slot"
DIFFERENT_EXAMINATION = "different_examination"
REASON_REQUIRED = "reason_required"
NOT_AN_ADMIN = "not_an_admin"
EXAMINER_OVERLAP = "examiner_overlap"
SLOT_NOT_FOUND = "slot_not_found"

ERROR_HTTP_STATUS: dict[str, int] = {
    # 400 Bad Request
    "invalid_json": 400,
    "csrf_failed": 400,
    # 401 Unauthorized
    "unauthenticated": 401,
    # 403 Forbidden
    "forbidden": 403,
    "not_approved": 403,
    "not_an_admin": 403,
    "account_inactive": 403,
    "password_change_required": 403,
    # 404 Not Found
    "not_found": 404,
    "slot_not_found": 404,
    "booking_not_found": 404,
    "examination_not_found": 404,
    # 405 Method Not Allowed
    "method_not_allowed": 405,
    # 409 Conflict (state / business rule conflicts)
    "booking_closed": 409,
    "slot_full": 409,
    "duplicate_booking": 409,
    "slot_not_available": 409,
    "cancel_deadline_passed": 409,
    "booking_not_cancellable": 409,
    "booking_not_reschedulable": 409,
    "booking_has_evaluation": 409,
    "slot_creation_closed": 409,
    "slot_edit_locked": 409,
    "slot_started": 409,
    "slot_has_bookings": 409,
    "slot_has_evaluations": 409,
    "slot_not_cancellable": 409,
    "slot_not_changeable": 409,
    "examiner_overlap": 409,
    "exam_has_bookings": 409,
    "course_in_use": 409,
    "rubric_locked": 409,
    "evaluation_locked": 409,
    # 415 Unsupported Media Type
    "unsupported_media_type": 415,
    # 429 Too Many Requests
    "too_many_requests": 429,
    # 422 Unprocessable Entity (validation / invalid values)
    "validation_error": 422,
    "slot_in_past": 422,
    "invalid_capacity": 422,
    "invalid_time_range": 422,
    "reason_required": 422,
    "total_exceeds_max": 422,
    "score_out_of_range": 422,
    "scores_incomplete": 422,
    "marks_below_existing": 422,
    "weightage_over_100": 422,
    "rubric_total_not_100": 422,
    "examiner_not_eligible": 422,
    "no_examiner_assigned": 422,
    # 500 Internal Server Error
    "internal_error": 500,
}


class AppError(Exception):
    http_status: int = 400

    def __init__(self, code: str, message: str, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        if http_status is not None:
            self.http_status = http_status


class BookingError(AppError):
    pass


class WindowError(AppError):
    pass


class PermissionDenied(AppError):  # noqa: N818
    """Raised when a user lacks required role permissions for an action."""

    def __init__(self, code: str = "permission_denied", message: str = "Access denied."):
        super().__init__(code=code, message=message, http_status=403)


class ValidationError(AppError):
    http_status = 422


def error_response(
    code: str,
    message: str,
    status: int | None = None,
    fields: dict[str, list[str]] | None = None,
):
    resolved_status = status if status is not None else ERROR_HTTP_STATUS.get(code, 400)
    err_obj: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if fields:
        err_obj["fields"] = fields
    req_id = getattr(g, "request_id", None)
    if req_id:
        err_obj["request_id"] = req_id
    return jsonify({"error": err_obj}), resolved_status


def _is_api_request() -> bool:
    return request.path.startswith("/api/")


def register_error_handlers(app) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(exc: AppError):
        if _is_api_request():
            status = ERROR_HTTP_STATUS.get(exc.code, exc.http_status)
            return error_response(exc.code, exc.message, status=status)
        logger.warning("Application error [%s]: %s (path=%s)", exc.code, exc.message, request.path)
        flash(exc.message, "danger")
        from app.security.auth_helpers import get_current_user, role_dashboard_url

        user = get_current_user()
        fallback_url = role_dashboard_url(user) if user else url_for("auth.login")
        return redirect(fallback_url)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(exc: CSRFError):
        if _is_api_request():
            return error_response(
                "csrf_failed",
                "Missing or invalid CSRF token.",
                status=400,
            )
        logger.warning(
            "CSRF validation failure on path=%s: %s",
            request.path,
            getattr(exc, "description", str(exc)),
        )
        flash("Your form session expired. Please try submitting again.", "warning")
        return redirect(request.referrer or url_for("auth.login"))

    @app.errorhandler(400)
    def handle_400(exc):
        if _is_api_request():
            return error_response("invalid_json", "Bad request.", status=400)
        return exc

    @app.errorhandler(401)
    def handle_401(exc):
        if _is_api_request():
            return error_response("unauthenticated", "Authentication is required.", status=401)
        return exc

    @app.errorhandler(403)
    def handle_403(exc):
        if _is_api_request():
            return error_response(
                "forbidden", "You do not have permission to perform this action.", status=403
            )
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_404(exc):
        if _is_api_request():
            return error_response("not_found", "The requested resource was not found.", status=404)
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def handle_405(exc):
        if _is_api_request():
            return error_response(
                "method_not_allowed", "HTTP method is not allowed for this endpoint.", status=405
            )
        return exc

    @app.errorhandler(415)
    def handle_415(exc):
        if _is_api_request():
            return error_response(
                "unsupported_media_type",
                "Content-Type must be application/json.",
                status=415,
            )
        return exc

    @app.errorhandler(429)
    def handle_429(exc):
        from flask import make_response

        retry_after = getattr(exc, "retry_after", None)
        if retry_after is None and hasattr(exc, "response") and exc.response:
            retry_after = exc.response.headers.get("Retry-After")
        if (
            retry_after is None
            and hasattr(exc, "description")
            and isinstance(exc.description, dict)
        ):
            retry_after = exc.description.get("retry_after")
        if retry_after is None:
            retry_after = 60

        try:
            retry_after = int(retry_after)
        except (ValueError, TypeError):
            retry_after = 60

        minutes = (retry_after + 59) // 60
        msg = f"Too many failed attempts. Try again in {minutes} minute(s)."

        if _is_api_request():
            resp = error_response("too_many_requests", msg, status=429)
            resp.headers["Retry-After"] = str(retry_after)
            return resp

        resp = make_response(
            render_template("errors/429.html", retry_after=retry_after, minutes=minutes),
            429,
        )
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    @app.errorhandler(500)
    def handle_500(exc):
        req_id = getattr(g, "request_id", "-")
        logger.exception("Internal Server Error (500) request_id=%s: %s", req_id, exc)
        if _is_api_request():
            return error_response(
                "internal_error",
                "An unexpected internal server error occurred.",
                status=500,
            )
        return render_template("errors/500.html", request_id=req_id), 500
