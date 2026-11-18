"""
FILE PURPOSE: Rubric-based evaluation rules for examiners: which students may be evaluated, saving drafts, submitting and publishing (PDR 5.5, TDR 4.1 evaluation tables).
"""

from decimal import Decimal

from sqlalchemy import func

from app.errors import AppError, BookingError
from app.extensions import db
from app.models import (
    Booking,
    Evaluation,
    EvaluationScore,
    ExaminationRubric,
    ExaminationSlot,
    User,
)
from app.services import audit_service, hooks, windows


def get_owned_booking(examiner_id, booking_id):
    booking = Booking.query.get(booking_id)
    if not booking or booking.status not in ["booked", "completed"]:
        return None
    slot = ExaminationSlot.query.get(booking.slot_id)
    if not slot or slot.examiner_id != examiner_id or slot.status == "cancelled":
        return None
    return booking


def pending_bookings(examiner_id, examination_id=None, q=None, page=1, per_page=20):
    query = Booking.query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id).filter(
        ExaminationSlot.examiner_id == examiner_id,
        ExaminationSlot.status != "cancelled",
        Booking.status.in_(["booked", "completed"]),
    )
    if examination_id:
        query = query.filter(ExaminationSlot.examination_id == examination_id)
    if q:
        query = query.join(User, Booking.student_id == User.id).filter(
            (User.full_name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )

    subq = db.session.query(Evaluation.booking_id).filter(
        Evaluation.status.in_(["submitted", "published"])
    )
    query = query.filter(~Booking.id.in_(subq))

    return query.order_by(Booking.booked_at.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def submitted_evaluations(examiner_id, status=None, page=1, per_page=20):
    query = Evaluation.query.filter_by(examiner_id=examiner_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(Evaluation.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def pending_evaluations_count(examiner_id):
    bookings = pending_bookings(examiner_id, page=1, per_page=1000000)
    return bookings.total


def form_context(booking):
    exam = booking.slot.examination
    rubrics = (
        ExaminationRubric.query.filter_by(examination_id=exam.id)
        .order_by(ExaminationRubric.position.asc())
        .all()
    )
    evaluation = Evaluation.query.filter_by(booking_id=booking.id).first()

    scores_map = {}
    comments_map = {}
    if evaluation:
        for sc in evaluation.scores:
            scores_map[sc.rubric_id] = sc.score
            comments_map[sc.rubric_id] = sc.comment

    return {
        "rubrics": rubrics,
        "scores_map": scores_map,
        "comments_map": comments_map,
        "remarks": evaluation.remarks if evaluation else "",
        "status": evaluation.status if evaluation else None,
        "locked": evaluation and evaluation.status == "published",
    }


def save_evaluation(
    examiner_id,
    booking_id,
    scores,
    comments=None,
    remarks="",
    action=None,
    submit=False,
):
    if action is None:
        action = "submit" if submit else "draft"
    if comments is None:
        comments = {}
    if remarks is None:
        remarks = ""
    booking = get_owned_booking(examiner_id, booking_id)
    if not booking:
        raise AppError("booking_not_found", "Booking not found or not evaluable.")

    exam = booking.slot.examination
    rubrics = ExaminationRubric.query.filter_by(examination_id=exam.id).all()
    if not rubrics:
        raise AppError("no_rubric", "Examination has no rubric criteria defined.")

    evaluation = Evaluation.query.filter_by(booking_id=booking_id).first()
    if evaluation and evaluation.status == "published":
        raise AppError("evaluation_locked", "Evaluation is locked and cannot be modified.")

    rubric_dict = {r.id: r for r in rubrics}

    total = Decimal("0.00")
    for r_id, val in scores.items():
        if r_id not in rubric_dict:
            raise AppError("invalid_rubric", "Invalid rubric criterion.")
        if val is not None:
            r_def = rubric_dict[r_id]
            max_criterion_score = Decimal(str(r_def.max_score))
            if not (Decimal("0") <= val <= max_criterion_score):
                raise AppError(
                    "score_out_of_range",
                    f"Score for {r_def.criterion_name} out of range (max {r_def.max_score}).",
                )
            total += val

    if total > exam.max_marks:
        raise AppError(
            "total_exceeds_max",
            f"Total marks ({total}) exceed examination maximum ({exam.max_marks}).",
        )

    if remarks and len(remarks) > 2000:
        raise AppError("remarks_too_long", "Remarks are too long (max 2000 characters).")

    if action in ["submit", "publish"]:
        for r_id in rubric_dict:
            if scores.get(r_id) is None:
                raise AppError(
                    "scores_incomplete", "All rubric criteria must be scored before submitting."
                )

    if not evaluation:
        evaluation = Evaluation(
            booking_id=booking_id,
            examiner_id=examiner_id,
            total_marks=Decimal("0.00"),
            status="draft",
        )
        db.session.add(evaluation)
        db.session.flush()

    evaluation.examiner_id = examiner_id
    evaluation.remarks = remarks or ""

    existing_scores = {sc.rubric_id: sc for sc in evaluation.scores}
    for r_id, val in scores.items():
        if val is None:
            if r_id in existing_scores:
                evaluation.scores.remove(existing_scores[r_id])
        else:
            q_val = val.quantize(Decimal("0.01"))
            if r_id in existing_scores:
                existing_scores[r_id].score = q_val
                existing_scores[r_id].comment = comments.get(r_id, "")
            else:
                new_sc = EvaluationScore(
                    evaluation=evaluation,
                    rubric_id=r_id,
                    score=q_val,
                    comment=comments.get(r_id, ""),
                )
                db.session.add(new_sc)

    db.session.flush()

    actual_total = sum(
        (Decimal(str(sc.score)) for sc in evaluation.scores), Decimal("0.00")
    ).quantize(Decimal("0.01"))
    evaluation.total_marks = actual_total

    now = windows.now_utc()
    if action in ("save_draft", "draft"):
        evaluation.status = "draft"
        audit_action = audit_service.EVALUATION_SAVE
    elif action == "submit":
        evaluation.status = "submitted"
        if not evaluation.submitted_at:
            evaluation.submitted_at = now
        audit_action = audit_service.EVALUATION_SUBMIT
    elif action == "publish":
        evaluation.status = "published"
        if not evaluation.submitted_at:
            evaluation.submitted_at = now
        if not evaluation.published_at:
            evaluation.published_at = now
        audit_action = audit_service.EVALUATION_PUBLISH
    else:
        raise AppError("invalid_action", "Invalid action.")

    audit_service.log_action(
        actor_id=examiner_id,
        action=audit_action,
        entity_type="evaluation",
        entity_id=evaluation.id,
        details={
            "booking_id": booking_id,
            "total": float(actual_total),
            "status": evaluation.status,
        },
    )
    db.session.commit()
    if action == "publish":
        hooks.emit(
            hooks.EVENT_EVALUATION_PUBLISHED,
            evaluation_id=evaluation.id,
            booking_id=booking.id,
            student_id=booking.student_id,
        )
    return evaluation


def published_for_student(student_id):
    return (
        Evaluation.query.join(Booking, Evaluation.booking_id == Booking.id)
        .filter(Booking.student_id == student_id, Evaluation.status == "published")
        .order_by(Evaluation.published_at.desc())
        .all()
    )


def publish_evaluation(examiner_id: int, evaluation_id: int) -> Evaluation:
    evaluation = db.session.get(Evaluation, evaluation_id)
    if not evaluation or evaluation.examiner_id != examiner_id:
        raise AppError("evaluation_not_found", "Evaluation not found.")
    if evaluation.status == "published":
        return evaluation
    now = windows.now_utc()
    evaluation.status = "published"
    if not evaluation.submitted_at:
        evaluation.submitted_at = now
    evaluation.published_at = now
    audit_service.log_action(
        actor_id=examiner_id,
        action=audit_service.EVALUATION_PUBLISH,
        entity_type="evaluation",
        entity_id=evaluation.id,
        details={
            "booking_id": evaluation.booking_id,
            "total": float(evaluation.total_marks),
            "status": "published",
        },
    )
    db.session.commit()
    hooks.emit(
        hooks.EVENT_EVALUATION_PUBLISHED,
        evaluation_id=evaluation.id,
        booking_id=evaluation.booking_id,
        student_id=evaluation.booking.student_id,
    )
    return evaluation


def admin_publish(actor_id: int, evaluation_id: int) -> Evaluation:
    actor = db.session.get(User, actor_id)
    if not actor or actor.role != "admin" or not actor.is_active:
        raise BookingError("not_an_admin", "Administrator privileges are required.")

    evaluation = db.session.get(Evaluation, evaluation_id)
    if not evaluation:
        raise BookingError("evaluation_not_found", "Evaluation not found.")
    if evaluation.status == "draft":
        raise BookingError(
            "evaluation_not_submitted", "Only submitted evaluations can be published."
        )
    if evaluation.status == "published":
        raise BookingError("evaluation_locked", "Evaluation is already published.")

    evaluation.status = "published"
    evaluation.published_at = windows.now_utc()

    audit_service.log_action(
        actor_id=actor_id,
        action=audit_service.EVALUATION_ADMIN_PUBLISH,
        entity_type="evaluation",
        entity_id=evaluation.id,
        details={"booking_id": evaluation.booking_id},
    )
    db.session.commit()
    hooks.emit(
        hooks.EVENT_EVALUATION_PUBLISHED,
        evaluation_id=evaluation.id,
        booking_id=evaluation.booking_id,
        student_id=evaluation.booking.student_id,
    )
    return evaluation


def list_evaluation_tracking(
    status: str | None = None,
    examiner_id: int | None = None,
    examination_id: int | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
):
    query = (
        db.session.query(Booking, Evaluation)
        .join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
        .join(User, Booking.student_id == User.id)
        .outerjoin(Evaluation, Evaluation.booking_id == Booking.id)
        .filter(
            Booking.status.in_(["booked", "completed"]),
            ExaminationSlot.status != "cancelled",
        )
    )

    if examiner_id:
        query = query.filter(ExaminationSlot.examiner_id == examiner_id)
    if examination_id:
        query = query.filter(Booking.examination_id == examination_id)
    if q:
        query = query.filter(User.full_name.ilike(f"%{q}%"))

    if status == "not_started":
        query = query.filter(Evaluation.id.is_(None))
    elif status in ("draft", "submitted", "published"):
        query = query.filter(Evaluation.status == status)

    rows = query.order_by(ExaminationSlot.start_at.desc()).all()

    wrapped = []
    for booking, evaluation in rows:
        state = evaluation.status if evaluation else "not_started"
        wrapped.append(
            {
                "booking": booking,
                "evaluation": evaluation,
                "tracking_state": state,
            }
        )

    total = len(wrapped)
    start = (page - 1) * per_page
    end = start + per_page
    items = wrapped[start:end]

    class TrackingPagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = max(1, (total + per_page - 1) // per_page)
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1

    return TrackingPagination(items, page, per_page, total)


def pending_by_examiner() -> list[tuple[User, int]]:
    rows = (
        db.session.query(User, func.count(Booking.id))
        .join(ExaminationSlot, ExaminationSlot.examiner_id == User.id)
        .join(Booking, Booking.slot_id == ExaminationSlot.id)
        .outerjoin(Evaluation, Evaluation.booking_id == Booking.id)
        .filter(
            User.role == "examiner",
            Booking.status.in_(["booked", "completed"]),
            ExaminationSlot.status != "cancelled",
            (Evaluation.id.is_(None)) | (Evaluation.status == "draft"),
        )
        .group_by(User.id)
        .order_by(func.count(Booking.id).desc())
        .all()
    )
    return [(user, int(count)) for user, count in rows]
