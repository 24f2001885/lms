"""
app/services/catalog_service.py - Catalog business operations for courses, exams, rubrics.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.extensions import db
from app.models.booking import Booking
from app.models.course import Course
from app.models.evaluation import Evaluation
from app.models.examination import Examination
from app.models.examination_examiner import ExaminationExaminer
from app.models.rubric import ExaminationRubric
from app.models.slot import ExaminationSlot
from app.models.user import User
from app.services import audit_service, exam_status


def create_course(
    actor_id: int, code: str, name: str, description: str | None, status: str = "active"
) -> Course:
    clean_code = code.strip().upper()
    existing = Course.query.filter(Course.code.ilike(clean_code)).first()
    if existing:
        raise AppError("duplicate_course_code", f"Course code '{clean_code}' is already in use.")

    course = Course(
        code=clean_code,
        name=name.strip(),
        description=description.strip() if description else None,
        status=status,
        created_by=actor_id,
    )
    db.session.add(course)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        raise AppError(
            "duplicate_course_code", f"Course code '{clean_code}' is already in use."
        ) from e

    audit_service.log_action(
        actor_id, audit_service.COURSE_CREATE, "course", course.id, {"code": course.code}
    )
    db.session.commit()
    return course


def update_course(
    actor_id: int, course_id: int, code: str, name: str, description: str | None, status: str
) -> Course:
    course = db.session.get(Course, course_id)
    if not course:
        raise AppError("course_not_found", "Course not found.")

    clean_code = code.strip().upper()
    existing = Course.query.filter(Course.code.ilike(clean_code), Course.id != course_id).first()
    if existing:
        raise AppError("duplicate_course_code", f"Course code '{clean_code}' is already in use.")

    course.code = clean_code
    course.name = name.strip()
    course.description = description.strip() if description else None
    course.status = status

    audit_service.log_action(
        actor_id,
        audit_service.COURSE_UPDATE,
        "course",
        course.id,
        {"code": course.code, "status": course.status},
    )
    db.session.commit()
    return course


def delete_course(actor_id: int, course_id: int) -> None:
    course = db.session.get(Course, course_id)
    if not course:
        raise AppError("course_not_found", "Course not found.")
    if course.examinations:
        raise AppError("course_in_use", "This course has examinations. Set it to inactive instead.")

    code = course.code
    db.session.delete(course)
    audit_service.log_action(
        actor_id, audit_service.COURSE_DELETE, "course", course_id, {"code": code}
    )
    db.session.commit()


def create_examination(actor_id: int, data: dict[str, Any]) -> Examination:
    course = db.session.get(Course, data["course_id"])
    if not course or course.status != "active":
        raise AppError("course_inactive", "Course must exist and be active.")

    if data["slot_creation_end"] <= data["slot_creation_start"]:
        raise AppError("invalid_window", "Slot creation end must be after slot creation start.")
    if data["booking_end"] <= data["booking_start"]:
        raise AppError("invalid_window", "Booking end must be after booking start.")
    if data["booking_start"] < data["slot_creation_end"]:
        raise AppError("invalid_window", "Booking start cannot be earlier than slot creation end.")

    cancellation_deadline = data.get("cancellation_deadline") or data["booking_end"]
    if cancellation_deadline < data["booking_start"]:
        raise AppError(
            "invalid_window", "Cancellation deadline cannot be earlier than booking start."
        )

    exam = Examination(
        course_id=data["course_id"],
        name=data["name"].strip(),
        description=data.get("description", "").strip() if data.get("description") else None,
        exam_type=data["exam_type"],
        duration_minutes=data["duration_minutes"],
        max_marks=data["max_marks"],
        slot_creation_start=data["slot_creation_start"],
        slot_creation_end=data["slot_creation_end"],
        booking_start=data["booking_start"],
        booking_end=data["booking_end"],
        cancellation_deadline=cancellation_deadline,
        slot_creation_open=data.get("slot_creation_open", False),
        booking_open=data.get("booking_open", False),
        status="draft",
        is_deleted=False,
    )
    db.session.add(exam)
    db.session.flush()

    exam_status.refresh_status(exam, actor_id=actor_id)
    audit_service.log_action(
        actor_id, audit_service.EXAM_CREATE, "examination", exam.id, {"name": exam.name}
    )
    db.session.commit()
    return exam


def update_examination(actor_id: int, exam_id: int, data: dict[str, Any]) -> Examination:
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        raise AppError("exam_not_found", "Examination not found.")

    if data["course_id"] != exam.course_id and exam.slots:
        raise AppError("course_locked", "Course cannot be changed once slots exist.")

    highest_eval = (
        db.session.query(func.max(Evaluation.total_marks))
        .join(Booking)
        .filter(Booking.examination_id == exam.id)
        .scalar()
    )
    if highest_eval is not None and data["max_marks"] < highest_eval:
        raise AppError(
            "marks_below_existing",
            f"Maximum marks cannot be lower than existing score {highest_eval}.",
        )

    if data["slot_creation_end"] <= data["slot_creation_start"]:
        raise AppError("invalid_window", "Slot creation end must be after slot creation start.")
    if data["booking_end"] <= data["booking_start"]:
        raise AppError("invalid_window", "Booking end must be after booking start.")
    if data["booking_start"] < data["slot_creation_end"]:
        raise AppError("invalid_window", "Booking start cannot be earlier than slot creation end.")

    exam.course_id = data["course_id"]
    exam.name = data["name"].strip()
    exam.description = data.get("description", "").strip() if data.get("description") else None
    exam.exam_type = data["exam_type"]
    exam.duration_minutes = data["duration_minutes"]
    exam.max_marks = data["max_marks"]
    exam.slot_creation_start = data["slot_creation_start"]
    exam.slot_creation_end = data["slot_creation_end"]
    exam.booking_start = data["booking_start"]
    exam.booking_end = data["booking_end"]
    exam.cancellation_deadline = data.get("cancellation_deadline") or data["booking_end"]

    exam_status.refresh_status(exam, actor_id=actor_id)
    audit_service.log_action(
        actor_id, audit_service.EXAM_UPDATE, "examination", exam.id, {"name": exam.name}
    )
    db.session.commit()
    return exam


def delete_examination(actor_id: int, exam_id: int) -> None:
    exam = db.session.get(Examination, exam_id)
    if not exam:
        raise AppError("exam_not_found", "Examination not found.")

    active_bookings = Booking.query.filter(
        Booking.examination_id == exam.id, Booking.status.in_(("booked", "completed"))
    ).count()
    if active_bookings > 0:
        raise AppError(
            "exam_has_bookings",
            "Cannot delete examination with active or completed student bookings.",
        )

    exam.is_deleted = True
    exam.slot_creation_open = False
    exam.booking_open = False
    exam.status = "closed"

    audit_service.log_action(
        actor_id, audit_service.EXAM_DELETE, "examination", exam.id, {"name": exam.name}
    )
    db.session.commit()


def rubric_weightage_total(exam_id: int) -> Decimal:
    val = (
        db.session.query(func.coalesce(func.sum(ExaminationRubric.weightage), 0))
        .filter_by(examination_id=exam_id)
        .scalar()
    )
    return Decimal(str(val))


def toggle_slot_creation(actor_id: int, exam_id: int, open_state: bool) -> Examination:
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        raise AppError("exam_not_found", "Examination not found.")

    if open_state:
        has_approved_examiner = (
            ExaminationExaminer.query.join(User, ExaminationExaminer.examiner_id == User.id)
            .filter(
                ExaminationExaminer.examination_id == exam.id,
                User.approval_status == "approved",
                User.is_active.is_(True),
            )
            .count()
            > 0
        )
        if not has_approved_examiner:
            raise AppError(
                "no_examiner_assigned",
                "At least one approved, active examiner must be assigned before opening slot creation.",
            )

    exam.slot_creation_open = open_state
    exam_status.refresh_status(exam, actor_id=actor_id)
    audit_service.log_action(
        actor_id,
        audit_service.EXAM_SLOT_CREATION_TOGGLE,
        "examination",
        exam.id,
        {"open": open_state},
    )
    db.session.commit()
    return exam


def toggle_booking(actor_id: int, exam_id: int, open_state: bool) -> Examination:
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        raise AppError("exam_not_found", "Examination not found.")

    if open_state:
        total = rubric_weightage_total(exam.id)
        if abs(total - Decimal("100.00")) > Decimal("0.01"):
            raise AppError(
                "rubric_total_not_100",
                f"Rubric weightage must total exactly 100% (currently {total}%).",
            )

    exam.booking_open = open_state
    exam_status.refresh_status(exam, actor_id=actor_id)
    audit_service.log_action(
        actor_id, audit_service.EXAM_BOOKING_TOGGLE, "examination", exam.id, {"open": open_state}
    )
    db.session.commit()
    return exam


def add_rubric(
    actor_id: int,
    exam_id: int,
    criterion_name: str,
    description: str | None,
    weightage: Decimal,
    max_score: Decimal,
) -> ExaminationRubric:
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        raise AppError("exam_not_found", "Examination not found.")

    has_evals = (
        db.session.query(Evaluation).join(Booking).filter(Booking.examination_id == exam.id).count()
        > 0
    )
    if has_evals:
        raise AppError(
            "rubric_locked", "Rubrics cannot be modified after evaluations have been recorded."
        )

    clean_name = criterion_name.strip()
    existing = ExaminationRubric.query.filter_by(
        examination_id=exam.id, criterion_name=clean_name
    ).first()
    if existing:
        raise AppError("duplicate_criterion", f"A criterion named '{clean_name}' already exists.")

    current_total = rubric_weightage_total(exam.id)
    if current_total + weightage > Decimal("100.00"):
        raise AppError(
            "weightage_over_100",
            f"Adding {weightage}% would exceed 100% (currently {current_total}%).",
        )

    rubric = ExaminationRubric(
        examination_id=exam.id,
        criterion_name=clean_name,
        description=description.strip() if description else None,
        weightage=weightage,
        max_score=max_score,
        position=len(exam.rubrics),
    )
    db.session.add(rubric)
    audit_service.log_action(
        actor_id,
        audit_service.RUBRIC_ADD,
        "examination_rubric",
        exam.id,
        {"criterion": clean_name, "weightage": str(weightage)},
    )
    db.session.commit()
    return rubric


def delete_rubric(actor_id: int, rubric_id: int) -> None:
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if not rubric:
        raise AppError("rubric_not_found", "Rubric not found.")

    has_evals = (
        db.session.query(Evaluation)
        .join(Booking)
        .filter(Booking.examination_id == rubric.examination_id)
        .count()
        > 0
    )
    if has_evals:
        raise AppError(
            "rubric_locked", "Rubrics cannot be modified after evaluations have been recorded."
        )

    exam_id = rubric.examination_id
    name = rubric.criterion_name
    db.session.delete(rubric)
    audit_service.log_action(
        actor_id,
        audit_service.RUBRIC_DELETE,
        "examination_rubric",
        rubric_id,
        {"exam_id": exam_id, "criterion": name},
    )
    db.session.commit()


def assign_examiner(actor_id: int, exam_id: int, examiner_id: int) -> ExaminationExaminer:
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        raise AppError("exam_not_found", "Examination not found.")

    examiner = db.session.get(User, examiner_id)
    if (
        not examiner
        or examiner.role != "examiner"
        or examiner.approval_status != "approved"
        or not examiner.is_active
    ):
        raise AppError(
            "examiner_not_eligible", "Selected user is not an approved, active examiner."
        )

    existing = ExaminationExaminer.query.filter_by(
        examination_id=exam.id, examiner_id=examiner.id
    ).first()
    if existing:
        raise AppError("already_assigned", "Examiner is already assigned to this examination.")

    assignment = ExaminationExaminer(
        examination_id=exam.id, examiner_id=examiner.id, assigned_by=actor_id
    )
    db.session.add(assignment)
    audit_service.log_action(
        actor_id,
        audit_service.EXAM_EXAMINER_ASSIGN,
        "examination",
        exam.id,
        {"examiner_id": examiner.id},
    )
    db.session.commit()
    return assignment


def unassign_examiner(actor_id: int, exam_id: int, examiner_id: int) -> None:
    assignment = ExaminationExaminer.query.filter_by(
        examination_id=exam_id, examiner_id=examiner_id
    ).first()
    if not assignment:
        raise AppError("assignment_not_found", "Assignment not found.")

    active_slots = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_id,
        ExaminationSlot.examiner_id == examiner_id,
        ExaminationSlot.status != "cancelled",
    ).count()
    if active_slots > 0:
        raise AppError(
            "examiner_has_slots",
            "Cannot unassign examiner: Examiner owns active slots for this examination. Reassign slots first.",
        )

    db.session.delete(assignment)
    audit_service.log_action(
        actor_id,
        audit_service.EXAM_EXAMINER_UNASSIGN,
        "examination",
        exam_id,
        {"examiner_id": examiner_id},
    )
    db.session.commit()
