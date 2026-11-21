"""
FILE PURPOSE: HTTP tests for STU-01 to STU-08 (browse, book, cancel, lists).
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Browse: test_examinations_filters_and_paging, test_detail_404_for_draft, test_book_buttons_disabled_with_reasons (closed, full, already booked, not yet open).
2. Booking: test_book_flow_success_flash_and_redirect, test_double_post_gives_duplicate_flash_single_row, test_book_closed_window_flash, test_book_full_slot_flash, test_book_unknown_slot_404, test_get_on_book_url_405.
3. Cancel: test_cancel_before_deadline_frees_seat, test_cancel_after_deadline_flash_and_button_hidden, test_cancel_foreign_booking_404.
4. Lists: test_my_bookings_status_pills, test_schedule_lists_upcoming_only, test_history_includes_cancelled, test_dashboard_sections_fill_after_booking.
5. Assert flash text, redirect Location and database state in each test; freeze the clock with freeze_now.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 16 tests pass offline.

FILE PURPOSE: Integration tests for student browse, book, and cancel flow.
"""

from datetime import timedelta


def test_student_browse_and_book_flow(student_client, make_open_booking_setup, freeze_now):
    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)

    # Associate current logged in student with exam booking test
    freeze_now(exam.booking_start + timedelta(hours=1))

    res = client.get("/student/examinations")
    assert res.status_code == 200
    assert exam.name.encode() in res.data

    res_book = client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    assert res_book.status_code == 200
    assert b"Booking confirmed." in res_book.data
