"""
FILE PURPOSE: Defines the api_v1 blueprint (url_prefix /api/v1) and applies shared JSON/header policies.
"""

from flask import Blueprint, g, request

from app.blueprints.api_v1.validation import ApiValidationError
from app.errors import error_response

api_bp = Blueprint("api_v1", __name__)


@api_bp.before_request
def _enforce_json_request():
    # Exempt GET /docs (PUB-08 HTML page)
    if request.endpoint == "api_v1.api_docs":
        return None

    if request.method in ("POST", "PUT", "PATCH"):
        ct = (request.content_type or "").split(";")[0].strip().lower()
        if ct != "application/json":
            return error_response(
                "unsupported_media_type",
                "Content-Type must be application/json.",
                status=415,
            )
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error_response(
                "invalid_json",
                "Request body must be a valid JSON object.",
                status=400,
            )
        g.api_json = data

    elif request.method == "DELETE":
        raw = request.get_data()
        if raw:
            ct = (request.content_type or "").split(";")[0].strip().lower()
            if ct != "application/json":
                return error_response(
                    "unsupported_media_type",
                    "Content-Type must be application/json.",
                    status=415,
                )
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return error_response(
                    "invalid_json",
                    "Request body must be a valid JSON object.",
                    status=400,
                )
            g.api_json = data
        else:
            g.api_json = {}
    else:
        g.api_json = {}

    return None


@api_bp.errorhandler(ApiValidationError)
def _handle_validation_error(exc: ApiValidationError):
    return error_response(
        "validation_error",
        "Some fields are invalid.",
        status=422,
        fields=exc.fields,
    )


@api_bp.after_request
def _apply_api_headers(response):
    if response.mimetype == "application/json":
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    req_id = getattr(g, "request_id", None)
    if req_id and "X-Request-ID" not in response.headers:
        response.headers["X-Request-ID"] = req_id
    return response


from app.blueprints.api_v1 import (  # noqa: E402
    bookings,  # noqa: E402,F401
    docs,  # noqa: E402,F401
    examinations,  # noqa: E402,F401
    people,  # noqa: E402,F401
    session,  # noqa: E402,F401
    slots,  # noqa: E402,F401
    stats,  # noqa: E402,F401
)
