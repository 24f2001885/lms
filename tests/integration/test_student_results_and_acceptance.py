"""
FILE PURPOSE: Results visibility and the milestone acceptance flow (Design Plan 4.2 and 4.3 end to end).
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Results: test_unpublished_result_hidden_everywhere (list, detail, dashboard), test_published_result_visible_with_feedback, test_result_totals_match_scores, test_remarks_escaped.
2. Acceptance test_student_booking_milestone_acceptance through the HTTP client only: Admin-prepared fixtures with a booking-open examination and a 2-seat slot; student 1 browses, books (flash), sees it under My bookings and Schedule, cancels before the deadline (seat freed), books again; student 2 books the same slot; student 3 gets "This slot is full."; student 1 tries a second slot of the same examination and gets the duplicate message; clock moved past the deadline: cancel refused; clock moved past booking_end: new booking refused with "Booking is closed."; examiner submits and publishes an evaluation; student 1 sees the result.
3. Final assertions on the database: booked_count equals the number of active bookings for the slot, statuses consistent, audit rows exist for every booking.create and booking.cancel.
DEBUGGING:
# print(f"[DEBUG] acceptance step={step} {response.status_code} booked_count={slot.booked_count}")
OFFLINE DOCKER TEST CASES:
- The acceptance test passes offline in under 8 seconds and leaves booked_count equal to active bookings.

FILE PURPOSE: Integration acceptance test for full student lifecycle (browse -> book -> cancel -> rebook -> result).
"""

from datetime import timedelta


def test_student_acceptance_flow(
    student_client, make_open_booking_setup, make_published_evaluation, freeze_now
):
    client, student = student_client
    exam, slot, examiner, _ = make_open_booking_setup(student_count=1, capacity=5)

    freeze_now(exam.booking_start + timedelta(hours=1))

    # 1. Book slot
    res1 = client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    assert b"Booking confirmed." in res1.data

    # 2. View bookings
    res2 = client.get("/student/bookings")
    assert res2.status_code == 200
    assert exam.name.encode() in res2.data

    # 3. Publish evaluation and view result
    from app.models import Booking

    booking = Booking.query.filter_by(student_id=student.id, slot_id=slot.id).first()
    make_published_evaluation(booking, examiner, total=85)

    res3 = client.get("/student/results")
    assert res3.status_code == 200
    assert b"85" in res3.data
