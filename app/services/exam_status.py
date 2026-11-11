"""
FILE PURPOSE: Derives and stores the lifecycle status of an examination (draft, slot_creation, booking_open, closed, completed). Used lazily on reads in P3; the scheduled job that calls sync_all arrives in P6.
DEPENDS ON: app/services/windows.py, app/models (Examination, ExaminationSlot, Booking, Evaluation), app/services/audit_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. compute_status(exam, now=None) -> str, evaluated in THIS order (first match wins): (a) exam.is_deleted -> keep the stored status; (b) booking effectively open (windows.is_booking_open) -> "booking_open"; (c) slot creation effectively open (windows.is_slot_creation_open) -> "slot_creation"; (d) now > exam.booking_end: if the examination has at least one non-cancelled slot AND every non-cancelled slot has end_at < now AND no booking with status in (booked, completed) lacks an evaluation with status submitted or published -> "completed", otherwise "closed"; (e) otherwise "draft" (nothing opened yet, or between windows).
2. refresh_status(exam, actor_id=None, now=None) -> bool: compute, and if different from exam.status set it, write an audit row (action "exam.status_change", details {"from":..,"to":..}) via audit_service.log_action, and return True. It adds changes to the session without committing (caller commits).
3. status_label(status) returns the human text used in badges ("Slot creation", "Booking open", ...).
4. sync_all(now=None) is declared but only documented here ("implemented in P6 as the sync-exam-status job: loop non-deleted examinations, call refresh_status, mark past slots/bookings completed"); in P3 it may raise NotImplementedError.
5. Keep it side-effect free apart from the status column and the audit row.
DEBUGGING:
# print(f"[DEBUG] exam {exam.id} status {exam.status} -> {new_status} at {now}")
OFFLINE DOCKER TEST CASES:
- New exam with both switches off, now before every window: "draft".
- Switch on and inside the booking dates: "booking_open"; same dates with the switch off and now after booking_end: "closed".
- After booking_end with one past slot and one published evaluation per booking: "completed"; with one booking still unevaluated: "closed".
- No slots at all after booking_end: "closed" (never "completed").
- refresh_status twice in a row changes the status once and writes exactly one audit row.

app/services/exam_status.py - Examination lifecycle status transition service.

Calculates and synchronizes examination states (draft, slot_creation, booking_open,
closed, completed) based on timeline windows, switches, and slot evaluations.
"""

from datetime import datetime

from app.extensions import db
from app.models.booking import Booking
from app.models.examination import Examination
from app.models.slot import ExaminationSlot
from app.services.windows import now_utc


def compute_exam_status(exam: Examination, current_time: datetime | None = None) -> str:
    """
    Calculate the appropriate lifecycle status for an examination.
    """
    now = current_time or now_utc()

    if exam.is_deleted:
        return "closed"

    # If all slots have ended and all active bookings have published evaluations
    if exam.slots:
        all_slots_ended = all(slot.end_at < now for slot in exam.slots)
        if all_slots_ended:
            active_bookings = (
                Booking.query.filter_by(examination_id=exam.id, status="booked").all()
            )
            if active_bookings:
                all_evaluated = all(
                    b.evaluation is not None and b.evaluation.status in ("submitted", "published")
                    for b in active_bookings
                )
                if all_evaluated:
                    return "completed"

    # Booking open state
    if exam.booking_open and (exam.booking_start <= now <= exam.booking_end):
        return "booking_open"

    # After booking deadline has elapsed
    if now > exam.booking_end:
        return "closed"

    # Slot creation open state
    if exam.slot_creation_open and (exam.slot_creation_start <= now <= exam.slot_creation_end):
        return "slot_creation"

    return "draft"


def sync_examination_status(exam: Examination, current_time: datetime | None = None) -> str:
    """
    Compute and update the examination status, committing changes if altered.
    """
    new_status = compute_exam_status(exam, current_time)
    if exam.status != new_status:
        exam.status = new_status
        db.session.commit()
    return new_status


def sync_all_examinations(current_time: datetime | None = None) -> int:
    """
    CLI / Background sync: updates all non-deleted examinations.
    Returns the count of examinations updated.
    """
    now = current_time or now_utc()
    exams = Examination.query.filter_by(is_deleted=False).all()
    updated_count = 0

    for exam in exams:
        old_status = exam.status
        new_status = compute_exam_status(exam, now)
        if old_status != new_status:
            exam.status = new_status
            updated_count += 1

    # Also mark ended slots as completed
    slots = ExaminationSlot.query.filter(
        ExaminationSlot.end_at < now,
        ExaminationSlot.status.in_(("available", "full")),
    ).all()
    for slot in slots:
        slot.status = "completed"

    db.session.commit()
    return updated_count