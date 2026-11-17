"""
FILE PURPOSE: Builds the data for every chart, already scoped to the viewer's role.
Pure data: no Flask objects, no JSON responses, no HTML. Used by chart endpoints.
"""

from collections import defaultdict
from datetime import timedelta

from app.errors import AppError
from app.models.booking import Booking
from app.models.evaluation import Evaluation
from app.models.examination import Examination
from app.models.examination_examiner import ExaminationExaminer
from app.models.slot import ExaminationSlot
from app.models.user import User
from app.services import windows


def validate_days(value) -> int:
    """Validate days query parameter: 1..180 integer."""
    try:
        days = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"Days must be an integer, got {value!r}") from None
    if days < 1 or days > 180:
        raise ValueError(f"Days must be between 1 and 180, got {days}")
    return days


def bookings_by_day(user: User, days: int = 30) -> dict:
    """
    Daily count of bookings and cancellations over the last `days` local days.
    zero-filled, ending on local today.
    """
    days = validate_days(days)
    now = windows.now_utc()
    today_local = windows.to_local(now).date()
    start_local = today_local - timedelta(days=days - 1)

    labels = [(start_local + timedelta(days=i)).isoformat() for i in range(days)]
    booked_counts: dict[str, int] = {lbl: 0 for lbl in labels}
    cancelled_counts: dict[str, int] = {lbl: 0 for lbl in labels}

    if user.role == "admin":
        rows = Booking.query.with_entities(Booking.booked_at, Booking.cancelled_at).all()
    elif user.role == "examiner":
        rows = (
            Booking.query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
            .filter(ExaminationSlot.examiner_id == user.id)
            .with_entities(Booking.booked_at, Booking.cancelled_at)
            .all()
        )
    elif user.role == "student":
        rows = (
            Booking.query.filter(Booking.student_id == user.id)
            .with_entities(Booking.booked_at, Booking.cancelled_at)
            .all()
        )
    else:
        raise AppError(
            "forbidden", "You do not have permission to view this chart.", http_status=403
        )

    for b_at, c_at in rows:
        if b_at:
            b_local = windows.to_local(b_at).date().isoformat()
            if b_local in booked_counts:
                booked_counts[b_local] += 1
        if c_at:
            c_local = windows.to_local(c_at).date().isoformat()
            if c_local in cancelled_counts:
                cancelled_counts[c_local] += 1

    series = [
        {"name": "Booked", "data": [booked_counts[lbl] for lbl in labels]},
        {"name": "Cancelled", "data": [cancelled_counts[lbl] for lbl in labels]},
    ]
    return {"labels": labels, "series": series}


def booking_status(user: User) -> dict:
    """
    Counts of bookings by status (Booked, Completed, Cancelled) scoped to user.
    """
    labels = ["Booked", "Completed", "Cancelled"]

    if user.role == "admin":
        rows = Booking.query.with_entities(Booking.status).all()
    elif user.role == "examiner":
        rows = (
            Booking.query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
            .filter(ExaminationSlot.examiner_id == user.id)
            .with_entities(Booking.status)
            .all()
        )
    elif user.role == "student":
        rows = (
            Booking.query.filter(Booking.student_id == user.id).with_entities(Booking.status).all()
        )
    else:
        raise AppError(
            "forbidden", "You do not have permission to view this chart.", http_status=403
        )

    counts = {"booked": 0, "completed": 0, "cancelled": 0}
    for (st,) in rows:
        if st in counts:
            counts[st] += 1

    series = [
        {
            "name": "Bookings",
            "data": [counts["booked"], counts["completed"], counts["cancelled"]],
        }
    ]
    return {"labels": labels, "series": series}


def participants_by_slot(user: User, limit: int = 12) -> dict:
    """
    Next `limit` non-cancelled future slots by start_at. Admin & Examiner only.
    """
    if user.role == "student":
        raise AppError("forbidden", "Students cannot view participant charts.", http_status=403)
    if user.role not in ("admin", "examiner"):
        raise AppError(
            "forbidden", "You do not have permission to view this chart.", http_status=403
        )

    now = windows.now_utc()
    query = (
        ExaminationSlot.query.join(Examination, ExaminationSlot.examination_id == Examination.id)
        .filter(
            Examination.is_deleted.is_(False),
            ExaminationSlot.status != "cancelled",
            ExaminationSlot.start_at >= now,
        )
        .order_by(ExaminationSlot.start_at.asc())
    )

    if user.role == "examiner":
        query = query.filter(ExaminationSlot.examiner_id == user.id)

    slots = query.limit(limit).all()

    labels = []
    booked_data = []
    free_data = []

    for slot in slots:
        local_dt = windows.to_local(slot.start_at)
        lbl = f"{local_dt.strftime('%d %b %H:%M')} {slot.examination.name}"[:28]
        labels.append(lbl)
        booked = int(slot.booked_count)
        free = int(max(0, slot.max_capacity - slot.booked_count))
        booked_data.append(booked)
        free_data.append(free)

    series = [
        {"name": "Booked", "data": booked_data},
        {"name": "Seats free", "data": free_data},
    ]
    return {"labels": labels, "series": series}


