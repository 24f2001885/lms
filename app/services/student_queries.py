"""
FILE PURPOSE: Read-only queries for the student screens, so routes contain no query logic and every query is scoped to the signed-in student (PDR 5.4, TDR section 6).
DEPENDS ON: app/models, app/services/windows.py, app/services/evaluation_service.py (published_for_student), app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Visibility rule for examinations: show an examination to students only when it is not soft-deleted, its course is active, and (its status is not "draft" OR it has at least one non-cancelled slot). Drafts without slots stay hidden. This also covers the gap between the slot-creation window and the booking window.
2. list_examinations(student_id, q=None, course_id=None, exam_type=None, page=1, per_page=20): paginated visible examinations ordered by booking_start; each item carries booking state from windows.window_state (open/closed/scheduled with the reason text, e.g. "Booking opens on 12 Dec, 10:00"), the student's own active booking for it (or None) and the count of available slots. Filters are whitelisted (exam_type must be in EXAM_TYPES, course_id must be an int).
3. get_examination_for_student(exam_id) returns the examination only if visible (else None -> 404). slots_for_examination(exam_id) returns slots with status available or full whose start_at is in the future (completed/cancelled hidden), ordered by start_at, eager loading the examiner name, each with seats_left.
4. dashboard_data(student_id): available_examinations (booking effectively open now and the student has no active booking for it, max 6), available_slots (next 6 available future slots of those examinations), upcoming (the student's booked bookings whose slot starts in the future, next 5), booked (all the student's bookings with status booked, count and list), published_results (latest 5 from evaluation_service.published_for_student).
5. my_bookings(student_id, status=None, page=1): the student's bookings, newest first, eager loading slot, examination, examiner and evaluation (only the published flag). get_owned_booking(student_id, booking_id) returns None for anyone else's booking. schedule(student_id): booked bookings with future slot start ordered ascending. history(student_id, page): ALL of the student's bookings of every status (booked, cancelled, completed) newest first plus a grouped examination-history summary (examination, final status, result published yes/no).
6. results(student_id, page) and result_detail(student_id, booking_id): ONLY evaluations with status "published" belonging to the student's own bookings; result_detail returns total, maximum marks, per-criterion scores with comments and the remarks; anything else returns None (404). Students never see draft or submitted evaluations or the examiner's internal data beyond name.
7. Every function takes student_id explicitly; no function accepts a user object from the request; no query is written without a student filter where student data is involved.
DEBUGGING:
# print(f"[DEBUG] student_queries {name} student={student_id} rows={len(items)}")
OFFLINE DOCKER TEST CASES:
- A draft examination without slots is invisible; one with a slot is visible with the reason text.
- dashboard_data excludes examinations the student already booked from available_examinations.
- get_owned_booking returns None for another student's booking; result_detail returns None for a draft or submitted evaluation.
- history includes cancelled bookings; schedule excludes past slots and cancelled bookings.
- list_examinations with exam_type="quiz" is ignored (whitelist) and does not error.

FILE PURPOSE: Read-only queries scoped exclusively to the signed-in student (PDR 5.4).
"""

from app.models import Booking, Course, Evaluation, Examination, ExaminationSlot
from app.services import evaluation_service, windows

EXAM_TYPES_WHITELIST = ["viva", "lab", "written", "quiz", "project"]


def is_examination_visible(exam):
    if not exam or exam.is_deleted:
        return False
    if exam.course and not exam.course.is_active:
        return False
    if exam.status == "draft":
        non_cancelled_slots = ExaminationSlot.query.filter(
            ExaminationSlot.examination_id == exam.id, ExaminationSlot.status != "cancelled"
        ).count()
        if non_cancelled_slots == 0:
            return False
    return True


def list_examinations(student_id, q=None, course_id=None, exam_type=None, page=1, per_page=20):
    query = Examination.query.filter_by(is_deleted=False)
    query = query.join(Course, Examination.course_id == Course.id).filter(
        Course.is_active.is_(True)
    )

    if q:
        query = query.filter((Examination.name.ilike(f"%{q}%")) | (Course.code.ilike(f"%{q}%")))
    if course_id and isinstance(course_id, int):
        query = query.filter(Examination.course_id == course_id)
    if exam_type and exam_type in EXAM_TYPES_WHITELIST:
        query = query.filter(Examination.exam_type == exam_type)

    all_items = query.order_by(Examination.booking_start.asc()).all()
    visible_items = [e for e in all_items if is_examination_visible(e)]

    now = windows.now_utc()
    for exam in visible_items:
        exam.window_info = windows.window_state(exam, now)
        exam.own_booking = Booking.query.filter(
            Booking.student_id == student_id,
            Booking.examination_id == exam.id,
            Booking.status.in_(["booked", "completed"]),
        ).first()
        exam.available_slots_count = ExaminationSlot.query.filter(
            ExaminationSlot.examination_id == exam.id,
            ExaminationSlot.status == "available",
            ExaminationSlot.start_at > now,
        ).count()

    total = len(visible_items)
    start = (page - 1) * per_page
    end = start + per_page
    items = visible_items[start:end]

    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page if per_page else 1
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1

    return SimplePagination(items, page, per_page, total)


