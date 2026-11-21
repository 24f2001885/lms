"""
FILE PURPOSE: Booking actions and views: book (STU-04), cancel, my bookings (STU-05), booking detail (STU-06), schedule (STU-07), history (STU-08).
DEPENDS ON: student_bp, student_required, app/forms/common.py (ConfirmForm), app/services/booking_engine.py, app/services/student_queries.py, app/errors.py.
PROMPT FOR LLM IMPLEMENTATION:
1. POST /student/slots/<id>/book: validate ConfirmForm; load the slot (404 if it does not exist or its examination is not visible to students); call booking_engine.book_slot(g.user.id, slot_id). Success: flash "Booking confirmed." (category success) and redirect to /student/bookings. BookingError/WindowError: flash the error message (category danger) and redirect back to /student/examinations/<examination_id>. Never render on POST (post/redirect/get), so a refresh cannot double-submit.
2. POST /student/bookings/<id>/cancel: validate ConfirmForm; booking via student_queries.get_owned_booking (404 for other students' ids); call booking_engine.cancel_booking; flash "Booking cancelled. Your seat has been released." or the error message; redirect to /student/bookings.
3. GET /student/bookings (status filter, pagination), GET /student/bookings/<id> (own only; shows status, slot time, examiner, deadline note, Cancel button when allowed), GET /student/schedule, GET /student/history.
4. The Cancel button shows only for status booked; it is enabled until the examination's cancellation deadline and otherwise replaced by the text "Cancellation closed on <local date>".
5. Double-submit protection is server-side only: a second identical POST must end in the duplicate_booking flash.
DEBUGGING:
# print(f"[DEBUG] student booking action {request.path} user={g.user.id} result={result}")
OFFLINE DOCKER TEST CASES:
- Book then cancel through the client: booking_count and slot status change as expected.
- Posting book twice quickly shows "You already have a booking for this examination." the second time and keeps one row.
- Cancel of another student's booking returns 404 and changes nothing.
- A forged book POST to a cancelled slot flashes the unavailable message.
- GET on the book or cancel URLs returns 405.

FILE PURPOSE: Booking actions (book, cancel) and list views (my bookings, detail, schedule, history).
"""

from flask import abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.student import student_bp
from app.errors import BookingError, WindowError
from app.forms.common import ConfirmForm
from app.models import ExaminationSlot
from app.security.decorators import student_required
from app.services import booking_engine, student_queries


@student_bp.route("/slots/<int:slot_id>/book", methods=["POST"])
@student_required
def book_slot_action(slot_id):
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("Invalid request token.", "danger")
        return redirect(url_for("student.examinations_list"))

    slot = ExaminationSlot.query.get(slot_id)
    if not slot or not student_queries.is_examination_visible(slot.examination):
        abort(404)

    try:
        booking_engine.book_slot(g.user.id, slot_id)
        flash("Booking confirmed.", "success")
        return redirect(url_for("student.my_bookings_list"))
    except (BookingError, WindowError) as e:
        flash(str(e), "danger")
        return redirect(url_for("student.examination_detail", exam_id=slot.examination_id))


@student_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@student_required
def cancel_booking_action(booking_id):
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("Invalid request token.", "danger")
        return redirect(url_for("student.my_bookings_list"))

    booking = student_queries.get_owned_booking(g.user.id, booking_id)
    if not booking:
        abort(404)

    try:
        booking_engine.cancel_booking(g.user.id, booking_id)
        flash("Booking cancelled. Your seat has been released.", "success")
    except (BookingError, WindowError) as e:
        flash(str(e), "danger")

    return redirect(url_for("student.my_bookings_list"))


@student_bp.route("/bookings")
@student_required
def my_bookings_list():
    status = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    pagination = student_queries.my_bookings(g.user.id, status=status or None, page=page)
    confirm_form = ConfirmForm()

    return render_template(
        "student/bookings.html",
        pagination=pagination,
        page=pagination,
        selected_status=status,
        confirm_form=confirm_form,
    )


@student_bp.route("/bookings/<int:booking_id>")
@student_required
def booking_detail(booking_id):
    booking = student_queries.get_owned_booking(g.user.id, booking_id)
    if not booking:
        abort(404)

    result_pub = student_queries.result_detail(g.user.id, booking_id)
    confirm_form = ConfirmForm()

    return render_template(
        "student/booking_detail.html",
        booking=booking,
        result_pub=result_pub,
        confirm_form=confirm_form,
    )


@student_bp.route("/schedule")
@student_required
def schedule_view():
    bookings = student_queries.schedule(g.user.id)
    return render_template("student/schedule.html", bookings=bookings)


@student_bp.route("/history")
@student_required
def history_view():
    page = request.args.get("page", 1, type=int)
    data = student_queries.history(g.user.id, page=page)
    return render_template("student/history.html", data=data, page=data["bookings_page"])
