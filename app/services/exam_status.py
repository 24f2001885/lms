"""
app/services/exam_status.py - Examination lifecycle status derivation service.

Evaluates draft, slot_creation, booking_open, closed, and completed states.
"""

from datetime import datetime

from app.extensions import db
from app.models.booking import Booking
from app.models.examination import Examination
from app.models.slot import ExaminationSlot
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
            active_bookings = (
                Booking.query.filter(
                    Booking.examination_id == exam.id,
                    Booking.status.in_(("booked", "completed")),
                ).all()
            )
            if active_bookings:
                all_evaluated = all(
                    b.evaluation is not None and b.evaluation.status in ("submitted", "published")
                    for b in active_bookings
                )
                if all_evaluated:
                    return "completed"
        return "closed"

    return "draft"


def refresh_status(exam: Examination, actor_id: int | datetime | None = None, now: datetime | None = None) -> bool:
    """
    Recalculate status and stage an audit log if it changed. Returns True if changed.
    Supports either refresh_status(exam, actor_id, now) or refresh_status(exam, now).
    """
    if isinstance(actor_id, datetime):
        now = actor_id
        actor_id = None

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


def sync_all(now: datetime | None = None) -> dict[str, int]:
    """Synchronize slot/booking completion and examination statuses idempotently."""
    now_time = now if now is not None else windows.now_utc()
    exams = Examination.query.filter_by(is_deleted=False).all()

    summary = {
        "examinations": len(exams),
        "slots_completed": 0,
        "bookings_completed": 0,
        "status_changes": 0,
    }

    for exam in exams:
        slots_done = 0
        bookings_done = 0
        old_status = exam.status

        past_slots = ExaminationSlot.query.filter(
            ExaminationSlot.examination_id == exam.id,
            ExaminationSlot.end_at < now_time,
            ExaminationSlot.status.in_(["available", "full"]),
        ).all()

        for slot in past_slots:
            slot.status = "completed"
            slots_done += 1

            active_bookings = Booking.query.filter_by(slot_id=slot.id, status="booked").all()
            for booking in active_bookings:
                booking.status = "completed"
                bookings_done += 1

        new_status = compute_status(exam, now_time)
        status_changed = new_status != old_status
        if status_changed:
            exam.status = new_status

        if slots_done > 0 or bookings_done > 0 or status_changed:
            summary["slots_completed"] += slots_done
            summary["bookings_completed"] += bookings_done
            if status_changed:
                summary["status_changes"] += 1

            audit_service.log_action(
                actor_id=None,
                action=audit_service.SYSTEM_STATUS_SYNC,
                entity_type="examination",
                entity_id=exam.id,
                details={
                    "slots_completed": slots_done,
                    "bookings_completed": bookings_done,
                    "status": new_status,
                },
            )
            db.session.commit()

    return summary