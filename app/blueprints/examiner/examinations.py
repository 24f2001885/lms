"""
FILE PURPOSE: EXM-02 assigned examinations list and EXM-03 examination detail.
"""

from flask import abort, g, render_template, request

from app.blueprints.examiner import examiner_bp
from app.models import ExaminationRubric, ExaminationSlot
from app.security.decorators import approved_examiner_required
from app.services import slot_service


@examiner_bp.route("/examinations")
@approved_examiner_required
def examinations_list():
    examiner_id = g.user.id
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    exams = slot_service.list_assigned_examinations(examiner_id)

    filtered = []
    for exam in exams:
        course_code = exam.course.code.lower() if exam.course else ""
        if q and q.lower() not in exam.name.lower() and q.lower() not in course_code:
            continue
        if status_filter and exam.status != status_filter:
            continue

        exam.slot_state = slot_service.slot_creation_state(exam)
        exam.my_slots_count = ExaminationSlot.query.filter_by(
            examination_id=exam.id, examiner_id=examiner_id
        ).count()
        filtered.append(exam)

    return render_template(
        "examiner/examinations_list.html", examinations=filtered, q=q, status=status_filter
    )


@examiner_bp.route("/examinations/<int:exam_id>")
@approved_examiner_required
def examination_detail(exam_id):
    examiner_id = g.user.id
    exam = slot_service.get_assigned_examination(examiner_id, exam_id)
    if not exam:
        abort(404)

    rubrics = (
        ExaminationRubric.query.filter_by(examination_id=exam.id)
        .order_by(ExaminationRubric.position.asc())
        .all()
    )
    slots = (
        ExaminationSlot.query.filter_by(examination_id=exam.id, examiner_id=examiner_id)
        .order_by(ExaminationSlot.start_at.asc())
        .all()
    )
    slot_state = slot_service.slot_creation_state(exam)

    return render_template(
        "examiner/examination_detail.html",
        examination=exam,
        rubrics=rubrics,
        slots=slots,
        slot_state=slot_state,
    )
