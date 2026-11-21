"""
app/services/audit_service.py - Append-only audit logger for LMS.

Records immutable actions without committing so it shares transaction atomicity
with the calling operation.
"""

import json
from typing import Any

from flask import has_request_context, request

from app.extensions import db
from app.models.audit_log import AuditLog

# Standard Action Constants
COURSE_CREATE = "course.create"
COURSE_UPDATE = "course.update"
COURSE_DELETE = "course.delete"

EXAM_CREATE = "exam.create"
EXAM_UPDATE = "exam.update"
EXAM_DELETE = "exam.delete"
EXAM_SLOT_CREATION_TOGGLE = "exam.slot_creation_toggle"
EXAM_BOOKING_TOGGLE = "exam.booking_toggle"
EXAM_STATUS_CHANGE = "exam.status_change"

RUBRIC_ADD = "rubric.add"
RUBRIC_UPDATE = "rubric.update"
RUBRIC_DELETE = "rubric.delete"

EXAM_EXAMINER_ASSIGN = "exam.examiner_assign"
EXAM_EXAMINER_UNASSIGN = "exam.examiner_unassign"

USER_EXAMINER_CREATE = "user.examiner_create"
USER_APPROVE = "user.approve"
USER_REJECT = "user.reject"
USER_DEACTIVATE = "user.deactivate"
USER_ACTIVATE = "user.activate"
USER_TEMP_PASSWORD = "user.temp_password"

SLOT_EXAMINER_CHANGE = "slot.examiner_change"


def log_action(
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Stage an AuditLog row without committing. Caller must commit the session.
    """
    if ip_address is None and has_request_context():
        ip_address = request.remote_addr

    details_json = None
    if details is not None:
        details_json = json.dumps(details, sort_keys=True, default=str)

    row = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details_json,
        ip_address=ip_address,
    )
    db.session.add(row)
    return row


def history_for(entity_type: str, entity_id: int) -> list[AuditLog]:
    """Return audit history for a specific entity, newest first."""
    return (
        AuditLog.query.filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(AuditLog.id.desc())
        .all()
    )


def recent(limit: int = 50) -> list[AuditLog]:
    """Return the newest audit log entries overall."""
    return AuditLog.query.order_by(AuditLog.id.desc()).limit(limit).all()
