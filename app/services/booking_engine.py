"""
FILE PURPOSE: The flagship feature: booking and cancelling slots with capacity, duplicate and window rules (TDR section 3). P5 delivers book_slot and cancel_booking in their FINAL algorithmic form; P6 adds the write-lock transaction, reschedule, admin cancel, slot cancel and change examiner to this same module.
DEPENDS ON: app/models (Booking, ExaminationSlot, Examination, User), app/services/windows.py, app/services/hooks.py, app/services/audit_service.py, app/errors.py (BookingError and the code constants), app/extensions.py (db).
PROMPT FOR LLM IMPLEMENTATION:
1. Invariants to protect (TDR 3.1): 0 <= booked_count <= max_capacity; at most one booking with status booked or completed per (student, examination); booking only while the booking window is open; slot status becomes full exactly when booked_count == max_capacity and returns to available when a seat is freed (unless the slot is cancelled or completed).
2. Clock: always windows.now_utc() through the module (or the optional now argument for tests). Never datetime.now().
3. book_slot(student_id, slot_id, now=None) -> Booking. Do everything in ONE transaction and commit once at the end. Check IN THIS ORDER, each failure raises BookingError(code, message) and rolls back: (a) student exists, role student, is_active ("not_a_student"); (b) slot exists, joined to its examination ("slot_not_found"); (c) slot.status: "full" -> SLOT_FULL ("This slot is full. Please choose another slot."), "cancelled" or "completed" -> SLOT_NOT_AVAILABLE ("This slot is no longer available."); (d) slot.start_at must be later than now, otherwise SLOT_NOT_AVAILABLE; (e) the examination is not soft-deleted and its course is active, then windows.assert_booking_open(exam, now) (BOOKING_CLOSED, "Booking is closed."); (f) hooks.run_pre_booking(HookContext(...)); (g) duplicate check: any booking of this student for this EXAMINATION with status booked or completed -> DUPLICATE_BOOKING ("You already have a booking for this examination."); (h) capacity claim with ONE conditional UPDATE: set booked_count = booked_count + 1 where id = slot_id and status = "available" and booked_count < max_capacity; if the affected row count is 0, reload the slot and raise SLOT_FULL or SLOT_NOT_AVAILABLE accordingly (a guarded UPDATE, not read-then-write, so a stale read can never overbook); (i) insert Booking(student_id, slot_id, examination_id copied from the slot, status "booked", booked_at = now); (j) if the claimed count now equals max_capacity run a second conditional UPDATE setting status = "full" where id = slot_id and status = "available" and booked_count = max_capacity; (k) audit_service.log_action(student_id, BOOKING_CREATE, "booking", booking.id, {...}); commit.
4. IntegrityError mapping (second line of defence): on commit/flush rollback and translate: the partial unique index uq_bookings_active_student_exam -> DUPLICATE_BOOKING; the CHECK on booked_count -> SLOT_FULL; anything else is re-raised.
5. cancel_booking(student_id, booking_id, now=None) -> Booking: booking must exist and belong to the student ("booking_not_found"), status must be "booked" ("booking_not_cancellable": completed and already-cancelled bookings cannot be cancelled), windows.assert_can_cancel(exam, now) (CANCEL_DEADLINE_PASSED, "The cancellation deadline has passed."). Then call the internal helper below, audit BOOKING_CANCEL with {"by": "student"}, commit, and AFTER the commit call hooks.run_post_cancel.
6. Internal helper _release_seat(booking, cancelled_by_id, now): set booking.status "cancelled", cancelled_at, cancelled_by; run a guarded UPDATE decrementing the slot (booked_count = booked_count - 1 where id = slot_id and booked_count > 0); then a guarded UPDATE setting the slot status back to "available" where id = slot_id and status = "full" and booked_count < max_capacity (a cancelled or completed slot is never reopened). P6 reuses this helper for admin cancel and slot cancel; keep it free of window checks and commits.
7. All user-visible messages are short, plain English (TDR 12). Error code constants come from app/errors.py; do not invent new codes besides slot_not_found, not_a_student, booking_not_found, booking_not_cancellable (define them as constants next to the others if app/errors.py lacks them).
8. No Flask request/flash/redirect usage in this module; the engine is shared by HTML routes now and the JSON API in P7.
DEBUGGING:
# print(f"[DEBUG] book_slot student={student_id} slot={slot_id} booked_count_before={before} rowcount={result.rowcount} status={slot.status}")
OFFLINE DOCKER TEST CASES:
- Happy path: booking row created with status "booked", slot.booked_count 1, audit row booking.create.
- Booking the last seat flips the slot to "full"; the next student gets slot_full; after one cancellation the slot is "available" again and a booking succeeds.
- Closed window (switch off, before start, after end) -> booking_closed; slot already started -> slot_not_available; cancelled slot -> slot_not_available.
- Same student, same examination, second slot -> duplicate_booking; after cancelling, re-booking works.
- Cancelling after the deadline -> cancel_deadline_passed and booked_count unchanged; cancelling a completed or already cancelled booking -> booking_not_cancellable.
- Cancelling someone else's booking -> booking_not_found.
- A veto from a registered pre-booking hook leaves the database untouched.
- Each failure case leaves booked_count and booking rows exactly as before (rollback proof).
- The guarded UPDATE prevents overbooking even if booked_count was read stale (simulate by calling the UPDATE path directly with booked_count = max_capacity).

FILE PURPOSE: Flagship engine for booking and cancelling slots with capacity, duplicate, and window rules (TDR 3.3).
"""

