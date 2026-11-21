"""
FILE PURPOSE: EXM-04, EXM-05, EXM-06 slot list, create, edit, delete and booked students.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.examiner import examiner_bp
from app.errors import AppError, BookingError, WindowError
from app.forms.booking_actions import ReasonForm
from app.forms.slot import SlotForm
from app.security.decorators import approved_examiner_required
from app.services import booking_engine, slot_service


@examiner_bp.route("/slots")
@approved_examiner_required
def slots_list():
    examiner_id = g.user.id
    examination_id = request.args.get("examination_id", type=int)
    status = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = slot_service.list_slots(
        examiner_id, examination_id=examination_id, status=status or None, page=page
    )
    assigned_exams = slot_service.list_assigned_examinations(examiner_id)

    return render_template(
        "examiner/slots_list.html",
        pagination=pagination,
        assigned_exams=assigned_exams,
        selected_exam=examination_id,
        selected_status=status,
    )


@examiner_bp.route("/slots/new", methods=["GET", "POST"])
@approved_examiner_required
def slot_create():
    examiner_id = g.user.id
    assigned_exams = slot_service.list_assigned_examinations(examiner_id)

    form = SlotForm()
    form.examination_id.choices = [(e.id, f"{e.course.code} - {e.name}") for e in assigned_exams]

    if request.method == "POST" and form.validate_on_submit():
        try:
            exam_id, start_utc, end_utc, capacity = form.to_service_data()
            slot_service.create_slot(examiner_id, exam_id, start_utc, end_utc, capacity)
            flash("Slot created successfully.", "success")
            return redirect(url_for("examiner.slots_list"))
        except (AppError, WindowError) as e:
            flash(str(e), "danger")

    return render_template("examiner/slot_form.html", form=form, action="create")


@examiner_bp.route("/slots/<int:slot_id>/edit", methods=["GET", "POST"])
@approved_examiner_required
def slot_edit(slot_id):
    examiner_id = g.user.id
    slot = slot_service.get_owned_slot(examiner_id, slot_id)
    if not slot:
        abort(404)

    assigned_exams = slot_service.list_assigned_examinations(examiner_id)
    form = SlotForm()
    form.examination_id.choices = [(e.id, f"{e.course.code} - {e.name}") for e in assigned_exams]

    if request.method == "GET":
        form.populate_from(slot)

    if request.method == "POST" and form.validate_on_submit():
        try:
            _, start_utc, end_utc, capacity = form.to_service_data()
            slot_service.update_slot(examiner_id, slot_id, start_utc, end_utc, capacity)
            flash("Slot updated successfully.", "success")
            return redirect(url_for("examiner.slots_list"))
        except (AppError, WindowError) as e:
            flash(str(e), "danger")

    return render_template("examiner/slot_form.html", form=form, action="edit", slot=slot)


@examiner_bp.route("/slots/<int:slot_id>/update", methods=["POST"])
@approved_examiner_required
def slot_update(slot_id):
    examiner_id = g.user.id
    slot = slot_service.get_owned_slot(examiner_id, slot_id)
    if not slot:
        abort(404)

    form = SlotForm()
    assigned_exams = slot_service.list_assigned_examinations(examiner_id)
    form.examination_id.choices = [(e.id, f"{e.course.code} - {e.name}") for e in assigned_exams]

    if form.validate_on_submit():
        try:
            _, start_utc, end_utc, capacity = form.to_service_data()
            slot_service.update_slot(examiner_id, slot_id, start_utc, end_utc, capacity)
            flash("Slot updated successfully.", "success")
            return redirect(url_for("examiner.slots_list"))
        except (AppError, WindowError) as e:
            flash(str(e), "danger")

    return render_template("examiner/slot_form.html", form=form, action="edit", slot=slot)


@examiner_bp.route("/slots/<int:slot_id>/delete", methods=["POST"])
@approved_examiner_required
def slot_delete(slot_id):
    examiner_id = g.user.id
    try:
        slot_service.delete_slot(examiner_id, slot_id)
        flash("Slot removed.", "success")
    except (AppError, WindowError) as e:
        flash(str(e), "danger")
    return redirect(url_for("examiner.slots_list"))


@examiner_bp.route("/slots/<int:slot_id>/students")
@approved_examiner_required
def slot_students(slot_id):
    examiner_id = g.user.id
    slot = slot_service.get_owned_slot(examiner_id, slot_id)
    if not slot:
        abort(404)

    bookings = slot_service.booked_students(examiner_id, slot_id)
    from app.models import Booking

    cancelled_count = Booking.query.filter_by(slot_id=slot_id, status="cancelled").count()

    return render_template(
        "examiner/slot_students.html", slot=slot, bookings=bookings, cancelled_count=cancelled_count
    )


@examiner_bp.route("/slots/<int:slot_id>/cancel", methods=["POST"])
@approved_examiner_required
def cancel_slot_action(slot_id: int):
    slot = slot_service.get_owned_slot(g.user.id, slot_id)
    if not slot:
        abort(404)

    form = ReasonForm()
    if not form.validate_on_submit():
        flash("Please provide a valid cancellation reason (3-200 characters).", "danger")
        return redirect(url_for("examiner.slots_list"))

    try:
        cancelled_count = booking_engine.cancel_slot(slot.id, g.user.id, form.reason.data)
        flash(f"Slot cancelled. {cancelled_count} bookings were cancelled.", "success")
    except BookingError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("examiner.slots_list"))
