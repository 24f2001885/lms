"""
app/blueprints/admin/routes.py - Administrator control panel routes (Screens ADM-01 to ADM-18).

Delivers the 6-metric dashboard, Course/Exam CRUD, Rubric criteria manager,
Examiner approval queue, Slot examiner reassignment, Booking rescheduling,
Global search, and complete Audit history.
"""

import logging

from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.extensions import db
from app.forms.admin import (
    AssignExaminerForm,
    ChangeSlotExaminerForm,
    CourseForm,
    ExaminationForm,
    RescheduleBookingForm,
    RubricForm,
    SetTemporaryPasswordForm,
)
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.course import Course
from app.models.examination import Examination
from app.models.examination_examiner import ExaminationExaminer
from app.models.examination_rubric import ExaminationRubric
from app.models.examination_slot import ExaminationSlot
from app.models.user import User
from app.security.auth_helpers import get_current_user
from app.security.decorators import admin_required
from app.services.audit_service import log_audit
from app.services.exam_status import sync_examination_status
from app.services.search_service import search_all_entities
from app.services.windows import now_utc

logger = logging.getLogger("lms")


# ---------------------------------------------------------------------
# ADM-01: Admin Dashboard (Six Key Metrics)
# ---------------------------------------------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    """Display overall metrics dashboard across all portal resources."""
    stats = {
        "courses": Course.query.count(),
        "examinations": Examination.query.filter_by(is_deleted=False).count(),
        "examiners_approved": User.query.filter_by(
            role="examiner", approval_status="approved"
        ).count(),
        "examiners_pending": User.query.filter_by(
            role="examiner", approval_status="pending"
        ).count(),
        "students": User.query.filter_by(role="student").count(),
        "slots": ExaminationSlot.query.count(),
        "bookings": Booking.query.count(),
    }
    recent_exams = (
        Examination.query.filter_by(is_deleted=False).order_by(Examination.id.desc()).limit(5).all()
    )
    recent_audits = AuditLog.query.order_by(AuditLog.id.desc()).limit(5).all()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_exams=recent_exams,
        recent_audits=recent_audits,
    )


# ---------------------------------------------------------------------
# ADM-02 & ADM-03: Course Management
# ---------------------------------------------------------------------
@admin_bp.route("/courses", methods=["GET", "POST"])
@admin_required
def courses():
    """List all courses and handle new course creation (ADM-02, ADM-03)."""
    form = CourseForm()
    if form.validate_on_submit():
        admin = get_current_user()
        new_course = Course(
            code=form.code.data.strip().upper(),
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            status=form.status.data,
            created_by=admin.id,
        )
        db.session.add(new_course)
        db.session.commit()
        log_audit("course.create", "course", new_course.id, {"code": new_course.code})
        flash(f"Course '{new_course.code}' created successfully.", "success")
        return redirect(url_for("admin.courses"))

    all_courses = Course.query.order_by(Course.code.asc()).all()
    return render_template("admin/courses.html", courses=all_courses, form=form)


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_course(course_id: int):
    """Edit existing course metadata."""
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)

    form = CourseForm(original_course_id=course.id, obj=course)
    if form.validate_on_submit():
        course.code = form.code.data.strip().upper()
        course.name = form.name.data.strip()
        course.description = form.description.data.strip() if form.description.data else None
        course.status = form.status.data
        db.session.commit()
        log_audit("course.update", "course", course.id, {"code": course.code})
        flash(f"Course '{course.code}' updated successfully.", "success")
        return redirect(url_for("admin.courses"))

    return render_template("admin/course_edit.html", course=course, form=form)


@admin_bp.route("/courses/<int:course_id>/toggle", methods=["POST"])
@admin_required
def toggle_course(course_id: int):
    """Toggle course status between active and inactive."""
    course = db.session.get(Course, course_id)
    if not course:
        abort(404)

    course.status = "inactive" if course.status == "active" else "active"
    db.session.commit()
    log_audit("course.toggle", "course", course.id, {"new_status": course.status})
    flash(f"Course '{course.code}' is now {course.status}.", "info")
    return redirect(url_for("admin.courses"))


