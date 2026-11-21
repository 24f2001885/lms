"""
app/services/exam_status.py - Examination lifecycle status derivation service.

Evaluates draft, slot_creation, booking_open, closed, and completed states.
"""

from datetime import datetime

from app.models.booking import Booking
from app.models.examination import Examination
from app.services import audit_service, windows


def compute_status(exam: Examination, now: datetime | None = None) -> str:
    """
    Derive the current status of an examination following strict priority:
    (a) is_deleted -> keep existing status
    (b) booking open -> 'booking_open'
    (c) slot creation open -> 'slot_creation'
    (d) now > booking_end:
        - if >= 1 non-cancelled slot AND all slots ended AND all active bookings evaluated -> 'completed'
        - otherwise -> 'closed'
    (e) otherwise -> 'draft'
    """
    if exam.is_deleted:
        return exam.status

    current = now or windows.now_utc()

    if windows.is_booking_open(exam, current):
        return "booking_open"

    if windows.is_slot_creation_open(exam, current):
        return "slot_creation"

    if current > exam.booking_end:
        active_slots = [s for s in exam.slots if s.status != "cancelled"]
        if active_slots and all(s.end_at < current for s in active_slots):
            active_bookings = Booking.query.filter(
                Booking.examination_id == exam.id,
                Booking.status.in_(("booked", "completed")),
            ).all()
            if active_bookings:
                all_evaluated = all(
                    b.evaluation is not None and b.evaluation.status in ("submitted", "published")
                    for b in active_bookings
                )
                if all_evaluated:
                    return "completed"
        return "closed"

    return "draft"


def refresh_status(
    exam: Examination, actor_id: int | None = None, now: datetime | None = None
) -> bool:
    """
    Recalculate status and stage an audit log if it changed. Returns True if changed.
    """
    current = now or windows.now_utc()
    new_status = compute_status(exam, current)

    if new_status != exam.status:
        old_status = exam.status
        exam.status = new_status
        audit_service.log_action(
            actor_id=actor_id,
            action=audit_service.EXAM_STATUS_CHANGE,
            entity_type="examination",
            entity_id=exam.id,
            details={"from": old_status, "to": new_status},
        )
        return True
    return False


def status_label(status: str) -> str:
    """Return human-readable badge text for an examination status."""
    labels = {
        "draft": "Draft",
        "slot_creation": "Slot Creation",
        "booking_open": "Booking Open",
        "closed": "Closed",
        "completed": "Completed",
    }
    return labels.get(status, status.capitalize())


def sync_all(now: datetime | None = None) -> None:
    """Scheduled job runner placeholder (implemented fully in P6)."""
    raise NotImplementedError("sync_all is implemented in Phase P6.")
