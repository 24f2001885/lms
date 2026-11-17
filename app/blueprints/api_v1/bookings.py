"""
FILE PURPOSE: /api/v1/bookings endpoints (scoped list/get, student book, student/admin cancel).
"""

from flask import g, url_for

from app.blueprints.api_v1 import api_bp
from app.blueprints.api_v1.common import (
    api_login_required,
    api_roles,
    created,
    get_int_arg,
    get_str_arg,
    iso,
    json_body,
    list_response,
    ok,
    page_args,
    translate_app_error,
)
from app.blueprints.api_v1.serializers import booking_to_dict
from app.blueprints.api_v1.validation import (
    BOOKING_CREATE_SCHEMA,
    CANCEL_SCHEMA,
    ApiValidationError,
    validate,
)
from app.errors import AppError, error_response
from app.services import api_queries, booking_engine


@api_bp.route("/bookings", methods=["GET"])
@api_login_required
def list_bookings():
    page, per_page = page_args()
    status = get_str_arg("status")
    examination_id = get_int_arg("examination_id")

    pagination = api_queries.list_bookings(
        g.user,
        status=status,
        examination_id=examination_id,
        page=page,
        per_page=per_page,
    )
    return list_response(pagination, lambda b: booking_to_dict(b, g.user))


@api_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@api_login_required
def get_booking(booking_id: int):
    booking = api_queries.get_booking(g.user, booking_id)
    if not booking:
        return error_response("booking_not_found", "Booking not found.", status=404)
    return ok(booking_to_dict(booking, g.user))


@api_bp.route("/bookings", methods=["POST"])
@api_roles("student")
def create_booking():
    cleaned = validate(json_body(), BOOKING_CREATE_SCHEMA, partial=False)
    try:
        booking = booking_engine.book_slot(g.user.id, cleaned["slot_id"])
    except AppError as exc:
        return translate_app_error(exc)

    payload = {
        "id": int(booking.id),
        "slot_id": int(booking.slot_id),
        "examination_id": int(booking.examination_id),
        "status": booking.status,
        "booked_at": iso(booking.booked_at),
    }
    location = url_for("api_v1.get_booking", booking_id=booking.id)
    return created(payload, location=location)


@api_bp.route("/bookings/<int:booking_id>", methods=["DELETE"])
@api_roles("student", "admin")
def cancel_booking(booking_id: int):
    booking = api_queries.get_booking(g.user, booking_id)
    if not booking:
        return error_response("booking_not_found", "Booking not found.", status=404)

    if g.user.role == "student":
        try:
            cancelled = booking_engine.cancel_booking(g.user.id, booking.id)
        except AppError as exc:
            return translate_app_error(exc)
        return ok({"id": int(cancelled.id), "status": cancelled.status})

    # Admin cancellation requires JSON body {"reason": "..."} (3..200 chars)
    cleaned = validate(json_body(), CANCEL_SCHEMA, partial=False)
    reason = cleaned.get("reason")
    if not reason:
        raise ApiValidationError({"reason": ["This field is required."]})

    try:
        cancelled = booking_engine.admin_cancel_booking(booking.id, g.user.id, reason)
    except AppError as exc:
        return translate_app_error(exc)

    return ok({"id": int(cancelled.id), "status": cancelled.status})
