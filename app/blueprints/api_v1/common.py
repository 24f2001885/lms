"""
FILE PURPOSE: Shared helpers for API controllers: response builders, pagination args, ISO-8601 UTC timestamps, and guards.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from flask import current_app, g, jsonify, make_response, request

from app.blueprints.api_v1.validation import ApiValidationError
from app.errors import ERROR_HTTP_STATUS, AppError, error_response
from app.security.decorators import login_required, role_required

api_login_required = login_required
api_roles = role_required


def ok(data: Any, status: int = 200, headers: dict[str, str] | None = None):
    resp = make_response(jsonify(data), status)
    if headers:
        for k, v in headers.items():
            resp.headers[k] = v
    return resp


def created(data: Any, location: str):
    return ok(data, status=201, headers={"Location": location})


def no_content():
    return make_response("", 204)


def list_response(page_obj, serializer: Callable[[Any], dict[str, Any]]):
    payload = {
        "items": [serializer(item) for item in page_obj.items],
        "page": page_obj.page,
        "per_page": page_obj.per_page,
        "total": page_obj.total,
    }
    return ok(payload, status=200)


def page_args(args=None) -> tuple[int, int]:
    if args is None:
        args = request.args
    default_pp = int(current_app.config.get("DEFAULT_PAGE_SIZE", 20))
    max_pp = int(current_app.config.get("MAX_PAGE_SIZE", 100))

    raw_page = args.get("page", "1")
    raw_per_page = args.get("per_page", str(default_pp))

    errors: dict[str, list[str]] = {}
    page_val = 1
    per_page_val = default_pp

    try:
        page_val = int(raw_page)
        if page_val < 1:
            errors["page"] = ["Must be a whole number of at least 1."]
    except (TypeError, ValueError):
        errors["page"] = ["Must be a whole number of at least 1."]

    try:
        per_page_val = int(raw_per_page)
        if per_page_val < 1:
            errors["per_page"] = ["Must be a whole number of at least 1."]
        elif per_page_val > max_pp:
            per_page_val = max_pp
    except (TypeError, ValueError):
        errors["per_page"] = ["Must be a whole number of at least 1."]

    if errors:
        raise ApiValidationError(errors)

    return page_val, per_page_val


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Timestamp must be an ISO 8601 string with a timezone.")
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError("Timestamp must include a timezone offset or Z.")
    return dt.astimezone(UTC).replace(tzinfo=None)


def json_body() -> dict[str, Any]:
    return getattr(g, "api_json", {}) or {}


def get_int_arg(name: str) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ApiValidationError({name: ["Must be a whole number."]}) from exc


def get_str_arg(name: str) -> str | None:
    raw = request.args.get(name)
    if raw is None:
        return None
    cleaned = raw.strip()
    return cleaned if cleaned else None


def translate_app_error(exc: AppError):
    status = ERROR_HTTP_STATUS.get(exc.code, exc.http_status)
    return error_response(exc.code, exc.message, status=status)
