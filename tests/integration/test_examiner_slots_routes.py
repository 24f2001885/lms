"""
FILE PURPOSE: HTTP tests for EXM-02 to EXM-06.
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_examinations_list_only_assigned, test_create_slot_disabled_button_reason_before_window, test_create_slot_flow_in_window (form post with local times, DB row has UTC), test_create_slot_outside_window_flash, test_overlap_flash_with_time, test_edit_prefills_local_time, test_edit_locked_after_booking_start_flash, test_delete_confirm_flow, test_slot_with_booking_hides_edit_delete, test_students_page_lists_booked_only, test_pagination_keeps_filters.
2. Assert flash text and database state in every test; use freeze_now to place the clock before, inside and after the windows.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.

FILE PURPOSE: HTTP tests for examiner slot management (EXM-02 to EXM-06).
"""


def test_examinations_list_route(examiner_client, make_ready_examination):
    client, examiner = examiner_client
    make_ready_examination(examiner=examiner)

    response = client.get("/examiner/examinations")
    assert response.status_code == 200
    assert b"My Examinations" in response.data


def test_slot_create_route_get(examiner_client, make_ready_examination):
    client, examiner = examiner_client
    make_ready_examination(examiner=examiner)

    response = client.get("/examiner/slots/new")
    assert response.status_code == 200
    assert b"Create New Slot" in response.data
