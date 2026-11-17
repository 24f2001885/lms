"""
FILE PURPOSE: Single place that converts model objects into role-scoped JSON dictionaries.
"""

from typing import Any

from app.blueprints.api_v1.common import iso
from app.models import Booking, Examination, ExaminationSlot, User
from app.services import windows

FORBIDDEN_KEYS: set[str] = {
    "password_hash",
    "password",
    "must_change_password",
    "ip_address",
    "secret_key",
}


def examination_to_dict(exam: Examination, viewer: User) -> dict[str, Any]:
    now = windows.now_utc()
    data: dict[str, Any] = {
        "id": int(exam.id),
        "course_id": int(exam.course_id),
        "course_code": exam.course.code if exam.course else None,
        "name": exam.name,
        "description": exam.description,
        "exam_type": exam.exam_type,
        "duration_minutes": int(exam.duration_minutes),
        "max_marks": int(exam.max_marks),
        "slot_creation_start": iso(exam.slot_creation_start),
        "slot_creation_end": iso(exam.slot_creation_end),
        "booking_start": iso(exam.booking_start),
        "booking_end": iso(exam.booking_end),
        "cancellation_deadline": iso(exam.cancellation_deadline),
        "slot_creation_open": bool(exam.slot_creation_open),
        "booking_open": bool(exam.booking_open),
        "slot_creation_effective_open": bool(windows.is_slot_creation_open(exam, now)),
        "booking_effective_open": bool(windows.is_booking_open(exam, now)),
        "status": exam.status,
    }
    if viewer.role == "admin":
        data["is_deleted"] = bool(exam.is_deleted)
    return data


def slot_to_dict(slot: ExaminationSlot, viewer: User) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": int(slot.id),
        "examination_id": int(slot.examination_id),
    }
    if viewer.role in ("admin", "examiner"):
        data["examiner_id"] = int(slot.examiner_id) if slot.examiner_id is not None else None
    data["examiner_name"] = slot.examiner.full_name if slot.examiner else None
    data["start_at"] = iso(slot.start_at)
    data["end_at"] = iso(slot.end_at)
    data["max_capacity"] = int(slot.max_capacity)
    data["booked_count"] = int(slot.booked_count)
    data["seats_left"] = max(0, int(slot.max_capacity) - int(slot.booked_count))
    data["status"] = slot.status
    return data


def booking_to_dict(booking: Booking, viewer: User) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": int(booking.id),
        "slot_id": int(booking.slot_id),
        "examination_id": int(booking.examination_id),
        "status": booking.status,
        "booked_at": iso(booking.booked_at),
        "cancelled_at": iso(booking.cancelled_at),
    }
    if viewer.role in ("admin", "examiner"):
        student = booking.student
        roll = (
            student.student_profile.roll_number
            if (student and getattr(student, "student_profile", None))
            else None
        )
        data["student_id"] = int(booking.student_id)
        data["student_name"] = student.full_name if student else None
        data["student_roll_number"] = roll

    if viewer.role == "admin":
        data["cancelled_by"] = (
            int(booking.cancelled_by) if booking.cancelled_by is not None else None
        )
        data["rescheduled_from_slot_id"] = (
            int(booking.rescheduled_from_slot_id)
            if booking.rescheduled_from_slot_id is not None
            else None
        )
    return data


def examiner_to_dict(user: User) -> dict[str, Any]:
    profile = getattr(user, "examiner_profile", None)
    return {
        "id": int(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "approval_status": user.approval_status,
        "is_active": bool(user.is_active),
        "department": profile.department if profile else None,
        "designation": profile.designation if profile else None,
        "contact_phone": profile.contact_phone if profile else None,
    }


def student_to_dict(user: User) -> dict[str, Any]:
    profile = getattr(user, "student_profile", None)
    return {
        "id": int(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "is_active": bool(user.is_active),
        "roll_number": profile.roll_number if profile else None,
        "program": profile.program if profile else None,
    }


def user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": int(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "approval_status": user.approval_status,
    }
