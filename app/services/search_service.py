"""
app/services/search_service.py - Administrator search across students, examiners, exams, bookings.
"""

from sqlalchemy import or_

from app.extensions import db
from app.models.booking import Booking
from app.models.course import Course
from app.models.examination import Examination
from app.models.examiner_profile import ExaminerProfile
from app.models.student_profile import StudentProfile
from app.models.user import User


def escape_like(text: str) -> str:
    """Escape LIKE wildcard characters (%, _) and backslash."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(kind: str, q: str, page: int = 1, per_page: int = 20):
    """
    Perform paginated search across a specific entity kind.
    Supported kinds: 'student', 'examiner', 'examination', 'booking'.
    """
    valid_kinds = ("student", "examiner", "examination", "booking")
    if kind not in valid_kinds:
        raise ValueError(f"Invalid search kind '{kind}'. Must be one of {valid_kinds}")

    clean_q = (q or "").strip()[:100]
    if not clean_q:
        return None  # Triggers empty search prompt in view

    is_digit = clean_q.isdigit()
    num_id = int(clean_q) if is_digit else None
    escaped_term = f"%{escape_like(clean_q)}%"

    if kind == "student":
        conds = [
            User.full_name.ilike(escaped_term, escape="\\"),
            User.email.ilike(escaped_term, escape="\\"),
            StudentProfile.roll_number.ilike(escaped_term, escape="\\"),
        ]
        if is_digit:
            conds.append(User.id == num_id)
        query = (
            User.query.filter(User.role == "student")
            .outerjoin(StudentProfile)
            .filter(or_(*conds))
            .order_by(
                (User.id == num_id).desc() if is_digit else User.id.asc(), User.full_name.asc()
            )
        )

    elif kind == "examiner":
        conds = [
            User.full_name.ilike(escaped_term, escape="\\"),
            User.email.ilike(escaped_term, escape="\\"),
            ExaminerProfile.department.ilike(escaped_term, escape="\\"),
        ]
        if is_digit:
            conds.append(User.id == num_id)
        query = (
            User.query.filter(User.role == "examiner")
            .outerjoin(ExaminerProfile)
            .filter(or_(*conds))
            .order_by(
                (User.id == num_id).desc() if is_digit else User.id.asc(), User.full_name.asc()
            )
        )

    elif kind == "examination":
        conds = [
            Examination.name.ilike(escaped_term, escape="\\"),
            Examination.description.ilike(escaped_term, escape="\\"),
            Course.code.ilike(escaped_term, escape="\\"),
            Course.name.ilike(escaped_term, escape="\\"),
        ]
        if is_digit:
            conds.append(Examination.id == num_id)
        query = (
            Examination.query.join(Course)
            .filter(or_(*conds))
            .order_by(
                (Examination.id == num_id).desc() if is_digit else Examination.id.asc(),
                Examination.name.asc(),
            )
        )

    elif kind == "booking":
        conds = [
            User.full_name.ilike(escaped_term, escape="\\"),
            User.email.ilike(escaped_term, escape="\\"),
            Examination.name.ilike(escaped_term, escape="\\"),
        ]
        if is_digit:
            conds.append(Booking.id == num_id)
        query = (
            Booking.query.join(User, Booking.student_id == User.id)
            .join(Examination, Booking.examination_id == Examination.id)
            .filter(or_(*conds))
            .order_by(
                (Booking.id == num_id).desc() if is_digit else Booking.id.asc(),
                Booking.booked_at.desc(),
            )
        )

    return db.paginate(query, page=page, per_page=min(per_page, 100), error_out=False)
