"""
FILE PURPOSE: ADM-16 reschedule booking, admin cancel with reason, and admin publish evaluation.
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.admin import admin_bp
from app.errors import BookingError
from app.extensions import db
from app.forms.booking_actions import ReasonForm, RescheduleForm
from app.forms.common import ConfirmForm
from app.models import Booking, Evaluation, ExaminationSlot
from app.security.decorators import admin_required
from app.services import booking_engine, evaluation_service, windows


def _eligible_target_slots(booking: Booking) -> list[ExaminationSlot]:
    now = windows.now_utc()
    return (
        ExaminationSlot.query.filter(
            ExaminationSlot.examination_id == booking.examination_id,
            ExaminationSlot.id != booking.slot_id,
            ExaminationSlot.status == "available",
            ExaminationSlot.start_at > now,
        )
        .order_by(ExaminationSlot.start_at.asc())
        .all()
    )


@admin_bp.route("/bookings/<int:booking_id>/reschedule", methods=["GET", "POST"])
@admin_required
def reschedule_booking(booking_id: int):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        abort(404)

    slots = _eligible_target_slots(booking)
    form = RescheduleForm()
    form.new_slot_id.choices = [
        (
            s.id,
            f"{s.start_at.strftime('%Y-%m-%d %H:%M')} - {s.examiner.full_name} - {s.max_capacity - s.booked_count} seats left",
        )
        for s in slots
    ]

    if request.method == "POST" and form.validate_on_submit():
        try:
            booking_engine.reschedule_booking(booking.id, form.new_slot_id.data, g.user.id)
            flash("Booking moved.", "success")
            return redirect(url_for("admin.booking_detail", booking_id=booking.id))
        except BookingError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.booking_detail", booking_id=booking.id))

    return render_template("admin/reschedule.html", booking=booking, form=form)


@admin_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_booking(booking_id: int):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        abort(404)

    form = ReasonForm()
    if not form.validate_on_submit():
        flash("Please provide a valid cancellation reason (3-200 characters).", "danger")
        return redirect(url_for("admin.booking_detail", booking_id=booking.id))

    try:
        booking_engine.admin_cancel_booking(booking.id, g.user.id, form.reason.data)
        flash("Booking cancelled.", "success")
    except BookingError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("admin.booking_detail", booking_id=booking.id))


@admin_bp.route("/evaluations/<int:evaluation_id>/publish", methods=["POST"])
@admin_required
def admin_publish_evaluation(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if not evaluation:
        abort(404)

    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("Invalid request token.", "danger")
        return redirect(url_for("admin.booking_detail", booking_id=evaluation.booking_id))

    try:
        evaluation_service.admin_publish(g.user.id, evaluation.id)
        flash("Evaluation published.", "success")
    except BookingError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("admin.booking_detail", booking_id=evaluation.booking_id))