from sqlalchemy.exc import IntegrityError

from app.errors import BookingError
from app.extensions import db
from app.models import Booking, ExaminationSlot, User
from app.services import audit_service, hooks, windows
from app.services.hooks import HookContext


def _release_seat(booking, cancelled_by_id, now=None):
    now_time = now if now else windows.now_utc()
    booking.status = "cancelled"
    booking.cancelled_at = now_time
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


def book_slot(student_id, slot_id, now=None):
    now_time = now if now else windows.now_utc()

    student = User.query.get(student_id)
    if not student or student.role != "student" or not student.is_active:
        raise BookingError("not_a_student", "User is not an active student.")

    slot = ExaminationSlot.query.get(slot_id)
    if not slot or not slot.examination:
        raise BookingError("slot_not_found", "Slot not found.")

    if slot.status == "full":
        raise BookingError("slot_full", "This slot is full. Please choose another slot.")
    if slot.status in ["cancelled", "completed"]:
        raise BookingError("slot_not_available", "This slot is no longer available.")

    if slot.start_at <= now_time:
        raise BookingError("slot_not_available", "This slot is no longer available.")

    exam = slot.examination
    if exam.is_deleted or (exam.course and not exam.course.is_active):
        raise BookingError("booking_closed", "Booking is closed.")

    windows.assert_booking_open(exam, now_time)

    ctx = HookContext(
        student_id=student_id, slot_id=slot_id, examination_id=exam.id, actor_id=student_id
    )
    hooks.run_pre_booking(ctx)

    existing = Booking.query.filter(
        Booking.student_id == student_id,
        Booking.examination_id == exam.id,
        Booking.status.in_(["booked", "completed"]),
    ).first()
    if existing:
        raise BookingError("duplicate_booking", "You already have a booking for this examination.")

    res = db.session.execute(
        ExaminationSlot.__table__.update()
        .where(ExaminationSlot.id == slot_id)
        .where(ExaminationSlot.status == "available")
        .where(ExaminationSlot.booked_count < ExaminationSlot.max_capacity)
        .values(booked_count=ExaminationSlot.booked_count + 1)
    )

    if res.rowcount == 0:
        db.session.refresh(slot)
        if slot.status == "full" or slot.booked_count >= slot.max_capacity:
            raise BookingError("slot_full", "This slot is full. Please choose another slot.")
        raise BookingError("slot_not_available", "This slot is no longer available.")

    booking = Booking(
        student_id=student_id,
        slot_id=slot_id,
        examination_id=exam.id,
        status="booked",
        booked_at=now_time,
    )
    db.session.add(booking)

    db.session.refresh(slot)
    if slot.booked_count >= slot.max_capacity:
        db.session.execute(
            ExaminationSlot.__table__.update()
            .where(ExaminationSlot.id == slot_id)
            .where(ExaminationSlot.status == "available")
            .where(ExaminationSlot.booked_count >= ExaminationSlot.max_capacity)
            .values(status="full")
        )

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
    except IntegrityError as err:
        db.session.rollback()
        raise BookingError(
            "duplicate_booking", "You already have a booking for this examination."
        ) from err
    except Exception:
        db.session.rollback()
        raise

    return booking


def cancel_booking(student_id, booking_id, now=None):
    now_time = now if now else windows.now_utc()

    booking = Booking.query.filter_by(id=booking_id, student_id=student_id).first()
    if not booking:
        raise BookingError("booking_not_found", "Booking not found.")

    if booking.status != "booked":
        raise BookingError("booking_not_cancellable", "This booking cannot be cancelled.")

    windows.assert_can_cancel(booking.examination, now_time)

    slot_id = booking.slot_id
    exam_id = booking.examination_id

    _release_seat(booking, cancelled_by_id=student_id, now=now_time)

    audit_service.log_action(
        actor_id=student_id,
        action=audit_service.BOOKING_CANCEL,
        entity_type="booking",
        entity_id=booking.id,
        details={"by": "student", "slot_id": slot_id},
    )
    db.session.commit()

    ctx = HookContext(
        student_id=student_id,
        slot_id=slot_id,
        examination_id=exam_id,
        booking_id=booking_id,
        actor_id=student_id,
    )
    hooks.run_post_cancel(ctx)

    return booking
