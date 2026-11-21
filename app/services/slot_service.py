"""
FILE PURPOSE: Examiner-side slot rules: create, update, remove, list, booked students and dashboard counts. All window and ownership rules for slots live here (PDR 5.3, TDR 3.5).
"""

from sqlalchemy import func

from app.errors import AppError
from app.extensions import db
from app.models import Booking, Examination, ExaminationExaminer, ExaminationSlot, User
from app.services import audit_service, slot_rules, windows


def get_owned_slot(examiner_id, slot_id):
    return ExaminationSlot.query.filter_by(id=slot_id, examiner_id=examiner_id).first()


def get_assigned_examination(examiner_id, examination_id):
    exam = Examination.query.filter_by(id=examination_id, is_deleted=False).first()
    if not exam:
        return None
    assignment = ExaminationExaminer.query.filter_by(
        examination_id=examination_id, examiner_id=examiner_id
    ).first()
    return exam if assignment else None


def list_assigned_examinations(examiner_id):
    assignments = ExaminationExaminer.query.filter_by(examiner_id=examiner_id).all()
    exam_ids = [a.examination_id for a in assignments]
    if not exam_ids:
        return []
    return Examination.query.filter(
        Examination.id.in_(exam_ids), Examination.is_deleted.is_(False)
    ).all()


def create_slot(examiner_id, examination_id, start_at, end_at, max_capacity):
    examiner = User.query.get(examiner_id)
    if not examiner or not examiner.is_active or examiner.approval_status != "approved":
        raise AppError("not_approved", "Examiner not approved or inactive.")

    exam = get_assigned_examination(examiner_id, examination_id)
    if not exam:
        raise AppError("examination_not_found", "Examination not found or not assigned.")

    windows.assert_slot_creation_open(exam)

    if not start_at or not end_at or start_at >= end_at:
        raise AppError("invalid_time_range", "Invalid time range: start must be before end.")

    now = windows.now_utc()
    if start_at < now:
        raise AppError("slot_in_past", "Slot start time cannot be in the past.")

    if not isinstance(max_capacity, int) or not (1 <= max_capacity <= 500):
        raise AppError("invalid_capacity", "Capacity must be between 1 and 500.")

    if slot_rules.has_overlap(examiner_id, start_at, end_at):
        raise AppError("examiner_overlap", "Slot overlaps with an existing time slot.")

    slot = ExaminationSlot(
        examination_id=examination_id,
        examiner_id=examiner_id,
        start_at=start_at,
        end_at=end_at,
        max_capacity=max_capacity,
        booked_count=0,
        status="available",
    )
    db.session.add(slot)
    db.session.flush()

    audit_service.log_action(
        actor_id=examiner_id,
        action=audit_service.SLOT_CREATE,
        entity_type="examination_slot",
        entity_id=slot.id,
        details={
            "examination_id": examination_id,
            "start": str(start_at),
            "end": str(end_at),
            "capacity": max_capacity,
        },
    )
    db.session.commit()
    return slot


def update_slot(examiner_id, slot_id, start_at, end_at, max_capacity):
    slot = get_owned_slot(examiner_id, slot_id)
    if not slot:
        raise AppError("slot_not_found", "Slot not found.")

    windows.assert_slots_editable(slot.examination)

    active_bookings = Booking.query.filter(
        Booking.slot_id == slot_id, Booking.status.in_(["booked", "completed"])
    ).count()
    if active_bookings > 0:
        raise AppError("slot_has_bookings", "Cannot update slot with active bookings.")

    if slot.status != "available":
        raise AppError("slot_not_editable", "Slot is not editable.")

    if not start_at or not end_at or start_at >= end_at:
        raise AppError("invalid_time_range", "Invalid time range.")

    if start_at < windows.now_utc():
        raise AppError("slot_in_past", "Slot start time cannot be in the past.")

    if not isinstance(max_capacity, int) or not (1 <= max_capacity <= 500):
        raise AppError("invalid_capacity", "Capacity must be between 1 and 500.")

    if slot_rules.has_overlap(examiner_id, start_at, end_at, exclude_slot_id=slot_id):
        raise AppError("examiner_overlap", "Slot overlaps with an existing time slot.")

    before_vals = {
        "start": str(slot.start_at),
        "end": str(slot.end_at),
        "capacity": slot.max_capacity,
    }

    slot.start_at = start_at
    slot.end_at = end_at
    slot.max_capacity = max_capacity

    audit_service.log_action(
        actor_id=examiner_id,
        action=audit_service.SLOT_UPDATE,
        entity_type="examination_slot",
        entity_id=slot.id,
        details={
            "before": before_vals,
            "after": {"start": str(start_at), "end": str(end_at), "capacity": max_capacity},
        },
    )
    db.session.commit()
    return slot


def delete_slot(examiner_id, slot_id):
    slot = get_owned_slot(examiner_id, slot_id)
    if not slot:
        raise AppError("slot_not_found", "Slot not found.")

    windows.assert_slots_editable(slot.examination)

    active_bookings = Booking.query.filter(
        Booking.slot_id == slot_id, Booking.status.in_(["booked", "completed"])
    ).count()
    if active_bookings > 0:
        raise AppError("slot_has_bookings", "Cannot delete slot with active bookings.")

    any_bookings = Booking.query.filter_by(slot_id=slot_id).count()

    if any_bookings == 0:
        db.session.delete(slot)
        mode = "deleted"
    else:
        slot.status = "cancelled"
        mode = "cancelled"

    audit_service.log_action(
        actor_id=examiner_id,
        action=audit_service.SLOT_DELETE,
        entity_type="examination_slot",
        entity_id=slot_id,
        details={"mode": mode},
    )
    db.session.commit()


def list_slots(examiner_id, examination_id=None, status=None, page=1, per_page=20):
    query = ExaminationSlot.query.filter_by(examiner_id=examiner_id)
    if examination_id:
        query = query.filter_by(examination_id=examination_id)
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(ExaminationSlot.start_at.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return pagination


def booked_students(examiner_id, slot_id):
    slot = get_owned_slot(examiner_id, slot_id)
    if not slot:
        return []
    return (
        Booking.query.join(User, Booking.student_id == User.id)
        .filter(Booking.slot_id == slot_id, Booking.status.in_(["booked", "completed"]))
        .order_by(User.full_name.asc())
        .all()
    )


def examiner_dashboard_counts(examiner_id):
    assigned_exams_count = ExaminationExaminer.query.filter_by(examiner_id=examiner_id).count()

    created_slots_count = ExaminationSlot.query.filter(
        ExaminationSlot.examiner_id == examiner_id, ExaminationSlot.status != "cancelled"
    ).count()

    students_booked_count = (
        db.session.query(func.count(Booking.id))
        .join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
        .filter(
            ExaminationSlot.examiner_id == examiner_id,
            ExaminationSlot.status != "cancelled",
            Booking.status.in_(["booked", "completed"]),
        )
        .scalar()
        or 0
    )

    now = windows.now_utc()
    upcoming_slots = (
        ExaminationSlot.query.filter(
            ExaminationSlot.examiner_id == examiner_id,
            ExaminationSlot.status != "cancelled",
            ExaminationSlot.start_at >= now,
        )
        .order_by(ExaminationSlot.start_at.asc())
        .limit(5)
        .all()
    )

    return {
        "assigned_examinations": assigned_exams_count,
        "created_slots": created_slots_count,
        "students_booked": students_booked_count,
        "upcoming_slots": upcoming_slots,
    }


def slot_creation_state(examination):
    state = windows.window_state(examination)
    slot_win = state["slot_creation"]
    return {**slot_win, "can_create": slot_win["open"]}