def get_examination_for_student(exam_id):
    exam = Examination.query.filter_by(id=exam_id, is_deleted=False).first()
    if not exam or not is_examination_visible(exam):
        return None
    return exam


def slots_for_examination(exam_id):
    now = windows.now_utc()
    slots = (
        ExaminationSlot.query.filter(
            ExaminationSlot.examination_id == exam_id,
            ExaminationSlot.status.in_(["available", "full"]),
            ExaminationSlot.start_at > now,
        )
        .order_by(ExaminationSlot.start_at.asc())
        .all()
    )
    return slots


def dashboard_data(student_id):
    now = windows.now_utc()
    all_exams = list_examinations(student_id, page=1, per_page=1000).items

    available_exams = []
    for e in all_exams:
        if e.window_info["booking"]["open"] and not e.own_booking:
            available_exams.append(e)
        if len(available_exams) >= 6:
            break

    avail_exam_ids = [e.id for e in available_exams]
    available_slots = []
    if avail_exam_ids:
        available_slots = (
            ExaminationSlot.query.filter(
                ExaminationSlot.examination_id.in_(avail_exam_ids),
                ExaminationSlot.status == "available",
                ExaminationSlot.start_at > now,
            )
            .order_by(ExaminationSlot.start_at.asc())
            .limit(6)
            .all()
        )

    upcoming_bookings = (
        Booking.query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
        .filter(
            Booking.student_id == student_id,
            Booking.status == "booked",
            ExaminationSlot.start_at > now,
        )
        .order_by(ExaminationSlot.start_at.asc())
        .limit(5)
        .all()
    )

    booked_bookings = Booking.query.filter_by(student_id=student_id, status="booked").all()
    published_results = evaluation_service.published_for_student(student_id)[:5]

    return {
        "available_examinations": available_exams,
        "available_slots": available_slots,
        "upcoming": upcoming_bookings,
        "booked": booked_bookings,
        "published_results": published_results,
    }


def my_bookings(student_id, status=None, page=1, per_page=20):
    query = Booking.query.filter_by(student_id=student_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(Booking.booked_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def get_owned_booking(student_id, booking_id):
    return Booking.query.filter_by(id=booking_id, student_id=student_id).first()


def schedule(student_id):
    now = windows.now_utc()
    return (
        Booking.query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
        .filter(
            Booking.student_id == student_id,
            Booking.status == "booked",
            ExaminationSlot.start_at > now,
        )
        .order_by(ExaminationSlot.start_at.asc())
        .all()
    )


def history(student_id, page=1, per_page=20):
    pagination = (
        Booking.query.filter_by(student_id=student_id)
        .order_by(Booking.booked_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    all_student_bookings = Booking.query.filter_by(student_id=student_id).all()
    exams_map = {}
    for b in all_student_bookings:
        e_id = b.examination_id
        if e_id not in exams_map:
            eval_pub = Evaluation.query.filter_by(booking_id=b.id, status="published").first()
            exams_map[e_id] = {
                "examination": b.examination,
                "final_status": b.status,
                "result_published": eval_pub is not None,
            }
        else:
            if b.status in ["booked", "completed"]:
                exams_map[e_id]["final_status"] = b.status

    return {"bookings_page": pagination, "examination_history": list(exams_map.values())}


def results(student_id, page=1, per_page=20):
    return (
        Evaluation.query.join(Booking, Evaluation.booking_id == Booking.id)
        .filter(Booking.student_id == student_id, Evaluation.status == "published")
        .order_by(Evaluation.published_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )


def result_detail(student_id, booking_id):
    booking = get_owned_booking(student_id, booking_id)
    if not booking:
        return None
    evaluation = Evaluation.query.filter_by(booking_id=booking_id, status="published").first()
    if not evaluation:
        return None

    exam = booking.examination
    scores_list = []
    for sc in evaluation.scores:
        scores_list.append(
            {
                "criterion": sc.rubric.criterion_name,
                "score": sc.score,
                "max_score": sc.rubric.max_score,
                "comment": sc.comment,
            }
        )

    return {
        "booking": booking,
        "evaluation": evaluation,
        "examination": exam,
        "total": evaluation.total_marks,
        "max_marks": exam.max_marks,
        "scores": scores_list,
        "remarks": evaluation.remarks,
    }