# ---------------------------------------------------------------------
# ADM-04, ADM-05 & ADM-06: Examination Management & Timeline Switches
# ---------------------------------------------------------------------
@admin_bp.route("/examinations", methods=["GET"])
@admin_required
def examinations():
    """List all examinations with course and status filters (ADM-04)."""
    course_id = request.args.get("course_id", type=int)
    status_filter = request.args.get("status")

    query = Examination.query.filter_by(is_deleted=False)
    if course_id:
        query = query.filter_by(course_id=course_id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    all_exams = query.order_by(Examination.id.desc()).all()
    courses_list = Course.query.filter_by(status="active").all()
    return render_template("admin/examinations.html", examinations=all_exams, courses=courses_list)


@admin_bp.route("/examinations/create", methods=["GET", "POST"])
@admin_required
def create_examination():
    """Create a new examination offering (ADM-05)."""
    form = ExaminationForm()
    # Populate course choices dynamically
    form.course_id.choices = [
        (c.id, f"{c.code} - {c.name}") for c in Course.query.filter_by(status="active").all()
    ]

    if form.validate_on_submit():
        cancellation_deadline = form.cancellation_deadline.data or form.booking_end.data

        new_exam = Examination(
            course_id=form.course_id.data,
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            exam_type=form.exam_type.data,
            duration_minutes=form.duration_minutes.data,
            max_marks=form.max_marks.data,
            slot_creation_start=form.slot_creation_start.data,
            slot_creation_end=form.slot_creation_end.data,
            booking_start=form.booking_start.data,
            booking_end=form.booking_end.data,
            cancellation_deadline=cancellation_deadline,
            slot_creation_open=form.slot_creation_open.data,
            booking_open=form.booking_open.data,
            status="draft",
        )
        db.session.add(new_exam)
        db.session.commit()

        # Compute initial state
        sync_examination_status(new_exam)
        log_audit("exam.create", "examination", new_exam.id, {"name": new_exam.name})
        flash(f"Examination '{new_exam.name}' created successfully.", "success")
        return redirect(url_for("admin.examination_detail", exam_id=new_exam.id))

    return render_template("admin/examination_create.html", form=form)


@admin_bp.route("/examinations/<int:exam_id>", methods=["GET"])
@admin_required
def examination_detail(exam_id: int):
    """Detailed examination management: timelines, rubrics, and examiners (ADM-06)."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    # Re-sync status dynamically based on current time and slot states
    sync_examination_status(exam)

    rubric_form = RubricForm()
    assign_form = AssignExaminerForm()

    # Get approved examiners not yet assigned to this examination
    assigned_ids = [a.examiner_id for a in exam.examiner_links]
    available_examiners = User.query.filter(
        User.role == "examiner",
        User.approval_status == "approved",
        User.is_active.is_(True),
        ~User.id.in_(assigned_ids) if assigned_ids else True,
    ).all()
    assign_form.examiner_id.choices = [
        (e.id, f"{e.full_name} ({e.email})") for e in available_examiners
    ]

    total_weightage = sum(r.weightage for r in exam.rubrics)

    return render_template(
        "admin/examination_detail.html",
        exam=exam,
        rubric_form=rubric_form,
        assign_form=assign_form,
        total_weightage=total_weightage,
        now=now_utc(),
    )


@admin_bp.route("/examinations/<int:exam_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_examination(exam_id: int):
    """Edit examination parameters and timeline windows."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    form = ExaminationForm(obj=exam)
    form.course_id.choices = [(c.id, f"{c.code} - {c.name}") for c in Course.query.all()]

    if form.validate_on_submit():
        exam.course_id = form.course_id.data
        exam.name = form.name.data.strip()
        exam.description = form.description.data.strip() if form.description.data else None
        exam.exam_type = form.exam_type.data
        exam.duration_minutes = form.duration_minutes.data
        exam.max_marks = form.max_marks.data
        exam.slot_creation_start = form.slot_creation_start.data
        exam.slot_creation_end = form.slot_creation_end.data
        exam.booking_start = form.booking_start.data
        exam.booking_end = form.booking_end.data
        exam.cancellation_deadline = form.cancellation_deadline.data or form.booking_end.data
        exam.slot_creation_open = form.slot_creation_open.data
        exam.booking_open = form.booking_open.data

        db.session.commit()
        sync_examination_status(exam)
        log_audit("exam.update", "examination", exam.id, {"name": exam.name})
        flash(f"Examination '{exam.name}' updated successfully.", "success")
        return redirect(url_for("admin.examination_detail", exam_id=exam.id))

    return render_template("admin/examination_edit.html", exam=exam, form=form)


@admin_bp.route("/examinations/<int:exam_id>/slot-creation/toggle", methods=["POST"])
@admin_required
def toggle_slot_creation(exam_id: int):
    """Toggle slot creation open/closed switch."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    exam.slot_creation_open = not exam.slot_creation_open
    db.session.commit()
    sync_examination_status(exam)
    log_audit(
        "exam.slot_creation_toggle", "examination", exam.id, {"open": exam.slot_creation_open}
    )
    status_label = "opened" if exam.slot_creation_open else "closed"
    flash(f"Slot creation {status_label} for '{exam.name}'.", "info")
    return redirect(url_for("admin.examination_detail", exam_id=exam.id))


@admin_bp.route("/examinations/<int:exam_id>/booking/toggle", methods=["POST"])
@admin_required
def toggle_booking(exam_id: int):
    """Toggle student booking open/closed switch."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    exam.booking_open = not exam.booking_open
    db.session.commit()
    sync_examination_status(exam)
    log_audit("exam.booking_toggle", "examination", exam.id, {"open": exam.booking_open})
    status_label = "opened" if exam.booking_open else "closed"
    flash(f"Student booking {status_label} for '{exam.name}'.", "info")
    return redirect(url_for("admin.examination_detail", exam_id=exam.id))


@admin_bp.route("/examinations/<int:exam_id>/delete", methods=["POST"])
@admin_required
def delete_examination(exam_id: int):
    """Soft delete an examination to preserve historical student transcripts."""
    exam = db.session.get(Examination, exam_id)
    if not exam:
        abort(404)

    exam.is_deleted = True
    exam.status = "closed"
    exam.slot_creation_open = False
    exam.booking_open = False
    db.session.commit()
    log_audit("exam.soft_delete", "examination", exam.id, {"name": exam.name})
    flash(f"Examination '{exam.name}' deleted.", "warning")
    return redirect(url_for("admin.examinations"))


# ---------------------------------------------------------------------
# ADM-07: Rubric Criteria Management
# ---------------------------------------------------------------------
@admin_bp.route("/examinations/<int:exam_id>/rubrics", methods=["POST"])
@admin_required
def add_rubric(exam_id: int):
    """Add a new scoring criterion to an examination (ADM-07)."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    form = RubricForm()
    if form.validate_on_submit():
        existing_criteria = [r.criterion_name.lower() for r in exam.rubrics]
        if form.criterion_name.data.strip().lower() in existing_criteria:
            flash(
                f"Criterion '{form.criterion_name.data}' already exists on this examination.",
                "danger",
            )
            return redirect(url_for("admin.examination_detail", exam_id=exam.id))

        new_rubric = ExaminationRubric(
            examination_id=exam.id,
            criterion_name=form.criterion_name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            weightage=form.weightage.data,
            max_score=form.max_score.data,
            position=len(exam.rubrics),
        )
        db.session.add(new_rubric)
        db.session.commit()
        log_audit("rubric.add", "examination_rubric", new_rubric.id, {"exam_id": exam.id})
        flash(f"Criterion '{new_rubric.criterion_name}' added.", "success")
    else:
        for errs in form.errors.values():
            for e in errs:
                flash(e, "danger")

    return redirect(url_for("admin.examination_detail", exam_id=exam.id))


@admin_bp.route("/rubrics/<int:rubric_id>/delete", methods=["POST"])
@admin_required
def delete_rubric(rubric_id: int):
    """Delete a rubric criterion."""
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if not rubric:
        abort(404)

    exam_id = rubric.examination_id
    db.session.delete(rubric)
    db.session.commit()
    log_audit("rubric.delete", "examination_rubric", rubric_id, {"exam_id": exam_id})
    flash("Rubric criterion deleted.", "info")
    return redirect(url_for("admin.examination_detail", exam_id=exam_id))


# ---------------------------------------------------------------------
# ADM-08: Examiner Assignment to Examination
# ---------------------------------------------------------------------
@admin_bp.route("/examinations/<int:exam_id>/examiners/assign", methods=["POST"])
@admin_required
def assign_examiner(exam_id: int):
    """Assign an approved examiner to an examination (ADM-08)."""
    exam = db.session.get(Examination, exam_id)
    if not exam or exam.is_deleted:
        abort(404)

    form = AssignExaminerForm()
    # Populate choices dynamically to validate
    available_examiners = User.query.filter_by(
        role="examiner", approval_status="approved", is_active=True
    ).all()
    form.examiner_id.choices = [(e.id, e.full_name) for e in available_examiners]

    if form.validate_on_submit():
        admin = get_current_user()
        assignment = ExaminationExaminer(
            examination_id=exam.id,
            examiner_id=form.examiner_id.data,
            assigned_by=admin.id,
        )
        db.session.add(assignment)
        db.session.commit()
        log_audit(
            "exam.assign_examiner", "examination", exam.id, {"examiner_id": assignment.examiner_id}
        )
        flash("Examiner assigned successfully.", "success")
    else:
        flash("Invalid examiner selection.", "danger")

    return redirect(url_for("admin.examination_detail", exam_id=exam.id))


@admin_bp.route(
    "/examinations/<int:exam_id>/examiners/<int:examiner_id>/unassign", methods=["POST"]
)
@admin_required
def unassign_examiner(exam_id: int, examiner_id: int):
    """Remove examiner assignment from an examination."""
    assignment = ExaminationExaminer.query.filter_by(
        examination_id=exam_id, examiner_id=examiner_id
    ).first()
    if assignment:
        # Check if examiner has active slots
        has_slots = (
            ExaminationSlot.query.filter_by(examination_id=exam_id, examiner_id=examiner_id).count()
            > 0
        )
        if has_slots:
            flash(
                "Cannot unassign examiner: Examiner has created slots for this examination.",
                "danger",
            )
        else:
            db.session.delete(assignment)
            db.session.commit()
            log_audit(
                "exam.unassign_examiner", "examination", exam_id, {"examiner_id": examiner_id}
            )
            flash("Examiner unassigned.", "info")

    return redirect(url_for("admin.examination_detail", exam_id=exam_id))


# ---------------------------------------------------------------------
# ADM-09 & ADM-10: Examiner Approval Queue & Management
# ---------------------------------------------------------------------
@admin_bp.route("/examiners", methods=["GET"])
@admin_required
def examiners():
    """List examiners with status filter (approved, pending, inactive) (ADM-09)."""
    status_filter = request.args.get("status", "all")
    query = User.query.filter_by(role="examiner")

    if status_filter == "pending":
        query = query.filter_by(approval_status="pending")
    elif status_filter == "approved":
        query = query.filter_by(approval_status="approved", is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)

    examiners_list = query.order_by(User.id.desc()).all()
    return render_template(
        "admin/examiners.html", examiners=examiners_list, current_status=status_filter
    )


@admin_bp.route("/examiners/<int:user_id>", methods=["GET", "POST"])
@admin_required
def examiner_detail(user_id: int):
    """View examiner profile and handle temporary password reset (ADM-10)."""
    examiner = db.session.get(User, user_id)
    if not examiner or examiner.role != "examiner":
        abort(404)

    password_form = SetTemporaryPasswordForm()
    if password_form.validate_on_submit():
        examiner.set_password(password_form.temporary_password.data)
        examiner.must_change_password = True
        db.session.commit()
        log_audit("user.temp_password", "user", examiner.id, {"target_email": examiner.email})
        flash(
            f"Temporary password set for '{examiner.email}'. Forced update required at next login.",
            "success",
        )
        return redirect(url_for("admin.examiner_detail", user_id=examiner.id))

    return render_template(
        "admin/examiner_detail.html", examiner=examiner, password_form=password_form
    )


@admin_bp.route("/examiners/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_examiner(user_id: int):
    """Approve a pending examiner account."""
    examiner = db.session.get(User, user_id)
    if not examiner or examiner.role != "examiner":
        abort(404)

    examiner.approval_status = "approved"
    examiner.is_active = True
    db.session.commit()
    log_audit("examiner.approve", "user", examiner.id, {"email": examiner.email})
    flash(f"Examiner '{examiner.full_name}' approved.", "success")
    return redirect(request.referrer or url_for("admin.examiners"))


@admin_bp.route("/examiners/<int:user_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_examiner(user_id: int):
    """Deactivate an examiner account (enforcing immediate logout)."""
    examiner = db.session.get(User, user_id)
    if not examiner or examiner.role != "examiner":
        abort(404)

    examiner.is_active = False
    db.session.commit()
    log_audit("examiner.deactivate", "user", examiner.id, {"email": examiner.email})
    flash(f"Examiner '{examiner.full_name}' has been deactivated.", "warning")
    return redirect(request.referrer or url_for("admin.examiners"))


# ---------------------------------------------------------------------
# ADM-11 & ADM-12: Student Management
# ---------------------------------------------------------------------
@admin_bp.route("/students", methods=["GET"])
@admin_required
def students():
    """Directory of enrolled student accounts (ADM-11)."""
    students_list = User.query.filter_by(role="student").order_by(User.id.desc()).all()
    return render_template("admin/students.html", students=students_list)


@admin_bp.route("/students/<int:user_id>", methods=["GET"])
@admin_required
def student_detail(user_id: int):
    """Student profile detail and historical examination bookings (ADM-12)."""
    student = db.session.get(User, user_id)
    if not student or student.role != "student":
        abort(404)

    bookings_list = Booking.query.filter_by(student_id=student.id).order_by(Booking.id.desc()).all()
    return render_template("admin/student_detail.html", student=student, bookings=bookings_list)


# ---------------------------------------------------------------------
# ADM-13 & ADM-14: Slots Oversight & Change Examiner
# ---------------------------------------------------------------------
@admin_bp.route("/slots", methods=["GET"])
@admin_required
def slots():
    """View all scheduled slots across all examinations (ADM-13)."""
    exam_id = request.args.get("examination_id", type=int)
    query = ExaminationSlot.query.join(Examination)

    if exam_id:
        query = query.filter(ExaminationSlot.examination_id == exam_id)

    slots_list = query.order_by(ExaminationSlot.start_at.desc()).all()
    exams_list = Examination.query.filter_by(is_deleted=False).all()
    return render_template("admin/slots.html", slots=slots_list, exams=exams_list)


@admin_bp.route("/slots/<int:slot_id>/examiner", methods=["GET", "POST"])
@admin_required
def change_slot_examiner(slot_id: int):
    """Change the assigned examiner for a specific examination slot (ADM-14)."""
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        abort(404)

    form = ChangeSlotExaminerForm()
    # Query approved examiners assigned to this examination
    assigned_examiners = (
        User.query.join(ExaminationExaminer, User.id == ExaminationExaminer.examiner_id)
        .filter(
            ExaminationExaminer.examination_id == slot.examination_id,
            User.is_active.is_(True),
            User.id != slot.examiner_id,
        )
        .all()
    )
    form.new_examiner_id.choices = [(e.id, e.full_name) for e in assigned_examiners]

    if form.validate_on_submit():
        old_examiner_id = slot.examiner_id
        slot.examiner_id = form.new_examiner_id.data
        db.session.commit()
        log_audit(
            "slot.change_examiner",
            "examination_slot",
            slot.id,
            {"old_examiner_id": old_examiner_id, "new_examiner_id": slot.examiner_id},
        )
        flash("Slot examiner updated successfully.", "success")
        return redirect(url_for("admin.slots"))

    return render_template("admin/slot_change_examiner.html", slot=slot, form=form)


# ---------------------------------------------------------------------
# ADM-15 & ADM-16: Bookings Oversight & Reschedule
# ---------------------------------------------------------------------
@admin_bp.route("/bookings", methods=["GET"])
@admin_required
def bookings():
    """List all student bookings with status filters (ADM-15)."""
    status_filter = request.args.get("status")
    query = Booking.query.join(ExaminationSlot)

    if status_filter:
        query = query.filter(Booking.status == status_filter)

    bookings_list = query.order_by(Booking.id.desc()).all()
    return render_template("admin/bookings.html", bookings=bookings_list)


@admin_bp.route("/bookings/<int:booking_id>/reschedule", methods=["GET", "POST"])
@admin_required
def reschedule_booking(booking_id: int):
    """Reschedule a student's booking to another slot of the same exam (ADM-16)."""
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.status != "booked":
        flash("Only active bookings can be rescheduled.", "warning")
        return redirect(url_for("admin.bookings"))

    form = RescheduleBookingForm()
    # Find available alternative slots for the exact same examination
    available_slots = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == booking.examination_id,
        ExaminationSlot.id != booking.slot_id,
        ExaminationSlot.booked_count < ExaminationSlot.max_capacity,
        ExaminationSlot.status == "available",
    ).all()

    form.new_slot_id.choices = [
        (
            s.id,
            f"{s.start_at.strftime('%d %b %Y, %H:%M')} (Seats: {s.booked_count}/{s.max_capacity})",
        )
        for s in available_slots
    ]

    if form.validate_on_submit():
        target_slot = db.session.get(ExaminationSlot, form.new_slot_id.data)
        if not target_slot or target_slot.booked_count >= target_slot.max_capacity:
            flash("The selected slot is full or unavailable.", "danger")
            return redirect(url_for("admin.reschedule_booking", booking_id=booking.id))

        old_slot = booking.slot

        # Atomic transaction: adjust counts on both slots
        old_slot.booked_count -= 1
        if old_slot.status == "full":
            old_slot.status = "available"

        target_slot.booked_count += 1
        if target_slot.booked_count >= target_slot.max_capacity:
            target_slot.status = "full"

        booking.rescheduled_from_slot_id = old_slot.id
        booking.slot_id = target_slot.id
        db.session.commit()

        log_audit(
            "booking.reschedule",
            "booking",
            booking.id,
            {"old_slot_id": old_slot.id, "new_slot_id": target_slot.id},
        )
        flash("Booking rescheduled successfully.", "success")
        return redirect(url_for("admin.bookings"))

    return render_template("admin/booking_reschedule.html", booking=booking, form=form)


