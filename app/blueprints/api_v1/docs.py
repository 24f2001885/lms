"""
FILE PURPOSE: PUB-08 Public API reference page at GET /api/v1/docs with drift guard.
"""

from typing import Any

from flask import render_template

from app.blueprints.api_v1 import api_bp

API_REFERENCE: list[dict[str, Any]] = [
    {
        "method": "GET",
        "path": "/api/v1/session",
        "roles": "Any authenticated user",
        "query": [],
        "body": "none",
        "success": "200 {user, csrf_token}",
        "errors": ["unauthenticated", "account_inactive"],
    },
    {
        "method": "GET",
        "path": "/api/v1/examinations",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": ["course_id", "status", "q", "include_deleted", "page", "per_page"],
        "body": "none",
        "success": "200 {items, page, per_page, total}",
        "errors": ["unauthenticated", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/examinations/<int:exam_id>",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": [],
        "body": "none",
        "success": "200 Examination object",
        "errors": ["unauthenticated", "examination_not_found"],
    },
    {
        "method": "POST",
        "path": "/api/v1/examinations",
        "roles": "Admin",
        "query": [],
        "body": [
            "course_id",
            "name",
            "description",
            "exam_type",
            "duration_minutes",
            "max_marks",
            "slot_creation_start",
            "slot_creation_end",
            "booking_start",
            "booking_end",
            "cancellation_deadline",
        ],
        "success": "201 Examination object + Location",
        "errors": ["forbidden", "csrf_failed", "validation_error", "invalid_time_range"],
    },
    {
        "method": "PUT",
        "path": "/api/v1/examinations/<int:exam_id>",
        "roles": "Admin",
        "query": [],
        "body": ["Partial Examination fields"],
        "success": "200 Examination object",
        "errors": [
            "forbidden",
            "examination_not_found",
            "validation_error",
            "marks_below_existing",
        ],
    },
    {
        "method": "DELETE",
        "path": "/api/v1/examinations/<int:exam_id>",
        "roles": "Admin",
        "query": [],
        "body": "none",
        "success": "204 No Content",
        "errors": ["forbidden", "examination_not_found", "exam_has_bookings"],
    },
    {
        "method": "GET",
        "path": "/api/v1/slots",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": ["examination_id", "status", "page", "per_page"],
        "body": "none",
        "success": "200 {items, page, per_page, total}",
        "errors": ["unauthenticated", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/slots/<int:slot_id>",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": [],
        "body": "none",
        "success": "200 Slot object",
        "errors": ["unauthenticated", "slot_not_found"],
    },
    {
        "method": "POST",
        "path": "/api/v1/slots",
        "roles": "Approved Examiner",
        "query": [],
        "body": ["examination_id", "start_at", "end_at", "max_capacity"],
        "success": "201 Slot object + Location",
        "errors": [
            "forbidden",
            "not_approved",
            "slot_creation_closed",
            "examiner_overlap",
            "validation_error",
        ],
    },
    {
        "method": "PUT",
        "path": "/api/v1/slots/<int:slot_id>",
        "roles": "Owning Approved Examiner",
        "query": [],
        "body": ["start_at", "end_at", "max_capacity"],
        "success": "200 Slot object",
        "errors": [
            "forbidden",
            "slot_not_found",
            "slot_edit_locked",
            "slot_has_bookings",
            "validation_error",
        ],
    },
    {
        "method": "DELETE",
        "path": "/api/v1/slots/<int:slot_id>",
        "roles": "Owning Approved Examiner",
        "query": [],
        "body": "none",
        "success": "204 No Content",
        "errors": ["forbidden", "slot_not_found", "slot_edit_locked"],
    },
    {
        "method": "GET",
        "path": "/api/v1/bookings",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": ["status", "examination_id", "page", "per_page"],
        "body": "none",
        "success": "200 {items, page, per_page, total}",
        "errors": ["unauthenticated", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/bookings/<int:booking_id>",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": [],
        "body": "none",
        "success": "200 Booking object",
        "errors": ["unauthenticated", "booking_not_found"],
    },
    {
        "method": "POST",
        "path": "/api/v1/bookings",
        "roles": "Student",
        "query": [],
        "body": ["slot_id"],
        "success": "201 {id, slot_id, examination_id, status, booked_at} + Location",
        "errors": [
            "forbidden",
            "slot_not_found",
            "slot_full",
            "duplicate_booking",
            "booking_closed",
        ],
    },
    {
        "method": "DELETE",
        "path": "/api/v1/bookings/<int:booking_id>",
        "roles": "Student (own booking) or Admin (with reason)",
        "query": [],
        "body": ["reason (required for Admin, 3-200 chars)"],
        "success": "200 {id, status: 'cancelled'}",
        "errors": ["forbidden", "booking_not_found", "cancel_deadline_passed", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/examiners",
        "roles": "Admin",
        "query": ["status", "q", "page", "per_page"],
        "body": "none",
        "success": "200 {items, page, per_page, total}",
        "errors": ["forbidden", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/students",
        "roles": "Admin",
        "query": ["q", "page", "per_page"],
        "body": "none",
        "success": "200 {items, page, per_page, total}",
        "errors": ["forbidden", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/stats/summary",
        "roles": "Admin",
        "query": [],
        "body": "none",
        "success": "200 {courses, examinations, examiners, students, slots, bookings}",
        "errors": ["forbidden"],
    },
    {
        "method": "GET",
        "path": "/api/v1/charts/bookings-by-day",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": ["days"],
        "body": "none",
        "success": '200 {"labels": [...], "series": [{"name", "data"}]}',
        "errors": ["unauthenticated", "forbidden", "validation_error"],
    },
    {
        "method": "GET",
        "path": "/api/v1/charts/booking-status",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": [],
        "body": "none",
        "success": '200 {"labels": [...], "series": [{"name", "data"}]}',
        "errors": ["unauthenticated", "forbidden"],
    },
    {
        "method": "GET",
        "path": "/api/v1/charts/participants-by-slot",
        "roles": "Admin, Examiner",
        "query": [],
        "body": "none",
        "success": '200 {"labels": [...], "series": [{"name", "data"}]}',
        "errors": ["unauthenticated", "forbidden"],
    },
    {
        "method": "GET",
        "path": "/api/v1/charts/examiner-workload",
        "roles": "Admin, Examiner",
        "query": [],
        "body": "none",
        "success": '200 {"labels": [...], "series": [{"name", "data"}]}',
        "errors": ["unauthenticated", "forbidden"],
    },
    {
        "method": "GET",
        "path": "/api/v1/charts/examination-completion",
        "roles": "Admin, Examiner",
        "query": [],
        "body": "none",
        "success": '200 {"labels": [...], "series": [{"name", "data"}]}',
        "errors": ["unauthenticated", "forbidden"],
    },
    {
        "method": "GET",
        "path": "/api/v1/charts/results",
        "roles": "Admin, Examiner, Student (role-scoped)",
        "query": [],
        "body": "none",
        "success": '200 {"labels": [...], "series": [{"name", "data"}]}',
        "errors": ["unauthenticated", "forbidden"],
    },
]

STATUS_POLICY_TABLE = [
    (
        400,
        "invalid_json / csrf_failed",
        "Malformed JSON body, non-object JSON payload, or missing/invalid X-CSRFToken.",
    ),
    (401, "unauthenticated", "No active session cookie; sign in at /login first."),
    (
        403,
        "forbidden / not_approved",
        "Authenticated user lacks the required role, is inactive, or is an unapproved examiner.",
    ),
    (404, "not_found", "Resource does not exist or is outside the caller's role visibility scope."),
    (405, "method_not_allowed", "HTTP verb is not supported on this resource."),
    (
        409,
        "conflict",
        "Business rule conflict (slot full, duplicate booking, window closed, edit locked).",
    ),
    (
        415,
        "unsupported_media_type",
        "POST/PUT/PATCH request missing Content-Type: application/json.",
    ),
    (
        422,
        "validation_error",
        "Field type/range validation failed or invalid query parameter value.",
    ),
    (500, "internal_error", "Unexpected server error; includes request_id for audit lookup."),
]


def undocumented_endpoints(app) -> list[tuple[str, str]]:
    documented = {(item["method"], item["path"]) for item in API_REFERENCE}
    missing: list[tuple[str, str]] = []
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/v1"):
            continue
        if rule.rule == "/api/v1/docs":
            continue
        for method in rule.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            if (method, rule.rule) not in documented:
                missing.append((method, rule.rule))
    return sorted(missing)


@api_bp.route("/docs", methods=["GET"])
def api_docs():
    return render_template(
        "api/docs.html",
        endpoints=API_REFERENCE,
        status_table=STATUS_POLICY_TABLE,
    )
