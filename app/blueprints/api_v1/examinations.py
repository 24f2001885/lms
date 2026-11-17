"""
FILE PURPOSE: /api/v1/examinations endpoints (list, get, create, update, soft-delete).
"""

from flask import g, request, url_for

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
from app.blueprints.api_v1.serializers import examination_to_dict
from app.blueprints.api_v1.validation import EXAMINATION_SCHEMA, ApiValidationError, validate
from app.errors import AppError, error_response
from app.services import api_queries, catalog_service


@api_bp.route("/examinations", methods=["GET"])
@api_login_required
def list_examinations():
    page, per_page = page_args()
    course_id = get_int_arg("course_id")
    status = get_str_arg("status")
    q = get_str_arg("q")
    include_deleted = request.args.get("include_deleted", "").lower() in ("1", "true")

    try:
        pagination = api_queries.list_examinations(
            g.user,
            q=q,
            course_id=course_id,
            status=status,
            include_deleted=include_deleted,
            page=page,
            per_page=per_page,
        )
    except ValueError as exc:
        raise ApiValidationError({"status": [str(exc)]}) from exc

    return list_response(pagination, lambda e: examination_to_dict(e, g.user))


@api_bp.route("/examinations/<int:exam_id>", methods=["GET"])
@api_login_required
def get_examination(exam_id: int):
    exam = api_queries.get_examination(g.user, exam_id)
    if not exam:
        return error_response("examination_not_found", "Examination not found.", status=404)
    return ok(examination_to_dict(exam, g.user))


@api_bp.route("/examinations", methods=["POST"])
@api_roles("admin")
def create_examination():
    cleaned = validate(json_body(), EXAMINATION_SCHEMA, partial=False)
    try:
        exam = catalog_service.create_examination(g.user.id, cleaned)
    except AppError as exc:
        return translate_app_error(exc)

    location = url_for("api_v1.get_examination", exam_id=exam.id)
    return created(examination_to_dict(exam, g.user), location=location)


@api_bp.route("/examinations/<int:exam_id>", methods=["PUT"])
@api_roles("admin")
def update_examination(exam_id: int):
    exam = api_queries.get_examination(g.user, exam_id)
    if not exam or exam.is_deleted:
        return error_response("examination_not_found", "Examination not found.", status=404)

    cleaned = validate(json_body(), EXAMINATION_SCHEMA, partial=True)
    merged = {
        "course_id": cleaned.get("course_id", exam.course_id),
        "name": cleaned.get("name", exam.name),
        "description": cleaned.get("description", exam.description),
        "exam_type": cleaned.get("exam_type", exam.exam_type),
        "duration_minutes": cleaned.get("duration_minutes", exam.duration_minutes),
        "max_marks": cleaned.get("max_marks", exam.max_marks),
        "slot_creation_start": cleaned.get("slot_creation_start", exam.slot_creation_start),
        "slot_creation_end": cleaned.get("slot_creation_end", exam.slot_creation_end),
        "booking_start": cleaned.get("booking_start", exam.booking_start),
        "booking_end": cleaned.get("booking_end", exam.booking_end),
        "cancellation_deadline": cleaned.get("cancellation_deadline", exam.cancellation_deadline),
    }

    try:
        updated = catalog_service.update_examination(g.user.id, exam.id, merged)
    except AppError as exc:
        return translate_app_error(exc)

    return ok(examination_to_dict(updated, g.user))


@api_bp.route("/examinations/<int:exam_id>", methods=["DELETE"])
@api_roles("admin")
def delete_examination(exam_id: int):
    exam = api_queries.get_examination(g.user, exam_id)
    if not exam or exam.is_deleted:
        return error_response("examination_not_found", "Examination not found.", status=404)

    try:
        catalog_service.delete_examination(g.user.id, exam.id)
    except AppError as exc:
        return translate_app_error(exc)

    return no_content()