def examiner_workload(user: User) -> dict:
    """
    Admin: workload per examiner (slots, booked students, not yet submitted).
    Examiner: own view per examination (slots, booked students, evaluated).
    """
    if user.role == "student":
        raise AppError("forbidden", "Students cannot view examiner workload.", http_status=403)

    if user.role == "admin":
        examiners = User.query.filter_by(role="examiner").all()
        items = []
        for ex in examiners:
            slots = ExaminationSlot.query.filter(
                ExaminationSlot.examiner_id == ex.id,
                ExaminationSlot.status != "cancelled",
            ).all()
            slot_ids = [s.id for s in slots]
            if slot_ids:
                bookings = Booking.query.filter(
                    Booking.slot_id.in_(slot_ids),
                    Booking.status.in_(["booked", "completed"]),
                ).all()
            else:
                bookings = []

            booked_count = len(bookings)
            not_yet_submitted = sum(
                1 for b in bookings if not b.evaluation or b.evaluation.status == "draft"
            )

            # Include examiners who have at least slots or bookings
            if slots or bookings:
                items.append(
                    {
                        "name": ex.full_name,
                        "slots": len(slots),
                        "booked_students": booked_count,
                        "not_yet_submitted": not_yet_submitted,
                    }
                )

        items.sort(key=lambda x: x["booked_students"], reverse=True)
        top = items[:12]

        labels = [x["name"] for x in top]
        series = [
            {"name": "Slots", "data": [x["slots"] for x in top]},
            {"name": "Booked students", "data": [x["booked_students"] for x in top]},
            {"name": "Not yet submitted", "data": [x["not_yet_submitted"] for x in top]},
        ]
        return {"labels": labels, "series": series}

    elif user.role == "examiner":
        # Own view: examinations where examiner has slots or is assigned
        slots = ExaminationSlot.query.filter(
            ExaminationSlot.examiner_id == user.id,
            ExaminationSlot.status != "cancelled",
        ).all()

        exam_slots: dict[int, list[ExaminationSlot]] = defaultdict(list)
        for s in slots:
            exam_slots[s.examination_id].append(s)

        # Also get assigned examinations
        assigned = (
            Examination.query.join(
                ExaminationExaminer, Examination.id == ExaminationExaminer.examination_id
            )
            .filter(
                ExaminationExaminer.examiner_id == user.id,
                Examination.is_deleted.is_(False),
            )
            .all()
        )

        exam_dict: dict[int, Examination] = {e.id: e for e in assigned}
        for s in slots:
            if s.examination and not s.examination.is_deleted:
                exam_dict[s.examination_id] = s.examination

        items = []
        for exam_id, exam in exam_dict.items():
            curr_slots = exam_slots.get(exam_id, [])
            slot_ids = [s.id for s in curr_slots]
            if slot_ids:
                bookings = Booking.query.filter(
                    Booking.slot_id.in_(slot_ids),
                    Booking.status.in_(["booked", "completed"]),
                ).all()
            else:
                bookings = []

            booked_count = len(bookings)
            evaluated_count = sum(
                1
                for b in bookings
                if b.evaluation and b.evaluation.status in ("submitted", "published")
            )

            if curr_slots or bookings:
                items.append(
                    {
                        "name": exam.name,
                        "slots": len(curr_slots),
                        "booked_students": booked_count,
                        "evaluated": evaluated_count,
                    }
                )

        items.sort(key=lambda x: x["booked_students"], reverse=True)
        top = items[:12]

        labels = [x["name"] for x in top]
        series = [
            {"name": "Slots", "data": [x["slots"] for x in top]},
            {"name": "Booked students", "data": [x["booked_students"] for x in top]},
            {"name": "Evaluated", "data": [x["evaluated"] for x in top]},
        ]
        return {"labels": labels, "series": series}

    else:
        raise AppError(
            "forbidden", "You do not have permission to view this chart.", http_status=403
        )


