"""
FILE PURPOSE: Read-only, role-scoped queries behind the JSON API (mirrors HTML screen scoping).
"""

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Booking,
    Course,
    Examination,
    ExaminationExaminer,
    ExaminationSlot,
    User,
)
from app.services import admin_service, windows

EXAM_STATUSES = ("draft", "slot_creation", "booking_open", "closed", "completed")


def _clamp_paging(page: int = 1, per_page: int = 20) -> tuple[int, int]:
    p = max(1, int(page))
    pp = max(1, min(100, int(per_page)))
    return p, pp


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _base_examination_query(user: User, include_deleted: bool = False):
    query = Examination.query.options(joinedload(Examination.course))

    if user.role == "admin":
        if not include_deleted:
            query = query.filter(Examination.is_deleted.is_(False))
        return query

    if user.role == "examiner":
        return query.join(
            ExaminationExaminer,
            ExaminationExaminer.examination_id == Examination.id,
        ).filter(
            Examination.is_deleted.is_(False),
            ExaminationExaminer.examiner_id == user.id,
        )

    # Student visibility rule: non-deleted, active course
    return query.join(Course, Examination.course_id == Course.id).filter(
        Examination.is_deleted.is_(False),
        Course.status == "active",
    )


def list_examinations(
    user: User,
    q: str | None = None,
    course_id: int | None = None,
    status: str | None = None,
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 20,
):
    p, pp = _clamp_paging(page, per_page)
    if status is not None and status not in EXAM_STATUSES:
        raise ValueError(f"Unknown examination status: {status}")

    query = _base_examination_query(user, include_deleted=include_deleted)

    if course_id is not None:
        query = query.filter(Examination.course_id == course_id)
    if status is not None:
        query = query.filter(Examination.status == status)
    if q:
        escaped = _escape_like(q.strip())
        query = query.join(Course, Examination.course_id == Course.id, isouter=True).filter(
            or_(
                Examination.name.ilike(f"%{escaped}%", escape="\\"),
                Course.code.ilike(f"%{escaped}%", escape="\\"),
            )
        )

    query = query.order_by(Examination.booking_start.asc(), Examination.id.asc())
    return db.paginate(query, page=p, per_page=pp, error_out=False)


def get_examination(user: User, exam_id: int) -> Examination | None:
    return (
        _base_examination_query(user, include_deleted=(user.role == "admin"))
        .filter(Examination.id == exam_id)
        .first()
    )


def _base_slot_query(user: User):
    now = windows.now_utc()
    query = ExaminationSlot.query.options(
        joinedload(ExaminationSlot.examiner),
        joinedload(ExaminationSlot.examination),
    )

    if user.role == "admin":
        return query
    if user.role == "examiner":
        return query.filter(ExaminationSlot.examiner_id == user.id)

    # Student: future available or full slots in student-visible examinations
    visible_exam_ids = _base_examination_query(user).with_entities(Examination.id)
    return query.filter(
        ExaminationSlot.examination_id.in_(visible_exam_ids),
        ExaminationSlot.status.in_(["available", "full"]),
        ExaminationSlot.start_at > now,
    )


def list_slots(
    user: User,
    examination_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
):
    p, pp = _clamp_paging(page, per_page)
    query = _base_slot_query(user)
    if examination_id is not None:
        query = query.filter(ExaminationSlot.examination_id == examination_id)
    if status is not None:
        query = query.filter(ExaminationSlot.status == status)

    query = query.order_by(ExaminationSlot.start_at.asc(), ExaminationSlot.id.asc())
    return db.paginate(query, page=p, per_page=pp, error_out=False)


def get_slot(user: User, slot_id: int) -> ExaminationSlot | None:
    return _base_slot_query(user).filter(ExaminationSlot.id == slot_id).first()


def _base_booking_query(user: User):
    query = Booking.query.options(
        joinedload(Booking.slot),
        joinedload(Booking.examination),
        joinedload(Booking.student).joinedload(User.student_profile),
    )

    if user.role == "admin":
        return query
    if user.role == "examiner":
        return query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id).filter(
            ExaminationSlot.examiner_id == user.id
        )
    return query.filter(Booking.student_id == user.id)


def list_bookings(
    user: User,
    status: str | None = None,
    examination_id: int | None = None,
    page: int = 1,
    per_page: int = 20,
):
    p, pp = _clamp_paging(page, per_page)
    query = _base_booking_query(user)
    if status is not None:
        query = query.filter(Booking.status == status)
    if examination_id is not None:
        query = query.filter(Booking.examination_id == examination_id)

    query = query.order_by(Booking.booked_at.desc(), Booking.id.desc())
    return db.paginate(query, page=p, per_page=pp, error_out=False)


def get_booking(user: User, booking_id: int) -> Booking | None:
    return _base_booking_query(user).filter(Booking.id == booking_id).first()


def list_examiners(
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
):
    p, pp = _clamp_paging(page, per_page)
    query = User.query.options(joinedload(User.examiner_profile)).filter(User.role == "examiner")

    if status == "pending":
        query = query.filter(User.approval_status == "pending")
    elif status == "approved":
        query = query.filter(User.approval_status == "approved", User.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active.is_(False))
    elif status == "rejected":
        query = query.filter(User.approval_status == "rejected")
    elif status is not None:
        raise ValueError(f"Unknown examiner filter status: {status}")

    if q:
        escaped = _escape_like(q.strip())
        query = query.filter(
            or_(
                User.full_name.ilike(f"%{escaped}%", escape="\\"),
                User.email.ilike(f"%{escaped}%", escape="\\"),
            )
        )

    query = query.order_by(User.created_at.desc(), User.id.asc())
    return db.paginate(query, page=p, per_page=pp, error_out=False)


def list_students(
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
):
    from app.models import StudentProfile

    p, pp = _clamp_paging(page, per_page)
    query = (
        User.query.options(joinedload(User.student_profile))
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .filter(User.role == "student")
    )

    if q:
        term = q.strip()
        escaped = _escape_like(term)
        conditions = [
            User.full_name.ilike(f"%{escaped}%", escape="\\"),
            User.email.ilike(f"%{escaped}%", escape="\\"),
            StudentProfile.roll_number.ilike(f"%{escaped}%", escape="\\"),
        ]
        if term.isdigit():
            conditions.append(User.id == int(term))
        query = query.filter(or_(*conditions))

    query = query.order_by(User.created_at.desc(), User.id.asc())
    return db.paginate(query, page=p, per_page=pp, error_out=False)


def summary() -> dict[str, int]:
    totals = admin_service.dashboard_totals()
    return {
        "courses": int(totals["courses"]),
        "examinations": int(totals["examinations"]),
        "examiners": int(totals["examiners"]),
        "students": int(totals["students"]),
        "slots": int(totals["slots"]),
        "bookings": int(totals["bookings"]),
    }