@admin_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@admin_required
def cancel_booking(booking_id: int):
    """Admin-initiated cancellation of a student's booking."""
    booking = db.session.get(Booking, booking_id)
    if not booking or booking.status != "booked":
        abort(404)

    admin = get_current_user()
    slot = booking.slot

    booking.status = "cancelled"
    booking.cancelled_at = now_utc()
    booking.cancelled_by = admin.id

    slot.booked_count = max(0, slot.booked_count - 1)
    if slot.status == "full":
        slot.status = "available"

    db.session.commit()
    log_audit("booking.admin_cancel", "booking", booking.id, {"slot_id": slot.id})
    flash("Booking cancelled by administrator.", "info")
    return redirect(url_for("admin.bookings"))


# ---------------------------------------------------------------------
# ADM-17: Global Multi-Entity Search
# ---------------------------------------------------------------------
@admin_bp.route("/search", methods=["GET"])
@admin_required
def search():
    """Global multi-entity search endpoint (ADM-17)."""
    q = request.args.get("q", "").strip()
    results = search_all_entities(q) if q else {}
    return render_template("admin/search.html", query=q, results=results)


# ---------------------------------------------------------------------
# ADM-18: Historical Audit Trail
# ---------------------------------------------------------------------
@admin_bp.route("/history", methods=["GET"])
@admin_required
def history():
    """Browse complete historical audit logs (ADM-18)."""
    entity_filter = request.args.get("entity_type")
    query = AuditLog.query

    if entity_filter:
        query = query.filter_by(entity_type=entity_filter)

    logs_list = query.order_by(AuditLog.id.desc()).limit(100).all()
    return render_template("admin/history.html", logs=logs_list)
