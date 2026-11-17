"""
FILE PURPOSE: Race-free slot booking, cancellation, rescheduling, slot cancellation, and examiner reassignment engine (TDR 3.3 & P6 Hardening).

CONCURRENCY DESIGN:
1. SQLite transactions begin with BEGIN IMMEDIATE (app/extensions.py), taking the RESERVED write lock at transaction start so concurrent writers serialize cleanly behind busy_timeout=5000.
2. Public methods refresh loaded slot rows immediately inside the transaction so stale identity-map values are never trusted.
3. Capacity claims and releases use conditional guarded SQL UPDATE statements (checking status and bounds in the WHERE clause), backed by DB CHECK constraints and partial unique index uq_bookings_active_student_exam.
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.errors import BookingError
from app.extensions import db
from app.models import Booking, Evaluation, ExaminationExaminer, ExaminationSlot, User
from app.services import audit_service, hooks, windows
from app.services.hooks import HookContext

SLOT_FULL = "slot_full"
SLOT_NOT_AVAILABLE = "slot_not_available"
SLOT_NOT_FOUND = "slot_not_found"
BOOKING_CLOSED = "booking_closed"
DUPLICATE_BOOKING = "duplicate_booking"
NOT_A_STUDENT = "not_a_student"
NOT_AN_ADMIN = "not_an_admin"
BOOKING_NOT_FOUND = "booking_not_found"
BOOKING_NOT_CANCELLABLE = "booking_not_cancellable"
BOOKING_NOT_RESCHEDULABLE = "booking_not_reschedulable"
BOOKING_HAS_EVALUATION = "booking_has_evaluation"
SAME_SLOT = "same_slot"
DIFFERENT_EXAMINATION = "different_examination"
REASON_REQUIRED = "reason_required"
SLOT_NOT_CANCELLABLE = "slot_not_cancellable"
SLOT_STARTED = "slot_started"
SLOT_HAS_EVALUATIONS = "slot_has_evaluations"


def _validate_reason(reason: str | None) -> str:
    cleaned = (reason or "").strip()
    if len(cleaned) < 3 or len(cleaned) > 200:
        raise BookingError(REASON_REQUIRED, "A reason between 3 and 200 characters is required.")
    return cleaned


def _assert_active_admin(actor_id: int) -> User:
    actor = db.session.get(User, actor_id)
    if not actor or actor.role != "admin" or not actor.is_active:
        raise BookingError(NOT_AN_ADMIN, "Administrator privileges are required.")
    return actor


def _load_slot_locked(slot_id: int) -> ExaminationSlot:
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        raise BookingError(SLOT_NOT_FOUND, "Slot not found.")
    db.session.refresh(slot)
    return slot


def _claim_seat(slot: ExaminationSlot) -> None:
    res = db.session.execute(
        ExaminationSlot.__table__.update()
        .where(ExaminationSlot.id == slot.id)
        .where(ExaminationSlot.status == "available")
        .where(ExaminationSlot.booked_count < ExaminationSlot.max_capacity)
        .values(booked_count=ExaminationSlot.booked_count + 1)
    )
    if res.rowcount == 0:
        db.session.refresh(slot)
        if slot.status == "full" or slot.booked_count >= slot.max_capacity:
            raise BookingError(SLOT_FULL, "This slot is full. Please choose another slot.")
        raise BookingError(SLOT_NOT_AVAILABLE, "This slot is no longer available.")

    db.session.refresh(slot)
    if slot.booked_count >= slot.max_capacity:
        db.session.execute(
            ExaminationSlot.__table__.update()
            .where(ExaminationSlot.id == slot.id)
            .where(ExaminationSlot.status == "available")
            .where(ExaminationSlot.booked_count >= ExaminationSlot.max_capacity)
            .values(status="full")
        )
        db.session.refresh(slot)


def _release_seat(booking: Booking, cancelled_by_id: int, now: datetime) -> None:
    booking.status = "cancelled"
    booking.cancelled_at = now
    booking.cancelled_by = cancelled_by_id

    slot_id = booking.slot_id
    db.session.execute(
        ExaminationSlot.__table__.update()
        .where(ExaminationSlot.id == slot_id)
        .where(ExaminationSlot.booked_count > 0)
        .values(booked_count=ExaminationSlot.booked_count - 1)
    )
    db.session.execute(
        ExaminationSlot.__table__.update()
        .where(ExaminationSlot.id == slot_id)
        .where(ExaminationSlot.status == "full")
        .where(ExaminationSlot.booked_count < ExaminationSlot.max_capacity)
        .values(status="available")
    )


def book_slot(student_id: int, slot_id: int, now: datetime | None = None) -> Booking:
    now_time = now if now is not None else windows.now_utc()

    student = db.session.get(User, student_id)
    if not student or student.role != "student" or not student.is_active:
        raise BookingError(NOT_A_STUDENT, "User is not an active student.")

    slot = _load_slot_locked(slot_id)
    if not slot.examination:
        raise BookingError(SLOT_NOT_FOUND, "Slot not found.")

    if slot.status in ("cancelled", "completed") or slot.start_at <= now_time:
        raise BookingError(SLOT_NOT_AVAILABLE, "This slot is no longer available.")

    exam = slot.examination
    if exam.is_deleted or (exam.course and exam.course.status != "active"):
        raise BookingError(BOOKING_CLOSED, "Booking is closed.")

    windows.assert_booking_open(exam, now_time)

    existing = Booking.query.filter(
        Booking.student_id == student_id,
        Booking.examination_id == exam.id,
        Booking.status.in_(["booked", "completed"]),
    ).first()
    if existing:
        raise BookingError(DUPLICATE_BOOKING, "You already have a booking for this examination.")

    if slot.status == "full":
        raise BookingError(SLOT_FULL, "This slot is full. Please choose another slot.")

    ctx = HookContext(
        student_id=student_id,
        slot_id=slot_id,
        examination_id=exam.id,
        booking_id=None,
        actor_id=student_id,
    )
    hooks.run_pre_booking(ctx)

    _claim_seat(slot)

    booking = Booking(
        student_id=student_id,
        slot_id=slot_id,
        examination_id=exam.id,
        status="booked",
        booked_at=now_time,
    )
    db.session.add(booking)

    try:
        db.session.flush()
        audit_service.log_action(
            actor_id=student_id,
            action=audit_service.BOOKING_CREATE,
            entity_type="booking",
            entity_id=booking.id,
            details={"slot_id": slot_id, "examination_id": exam.id},
        )
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        msg = str(exc.orig).lower() if exc.orig else ""
        if "booked_count" in msg or "check" in msg:
            raise BookingError(SLOT_FULL, "This slot is full. Please choose another slot.") from exc
        raise BookingError(
            DUPLICATE_BOOKING, "You already have a booking for this examination."
        ) from exc
    except Exception:
        db.session.rollback()
        raise

    return booking


def cancel_booking(student_id: int, booking_id: int, now: datetime | None = None) -> Booking:
    now_time = now if now is not None else windows.now_utc()

    booking = Booking.query.filter_by(id=booking_id, student_id=student_id).first()
    if not booking:
        raise BookingError(BOOKING_NOT_FOUND, "Booking not found.")
    if booking.status != "booked":
        raise BookingError(BOOKING_NOT_CANCELLABLE, "This booking cannot be cancelled.")

    windows.assert_can_cancel(booking.examination, now_time)

    slot = _load_slot_locked(booking.slot_id)
    exam_id = booking.examination_id

    _release_seat(booking, cancelled_by_id=student_id, now=now_time)
    audit_service.log_action(
        actor_id=student_id,
        action=audit_service.BOOKING_CANCEL,
        entity_type="booking",
        entity_id=booking.id,
        details={"by": "student", "slot_id": slot.id},
    )
    db.session.commit()

    hooks.run_post_cancel(
        HookContext(
            student_id=student_id,
            slot_id=slot.id,
            examination_id=exam_id,
            booking_id=booking.id,
            actor_id=student_id,
        )
    )
    return booking


def reschedule_booking(
    booking_id: int, new_slot_id: int, actor_id: int, now: datetime | None = None
) -> Booking:
    now_time = now if now is not None else windows.now_utc()
    _assert_active_admin(actor_id)

    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise BookingError(BOOKING_NOT_FOUND, "Booking not found.")
    if booking.status != "booked":
        raise BookingError(BOOKING_NOT_RESCHEDULABLE, "Only active bookings can be rescheduled.")

    existing_eval = Evaluation.query.filter_by(booking_id=booking.id).first()
    if existing_eval:
        raise BookingError(
            BOOKING_HAS_EVALUATION, "Cannot reschedule a booking that already has an evaluation."
        )

    target_slot = _load_slot_locked(new_slot_id)
    old_slot = _load_slot_locked(booking.slot_id)

    if target_slot.id == old_slot.id:
        raise BookingError(SAME_SLOT, "Please choose a different slot.")
    if target_slot.examination_id != booking.examination_id:
        raise BookingError(
            DIFFERENT_EXAMINATION, "Target slot must belong to the same examination."
        )
    if target_slot.status == "full":
        raise BookingError(SLOT_FULL, "This slot is full. Please choose another slot.")
    if target_slot.status in ("cancelled", "completed") or target_slot.start_at <= now_time:
        raise BookingError(SLOT_NOT_AVAILABLE, "This slot is no longer available.")

    # Claim seat on target slot
    _claim_seat(target_slot)

    # Release seat on old slot without cancelling the booking
    db.session.execute(
        ExaminationSlot.__table__.update()
        .where(ExaminationSlot.id == old_slot.id)
        .where(ExaminationSlot.booked_count > 0)
        .values(booked_count=ExaminationSlot.booked_count - 1)
    )
    db.session.execute(
        ExaminationSlot.__table__.update()
        .where(ExaminationSlot.id == old_slot.id)
        .where(ExaminationSlot.status == "full")
        .where(ExaminationSlot.booked_count < ExaminationSlot.max_capacity)
        .values(status="available")
    )

    booking.rescheduled_from_slot_id = old_slot.id
    booking.slot_id = target_slot.id

    audit_service.log_action(
        actor_id=actor_id,
        action=audit_service.BOOKING_RESCHEDULE,
        entity_type="booking",
        entity_id=booking.id,
        details={"from_slot": old_slot.id, "to_slot": target_slot.id, "by": actor_id},
        created_at=now_time,
    )
    db.session.commit()
    db.session.refresh(old_slot)
    db.session.refresh(target_slot)
    return booking


def admin_cancel_booking(
    booking_id: int, actor_id: int, reason: str, now: datetime | None = None
) -> Booking:
    now_time = now if now is not None else windows.now_utc()
    _assert_active_admin(actor_id)
    cleaned_reason = _validate_reason(reason)

    booking = db.session.get(Booking, booking_id)
    if not booking:
        raise BookingError(BOOKING_NOT_FOUND, "Booking not found.")
    if booking.status != "booked":
        raise BookingError(BOOKING_NOT_CANCELLABLE, "This booking cannot be cancelled.")

    existing_eval = Evaluation.query.filter(
        Evaluation.booking_id == booking.id,
        Evaluation.status.in_(["submitted", "published"]),
    ).first()
    if existing_eval:
        raise BookingError(
            BOOKING_HAS_EVALUATION,
            "Cannot cancel a booking with a submitted or published evaluation.",
        )

    slot = _load_slot_locked(booking.slot_id)
    _release_seat(booking, cancelled_by_id=actor_id, now=now_time)

    audit_service.log_action(
        actor_id=actor_id,
        action=audit_service.BOOKING_ADMIN_CANCEL,
        entity_type="booking",
        entity_id=booking.id,
        details={"reason": cleaned_reason, "slot_id": slot.id},
        created_at=now_time,
    )
    db.session.commit()

    hooks.run_post_cancel(
        HookContext(
            student_id=booking.student_id,
            slot_id=slot.id,
            examination_id=booking.examination_id,
            booking_id=booking.id,
            actor_id=actor_id,
        )
    )
    return booking


def cancel_slot(slot_id: int, actor_id: int, reason: str, now: datetime | None = None) -> int:
    now_time = now if now is not None else windows.now_utc()
    actor = db.session.get(User, actor_id)
    slot = _load_slot_locked(slot_id)

    is_admin = actor and actor.role == "admin" and actor.is_active
    is_owner = (
        actor
        and actor.role == "examiner"
        and actor.is_active
        and actor.approval_status == "approved"
        and slot.examiner_id == actor.id
    )
    if not (is_admin or is_owner):
        raise BookingError(SLOT_NOT_FOUND, "Slot not found.")

    if slot.status not in ("available", "full"):
        raise BookingError(SLOT_NOT_CANCELLABLE, "This slot cannot be cancelled.")
    if slot.start_at <= now_time:
        raise BookingError(SLOT_STARTED, "Cannot cancel a slot that has already started.")

    cleaned_reason = _validate_reason(reason)

    active_bookings = Booking.query.filter_by(slot_id=slot.id, status="booked").all()
    booking_ids = [b.id for b in active_bookings]
    if booking_ids:
        blocking_eval = Evaluation.query.filter(
            Evaluation.booking_id.in_(booking_ids),
            Evaluation.status.in_(["submitted", "published"]),
        ).first()
        if blocking_eval:
            raise BookingError(
                SLOT_HAS_EVALUATIONS,
                "Cannot cancel a slot with submitted or published evaluations.",
            )

    cancelled_contexts = []
    for b in active_bookings:
        _release_seat(b, cancelled_by_id=actor_id, now=now_time)
        cancelled_contexts.append(
            HookContext(
                student_id=b.student_id,
                slot_id=slot.id,
                examination_id=slot.examination_id,
                booking_id=b.id,
                actor_id=actor_id,
            )
        )

    slot.status = "cancelled"
    slot.booked_count = 0
    db.session.flush()
    assert slot.booked_count == 0

    audit_service.log_action(
        actor_id=actor_id,
        action=audit_service.SLOT_CANCEL,
        entity_type="slot",
        entity_id=slot.id,
        details={
            "bookings_cancelled": len(active_bookings),
            "booking_ids": booking_ids,
            "reason": cleaned_reason,
        },
        created_at=now_time,
    )
    db.session.commit()

    for ctx in cancelled_contexts:
        hooks.run_post_cancel(ctx)

    return len(active_bookings)


def change_examiner(slot_id: int, new_examiner_id: int, actor_id: int) -> ExaminationSlot:
    _assert_active_admin(actor_id)
    slot = _load_slot_locked(slot_id)

    if slot.status not in ("available", "full"):
        raise BookingError(
            SLOT_NOT_AVAILABLE, "Cannot reassign examiner on a closed or cancelled slot."
        )

    if slot.examiner_id == new_examiner_id:
        raise BookingError("same_examiner", "This examiner is already assigned to the slot.")

    new_examiner = db.session.get(User, new_examiner_id)
    if (
        not new_examiner
        or new_examiner.role != "examiner"
        or not new_examiner.is_active
        or new_examiner.approval_status != "approved"
    ):
        raise BookingError("invalid_examiner", "Selected user is not an approved active examiner.")

    assigned = ExaminationExaminer.query.filter_by(
        examination_id=slot.examination_id, examiner_id=new_examiner_id
    ).first()
    if not assigned:
        raise BookingError("examiner_not_assigned", "Examiner is not assigned to this examination.")

    # Check overlapping slots for the new examiner
    overlap = ExaminationSlot.query.filter(
        ExaminationSlot.examiner_id == new_examiner_id,
        ExaminationSlot.id != slot.id,
        ExaminationSlot.status != "cancelled",
        ExaminationSlot.start_at < slot.end_at,
        ExaminationSlot.end_at > slot.start_at,
    ).first()
    if overlap:
        raise BookingError("examiner_overlap", "Examiner already has an overlapping slot.")

    old_examiner_id = slot.examiner_id
    slot.examiner_id = new_examiner_id

    audit_service.log_action(
        actor_id=actor_id,
        action=audit_service.SLOT_EXAMINER_CHANGE,
        entity_type="slot",
        entity_id=slot.id,
        details={"from": old_examiner_id, "to": new_examiner_id},
    )
    db.session.commit()
    return slot
