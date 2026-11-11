"""
FILE PURPOSE: Single writer of audit_logs rows (append-only history of important actions).
DEPENDS ON: app/models/audit_log.py, app/extensions.py, flask (request for the IP).
PROMPT FOR LLM IMPLEMENTATION:
1. log_action(actor_id, action, entity_type, entity_id=None, details=None, ip_address=None) creates an AuditLog row and adds it to db.session WITHOUT committing, so it commits or rolls back together with the business change that caused it. details is a dict serialised with json.dumps(sort_keys=True, default=str); None stays NULL. When ip_address is None and a request context exists, use request.remote_addr.
2. Define action-name constants (strings, dotted lower case) that all later phases reuse: COURSE_CREATE, COURSE_UPDATE, COURSE_DELETE, EXAM_CREATE, EXAM_UPDATE, EXAM_DELETE, EXAM_SLOT_CREATION_TOGGLE, EXAM_BOOKING_TOGGLE, RUBRIC_ADD, RUBRIC_UPDATE, RUBRIC_DELETE, EXAM_EXAMINER_ASSIGN, EXAM_EXAMINER_UNASSIGN, USER_EXAMINER_CREATE, USER_APPROVE, USER_REJECT, USER_DEACTIVATE, USER_ACTIVATE, USER_TEMP_PASSWORD, SLOT_EXAMINER_CHANGE. (Later phases add BOOKING_*, SLOT_*, EVALUATION_*, SYSTEM_* constants in their own phases.)
3. NEVER put passwords, hashes, tokens or the generated temporary password in details; log only ids, field names changed and short reasons.
4. history_for(entity_type, entity_id) returns the rows newest first (used by detail pages and the history view); recent(limit=50) returns the newest rows overall.
DEBUGGING:
# print(f"[DEBUG] audit {action} {entity_type}#{entity_id} actor={actor_id} details={details}")
OFFLINE DOCKER TEST CASES:
- log_action followed by db.session.rollback() leaves no row (not committed by the helper).
- details with a datetime value is stored as valid JSON text; details=None stores NULL.
- A request-context call stores the client IP; a call outside a request stores NULL.
- history_for returns rows newest first.

app/services/audit_service.py - Structured audit logging service for LMS.

Records immutable actions (examiner approvals, slot modifications, booking reschedules)
into the audit_logs table (TDR Section 4.1).
"""

import json
import logging
from typing import Any

from flask import g, has_request_context, request

from app.extensions import db
from app.models.audit_log import AuditLog

logger = logging.getLogger("lms")


def log_audit(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
    actor_id: int | None = None,
) -> AuditLog:
    """
    Insert an immutable audit log record.

    Args:
        action: Dotted action identifier (e.g. 'exam.booking_toggle', 'examiner.approve')
        entity_type: Entity category (e.g. 'examination', 'user', 'booking')
        entity_id: Primary key ID of the modified entity
        details: Optional dictionary of context parameters
        actor_id: User ID of the actor (falls back to g.user.id if inside a request)
    """
    # Resolve actor ID from Flask request context if not explicitly provided
    if actor_id is None and has_request_context():
        user = getattr(g, "user", None)
        actor_id = user.id if user else None

    # Resolve client IP address if available
    ip_address = None
    if has_request_context():
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()

    details_str = json.dumps(details) if details else None

    log_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details_str,
        ip_address=ip_address,
    )

    db.session.add(log_entry)
    db.session.commit()

    logger.info("AUDIT: action=%s entity=%s#%s actor=%s", action, entity_type, entity_id, actor_id)
    return log_entry