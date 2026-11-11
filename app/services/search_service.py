"""
FILE PURPOSE: Admin search over students, examiners, examinations and bookings by NAME or ID (PDR 5.1).
DEPENDS ON: app/models, app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. escape_like(text) escapes the LIKE wildcards % and _ and the escape character itself, and every query uses .ilike(pattern, escape="\\") with the pattern %text%. No string-built SQL anywhere.
2. search(kind, q, page=1, per_page=20) where kind is one of "student", "examiner", "examination", "booking" (whitelist; anything else raises ValueError). q is stripped and limited to 100 characters; an empty q returns an empty result with a hint message flag instead of dumping all rows. Returns a pagination object from db.paginate(..., max_per_page=100, error_out=False).
3. Matching rules: if q is all digits also match id == int(q) (OR with the text match). student/examiner: users.full_name, users.email, plus student roll_number / examiner department (joined profiles), restricted by role. examination: name, description and course code/name (joined), INCLUDING soft-deleted rows but flagged. booking: booking id, student full name or email, examination name; joined so each result row has student, examination, slot time and status.
4. Order: exact id match first, then name ascending. Every result row is a plain model object; the template decides what to show. Never return password hashes to templates (templates must not print them).
DEBUGGING:
# print(f"[DEBUG] search kind={kind} q={q!r} digits={q.isdigit()} total={result.total}")
OFFLINE DOCKER TEST CASES:
- Searching "ana" finds students named Ana and Diana (case-insensitive) but no examiners.
- Searching "7" returns the user with id 7 as the first student result.
- Searching "100%" does not match everything (wildcard escaped).
- kind="invoice" raises ValueError; empty q returns zero rows and the hint flag.
- Booking search by student email finds that student's bookings across statuses.

app/services/search_service.py - Unified search service across portal entities.

Enables administrators to search across Students, Examiners, Examinations,
and Bookings by name, code, email, roll number, or numeric ID (Screen ADM-17).
"""

from typing import Any

from sqlalchemy import or_

from app.models.booking import Booking
from app.models.course import Course
from app.models.examination import Examination
from app.models.examiner_profile import ExaminerProfile
from app.models.student_profile import StudentProfile
from app.models.user import User


def search_all_entities(query_str: str) -> dict[str, list[Any]]:
    """
    Execute unified multi-entity search matching query_str.

    Returns:
        Dict with keys: 'students', 'examiners', 'examinations', 'courses', 'bookings'
    """
    clean_query = query_str.strip()
    if not clean_query:
        return {
            "students": [],
            "examiners": [],
            "examinations": [],
            "courses": [],
            "bookings": [],
        }

    is_numeric = clean_query.isdigit()
    numeric_id = int(clean_query) if is_numeric else None
    like_term = f"%{clean_query}%"

    # 1. Students Search (name, email, roll_number, or ID)
    student_filters = [
        User.full_name.ilike(like_term),
        User.email.ilike(like_term),
    ]
    if is_numeric:
        student_filters.append(User.id == numeric_id)

    students = (
        User.query.filter(User.role == "student")
        .outerjoin(StudentProfile)
        .filter(or_(*student_filters, StudentProfile.roll_number.ilike(like_term)))
        .limit(25)
        .all()
    )

    # 2. Examiners Search (name, email, department, or ID)
    examiner_filters = [
        User.full_name.ilike(like_term),
        User.email.ilike(like_term),
    ]
    if is_numeric:
        examiner_filters.append(User.id == numeric_id)

    examiners = (
        User.query.filter(User.role == "examiner")
        .outerjoin(ExaminerProfile)
        .filter(or_(*examiner_filters, ExaminerProfile.department.ilike(like_term)))
        .limit(25)
        .all()
    )

    # 3. Examinations Search (name, description, or ID)
    exam_filters = [
        Examination.name.ilike(like_term),
        Examination.description.ilike(like_term),
    ]
    if is_numeric:
        exam_filters.append(Examination.id == numeric_id)

    examinations = (
        Examination.query.filter(Examination.is_deleted.is_(False))
        .filter(or_(*exam_filters))
        .limit(25)
        .all()
    )

    # 4. Courses Search (code, name, or ID)
    course_filters = [
        Course.code.ilike(like_term),
        Course.name.ilike(like_term),
    ]
    if is_numeric:
        course_filters.append(Course.id == numeric_id)

    courses = Course.query.filter(or_(*course_filters)).limit(25).all()

    # 5. Bookings Search (by booking ID, student name, or exam name)
    booking_query = Booking.query.join(User, Booking.student_id == User.id).join(
        Examination, Booking.examination_id == Examination.id
    )
    booking_filters = [
        User.full_name.ilike(like_term),
        User.email.ilike(like_term),
        Examination.name.ilike(like_term),
    ]
    if is_numeric:
        booking_filters.append(Booking.id == numeric_id)

    bookings = booking_query.filter(or_(*booking_filters)).limit(25).all()

    return {
        "students": students,
        "examiners": examiners,
        "examinations": examinations,
        "courses": courses,
        "bookings": bookings,
    }