def examination_completion(user: User, limit: int = 12) -> dict:
    """
    Most recent `limit` examinations by booking_start.
    Series: Booked, Evaluation submitted, Published.
    """
    if user.role == "student":
        raise AppError("forbidden", "Students cannot view examination completion.", http_status=403)
    if user.role not in ("admin", "examiner"):
        raise AppError(
            "forbidden", "You do not have permission to view this chart.", http_status=403
        )

    query = Examination.query.filter(Examination.is_deleted.is_(False))
    if user.role == "examiner":
        query = query.join(
            ExaminationExaminer, Examination.id == ExaminationExaminer.examination_id
        ).filter(ExaminationExaminer.examiner_id == user.id)

    exams = query.order_by(Examination.booking_start.desc()).limit(limit).all()

    labels = []
    booked_data = []
    submitted_data = []
    published_data = []

    for exam in exams:
        if user.role == "admin":
            bookings = Booking.query.filter(
                Booking.examination_id == exam.id,
                Booking.status.in_(["booked", "completed"]),
            ).all()
        else:
            bookings = (
                Booking.query.join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
                .filter(
                    Booking.examination_id == exam.id,
                    ExaminationSlot.examiner_id == user.id,
                    Booking.status.in_(["booked", "completed"]),
                )
                .all()
            )

        labels.append(exam.name)
        booked_data.append(len(bookings))
        submitted_data.append(
            sum(
                1
                for b in bookings
                if b.evaluation and b.evaluation.status in ("submitted", "published")
            )
        )
        published_data.append(
            sum(1 for b in bookings if b.evaluation and b.evaluation.status == "published")
        )

    series = [
        {"name": "Booked", "data": booked_data},
        {"name": "Evaluation submitted", "data": submitted_data},
        {"name": "Published", "data": published_data},
    ]
    return {"labels": labels, "series": series}


def results(user: User, limit: int = 12) -> dict:
    """
    Student: own score percentages per exam (published only).
    Examiner: average score % per exam for own slots (published only).
    Admin: average score % per exam overall (published only).
    """
    if user.role == "student":
        evals = (
            Evaluation.query.join(Booking, Evaluation.booking_id == Booking.id)
            .join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
            .join(Examination, ExaminationSlot.examination_id == Examination.id)
            .filter(
                Booking.student_id == user.id,
                Evaluation.status == "published",
                Examination.is_deleted.is_(False),
            )
            .order_by(Evaluation.published_at.desc(), Evaluation.id.desc())
            .limit(limit)
            .all()
        )

        labels = []
        scores = []
        for ev in evals:
            exam = ev.booking.slot.examination
            pct = round(float(ev.total_marks / exam.max_marks * 100), 1)
            labels.append(exam.name)
            scores.append(pct)

        series = [{"name": "Score %", "data": scores}]
        return {"labels": labels, "series": series}

    elif user.role in ("admin", "examiner"):
        query = (
            Evaluation.query.join(Booking, Evaluation.booking_id == Booking.id)
            .join(ExaminationSlot, Booking.slot_id == ExaminationSlot.id)
            .join(Examination, ExaminationSlot.examination_id == Examination.id)
            .filter(
                Evaluation.status == "published",
                Examination.is_deleted.is_(False),
            )
        )
        if user.role == "examiner":
            query = query.filter(ExaminationSlot.examiner_id == user.id)

        evals = query.all()

        exam_map = {}
        for ev in evals:
            exam = ev.booking.slot.examination
            pct = float(ev.total_marks / exam.max_marks * 100)
            if exam.id not in exam_map:
                exam_map[exam.id] = {
                    "name": exam.name,
                    "scores": [],
                    "order": exam.booking_start,
                }
            exam_map[exam.id]["scores"].append(pct)

        sorted_exams = sorted(exam_map.values(), key=lambda x: x["order"], reverse=True)[:limit]
        labels = [e["name"] for e in sorted_exams]
        averages = [round(sum(e["scores"]) / len(e["scores"]), 1) for e in sorted_exams]
        series = [{"name": "Average %", "data": averages}]
        return {"labels": labels, "series": series}

    else:
        raise AppError(
            "forbidden", "You do not have permission to view this chart.", http_status=403
        )
