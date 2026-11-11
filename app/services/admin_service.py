"""
app/services/admin_service.py - Admin operations for users, slots, and dashboard totals.
"""

import secrets
from typing import Any

from app.errors import AppError
from app.extensions import db
from app.models.booking import Booking
from app.models.course import Course
from app.models.examination import Examination
from app.models.examination_examiner import ExaminationExaminer
from app.models.slot import ExaminationSlot
from app.models.user import User
from app.security.auth_helpers import validate_password_strength
from app.services import audit_service, slot_rules


def dashboard_totals() -> dict[str, Any]:
    """Execute COUNT queries only to build the 6 dashboard metrics."""
    courses_count = Course.query.count()
    exams_count = Examination.query.filter_by(is_deleted=False).count()
    examiners_count = User.query.filter_by(role="examiner").count()
    pending_count = User.query.filter_by(role="examiner", approval_status="pending").count()
    students_count = User.query.filter_by(role="student").count()
    slots_count = ExaminationSlot.query.filter(ExaminationSlot.status != "cancelled").count()
    bookings_count = Booking.query.filter(Booking.status.in_(("booked", "completed"))).count()
    cancelled_bookings = Booking.query.filter_by(status="cancelled").count()

    return {
        "courses": courses_count,
        "examinations": exams_count,
        "examiners": examiners_count,
        "examiners_pending": pending_count,
        "students": students_count,
        "slots": slots_count,
        "bookings": bookings_count,
        "cancelled_bookings": cancelled_bookings,
    }


def approve_examiner(actor_id: int, user_id: int) -> User:
    user = db.session.get(User, user_id)
    if not user:
        raise AppError("user_not_found", "User not found.")
    if user.role != "examiner":
        raise AppError("not_an_examiner", "Only examiner accounts can be approved.")

    user.approval_status = "approved"
    user.is_active = True
    if user.examiner_profile:
        user.examiner_profile.status = "active"

    audit_service.log_action(actor_id, audit_service.USER_APPROVE, "user", user.id, {"email": user.email})
    db.session.commit()
    return user


def reject_examiner(actor_id: int, user_id: int) -> User:
    user = db.session.get(User, user_id)
    if not user:
        raise AppError("user_not_found", "User not found.")
    if user.role != "examiner":
        raise AppError("not_an_examiner", "Only examiner accounts can be rejected.")

    user.approval_status = "rejected"
    audit_service.log_action(actor_id, audit_service.USER_REJECT, "user", user.id, {"email": user.email})
    db.session.commit()
    return user


def deactivate_user(actor_id: int, user_id: int) -> User:
    if actor_id == user_id:
        raise AppError("cannot_deactivate_self", "Administrators cannot deactivate their own account.")

    user = db.session.get(User, user_id)
    if not user:
        raise AppError("user_not_found", "User not found.")

    user.is_active = False
    if user.examiner_profile:
        user.examiner_profile.status = "inactive"

    audit_service.log_action(actor_id, audit_service.USER_DEACTIVATE, "user", user.id, {"email": user.email})
    db.session.commit()
    return user


def activate_user(actor_id: int, user_id: int) -> User:
    user = db.session.get(User, user_id)
    if not user:
        raise AppError("user_not_found", "User not found.")

    user.is_active = True
    if user.examiner_profile:
        user.examiner_profile.status = "active"

    audit_service.log_action(actor_id, audit_service.USER_ACTIVATE, "user", user.id, {"email": user.email})
    db.session.commit()
    return user


def set_temporary_password(actor_id: int, user_id: int, new_password: str | None = None) -> str:
    user = db.session.get(User, user_id)
    if not user:
        raise AppError("user_not_found", "User not found.")
    if user.role == "admin":
        raise AppError("cannot_reset_admin", "Admin temporary passwords cannot be set via this route.")

    plain_pass = (
        new_password.strip()
        if new_password and new_password.strip()
        else f"Tmp{secrets.token_urlsafe(9)}1"
    )
    problems = validate_password_strength(plain_pass)
    if problems:
        raise AppError("weak_password", problems[0])

    user.set_password(plain_pass)
    user.must_change_password = True

    audit_service.log_action(actor_id, audit_service.USER_TEMP_PASSWORD, "user", user.id, {"email": user.email})
    db.session.commit()
    return plain_pass


def change_slot_examiner(actor_id: int, slot_id: int, new_examiner_id: int) -> ExaminationSlot:
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        raise AppError("slot_not_found", "Slot not found.")
    if slot.status in ("cancelled", "completed"):
        raise AppError("slot_not_changeable", f"Cannot change examiner on a {slot.status} slot.")

    if slot.examiner_id == new_examiner_id:
        return slot

    is_assigned = (
        ExaminationExaminer.query.join(User, ExaminationExaminer.examiner_id == User.id)
        .filter(ExaminationExaminer.examination_id == slot.examination_id, User.id == new_examiner_id, User.approval_status == "approved", User.is_active.is_(True))
        .count()
        > 0
    )
    if not is_assigned:
        raise AppError("examiner_not_eligible", "Examiner is not assigned or not approved for this examination.")

    conflict = slot_rules.find_overlapping(new_examiner_id, slot.start_at, slot.end_at, exclude_slot_id=slot.id)
    if conflict:
        raise AppError("examiner_overlap", f"Examiner has an overlapping slot ({conflict.start_at.strftime('%H:%M')} - {conflict.end_at.strftime('%H:%M')}).")

    old_examiner_id = slot.examiner_id
    slot.examiner_id = new_examiner_id

    audit_service.log_action(actor_id, audit_service.SLOT_EXAMINER_CHANGE, "examination_slot", slot.id, {"from": old_examiner_id, "to": new_examiner_id})
    db.session.commit()
    return slot