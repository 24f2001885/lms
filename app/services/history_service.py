"""
FILE PURPOSE: Builds per-booking history timelines with role-based redaction (PDR 5.6).
"""

import json
from typing import Any

from app.extensions import db
from app.models import AuditLog, Booking, Evaluation
from app.services import audit_service


def booking_timeline(
    booking_id: int, viewer_role: str, viewer_id: int
) -> list[dict[str, Any]] | None:
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return None

    if viewer_role == "student":
        if booking.student_id != viewer_id:
            return None
    elif viewer_role == "examiner":
        if not booking.slot or booking.slot.examiner_id != viewer_id:
            return None
    elif viewer_role != "admin":
        return None

    events: list[dict[str, Any]] = []
    events.append({"at": booking.booked_at, "label": "Booked", "detail": None})

    logs = (
        AuditLog.query.filter_by(entity_type="booking", entity_id=booking.id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )

    for log in logs:
        details = json.loads(log.details) if log.details else {}
        if log.action == audit_service.BOOKING_RESCHEDULE:
            if viewer_role == "student":
                detail = "Moved to a different slot"
            else:
                detail = (
                    f"Moved from slot #{details.get('from_slot')} to slot #{details.get('to_slot')}"
                )
            events.append({"at": log.created_at, "label": "Rescheduled", "detail": detail})

        elif log.action == audit_service.BOOKING_ADMIN_CANCEL:
            if viewer_role == "admin":
                detail = f"Cancelled by admin (Reason: {details.get('reason')})"
            else:
                detail = "Cancelled by the administration"
            events.append({"at": log.created_at, "label": "Cancelled", "detail": detail})

    # Check slot cancellation audit logs referencing this booking
    slot_logs = AuditLog.query.filter_by(entity_type="slot", action=audit_service.SLOT_CANCEL).all()
    for slog in slot_logs:
        sdetails = json.loads(slog.details) if slog.details else {}
        if booking.id in sdetails.get("booking_ids", []):
            if viewer_role in ("admin", "examiner"):
                detail = f"Slot cancelled (Reason: {sdetails.get('reason')})"
            else:
                detail = "Cancelled by the administration"
            events.append({"at": slog.created_at, "label": "Cancelled", "detail": detail})

    if booking.cancelled_at and not any(e["label"] == "Cancelled" for e in events):
        if booking.cancelled_by == booking.student_id:
            detail = "Cancelled by student"
        elif viewer_role == "admin":
            detail = "Cancelled by admin"
        else:
            detail = "Cancelled by the administration"
        events.append({"at": booking.cancelled_at, "label": "Cancelled", "detail": detail})

    evaluation = Evaluation.query.filter_by(booking_id=booking.id).first()
    if evaluation:
        if evaluation.submitted_at and viewer_role in ("admin", "examiner"):
            events.append(
                {"at": evaluation.submitted_at, "label": "Evaluation submitted", "detail": None}
            )
        if evaluation.published_at and evaluation.status == "published":
            events.append(
                {
                    "at": evaluation.published_at,
                    "label": "Result published",
                    "detail": f"Total marks: {evaluation.total_marks}",
                }
            )

    events.sort(key=lambda item: item["at"])
    return events


def examination_history_for_student(student_id: int) -> list[dict[str, Any]]:
    bookings = (
        Booking.query.filter_by(student_id=student_id).order_by(Booking.booked_at.desc()).all()
    )
    summary: dict[int, dict[str, Any]] = {}
    for b in bookings:
        eid = b.examination_id
        if eid not in summary:
            pub = Evaluation.query.filter_by(booking_id=b.id, status="published").first()
            summary[eid] = {
                "examination": b.examination,
                "last_status": b.status,
                "result_published": pub is not None,
                "last_change": b.cancelled_at or b.booked_at,
            }
        else:
            if b.status in ("booked", "completed"):
                summary[eid]["last_status"] = b.status
    return list(summary.values())
