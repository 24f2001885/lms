"""
FILE PURPOSE: /api/v1/slots endpoints (role-scoped list/get, examiner-owned create/update/delete).
"""

from flask import g, url_for

from app.blueprints.api_v1 import api_bp
from app.blueprints.api_v1.common import (
    api_login_required,
    api_roles,
    created,
    get_int_arg,
    get_str_arg,
    json_body,
    list_response,
    no_content,
    ok,
    page_args,
    translate_app_error,
)
from app.blueprints.api_v1.serializers import slot_to_dict
from app.blueprints.api_v1.validation import SLOT_SCHEMA, SLOT_UPDATE_SCHEMA, validate
from app.errors import AppError, error_response
from app.services import api_queries, slot_service


@api_bp.route("/slots", methods=["GET"])
@api_login_required
def list_slots():
    page, per_page = page_args()
    examination_id = get_int_arg("examination_id")
    status = get_str_arg("status")

    pagination = api_queries.list_slots(
        g.user,
        examination_id=examination_id,
        status=status,
        page=page,
        per_page=per_page,
    )
    return list_response(pagination, lambda s: slot_to_dict(s, g.user))


@api_bp.route("/slots/<int:slot_id>", methods=["GET"])
@api_login_required
def get_slot(slot_id: int):
    slot = api_queries.get_slot(g.user, slot_id)
    if not slot:
        return error_response("slot_not_found", "Slot not found.", status=404)
    return ok(slot_to_dict(slot, g.user))


@api_bp.route("/slots", methods=["POST"])
@api_roles("examiner")
def create_slot():
    cleaned = validate(json_body(), SLOT_SCHEMA, partial=False)
    try:
        slot = slot_service.create_slot(
            g.user.id,
            cleaned["examination_id"],
            cleaned["start_at"],
            cleaned["end_at"],
            cleaned["max_capacity"],
        )
    except AppError as exc:
        return translate_app_error(exc)

    location = url_for("api_v1.get_slot", slot_id=slot.id)
    return created(slot_to_dict(slot, g.user), location=location)


@api_bp.route("/slots/<int:slot_id>", methods=["PUT"])
@api_roles("examiner")
def update_slot(slot_id: int):
    slot = api_queries.get_slot(g.user, slot_id)
    if not slot:
        return error_response("slot_not_found", "Slot not found.", status=404)

    cleaned = validate(json_body(), SLOT_UPDATE_SCHEMA, partial=True)
    start_at = cleaned.get("start_at", slot.start_at)
    end_at = cleaned.get("end_at", slot.end_at)
    max_capacity = cleaned.get("max_capacity", slot.max_capacity)

    try:
        updated = slot_service.update_slot(g.user.id, slot.id, start_at, end_at, max_capacity)
    except AppError as exc:
        return translate_app_error(exc)

    return ok(slot_to_dict(updated, g.user))


@api_bp.route("/slots/<int:slot_id>", methods=["DELETE"])
@api_roles("examiner")
def delete_slot(slot_id: int):
    slot = api_queries.get_slot(g.user, slot_id)
    if not slot:
        return error_response("slot_not_found", "Slot not found.", status=404)

    try:
        slot_service.delete_slot(g.user.id, slot.id)
    except AppError as exc:
        return translate_app_error(exc)

    return no_content()
