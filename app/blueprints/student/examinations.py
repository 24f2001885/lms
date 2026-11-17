"""
FILE PURPOSE: STU-02 browse/search/filter examinations and STU-03 examination detail with slots and the booking confirmation modal (STU-04).
DEPENDS ON: student_bp, student_required, app/services/student_queries.py, app/services/windows.py, app/forms/common.py (ConfirmForm, parse_page).
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/examinations with query parameters q, course_id, exam_type, page. Render student/examinations.html with the paginated cards from student_queries.list_examinations.
2. GET /student/examinations/<id>: examination via get_examination_for_student (404 when None), its slots via slots_for_examination, the student's own active booking for it, and windows.window_state for the reason line. Provide one ConfirmForm instance per page (CSRF token for the modal forms).
3. A Book button is enabled only when booking is effectively open, the slot is available and the student has no active booking for this examination; otherwise it is disabled with the exact reason text ("Booking opens on ...", "Booking is closed", "This slot is full", "You already booked this examination").
4. No booking logic here; the confirm modal posts to /student/slots/<id>/book (route in bookings.py).
DEBUGGING:
# print(f"[DEBUG] student exam detail exam={exam.id} slots={len(slots)} own_booking={own and own.id}")
OFFLINE DOCKER TEST CASES:
- Draft examination id returns 404; deleted examination returns 404.
- Filters narrow the list and survive paging.
- With booking closed every Book button is disabled with a reason line.

FILE PURPOSE: STU-02 browse examinations and STU-03 examination details with slots.
"""
from flask import abort, g, render_template, request

from app.blueprints.student import student_bp
from app.forms.common import ConfirmForm
from app.models import Booking, Course
from app.security.decorators import student_required
from app.services import student_queries, windows


@student_bp.route("/examinations")
@student_required
def examinations_list():
    q = request.args.get("q", "").strip()
    course_id = request.args.get("course_id", type=int)
    exam_type = request.args.get("exam_type", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = student_queries.list_examinations(
        g.user.id, q=q or None, course_id=course_id, exam_type=exam_type or None, page=page
    )
    courses = Course.query.filter_by(is_active=True).all()

    return render_template(
        "student/examinations.html",
        pagination=pagination,
        page=pagination,
        courses=courses,
        selected_q=q,
        selected_course=course_id,
        selected_type=exam_type
    )


@student_bp.route("/examinations/<int:exam_id>")
@student_required
def examination_detail(exam_id):
    exam = student_queries.get_examination_for_student(exam_id)
    if not exam:
        abort(404)

    slots = student_queries.slots_for_examination(exam.id)
    own_booking = Booking.query.filter(
        Booking.student_id == g.user.id,
        Booking.examination_id == exam.id,
        Booking.status.in_(["booked", "completed"])
    ).first()

    win_state = windows.window_state(exam)
    confirm_form = ConfirmForm()

    return render_template(
        "student/examination_detail.html",
        examination=exam,
        slots=slots,
        own_booking=own_booking,
        win_state=win_state,
        confirm_form=confirm_form
    )