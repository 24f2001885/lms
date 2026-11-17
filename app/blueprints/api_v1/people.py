"""
FILE PURPOSE: Admin-only read endpoints for /api/v1/examiners and /api/v1/students.
"""

from app.blueprints.api_v1 import api_bp
from app.blueprints.api_v1.common import (
    api_roles,
    get_str_arg,
    list_response,
    page_args,
)
from app.blueprints.api_v1.serializers import examiner_to_dict, student_to_dict
from app.blueprints.api_v1.validation import ApiValidationError
from app.services import api_queries


@api_bp.route("/examiners", methods=["GET"])
@api_roles("admin")
def list_examiners():
    page, per_page = page_args()
    status = get_str_arg("status")
    q = get_str_arg("q")

    try:
        pagination = api_queries.list_examiners(q=q, status=status, page=page, per_page=per_page)
    except ValueError as exc:
        raise ApiValidationError({"status": [str(exc)]}) from exc

    return list_response(pagination, examiner_to_dict)


@api_bp.route("/students", methods=["GET"])
@api_roles("admin")
def list_students():
    page, per_page = page_args()
    q = get_str_arg("q")

    pagination = api_queries.list_students(q=q, page=page, per_page=per_page)
    return list_response(pagination, student_to_dict)
