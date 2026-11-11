"""
FILE PURPOSE: Boundary tests for the time-window helper (risk R-3).
DEPENDS ON: app/services/windows.py, tests/conftest.py (freeze_now, make_examination).
PROMPT FOR LLM IMPLEMENTATION:
1. Parametrised boundary tests for is_booking_open and is_slot_creation_open: one second before start, exactly at start, mid window, exactly at end, one second after end, each with the switch on and off (switch off is always closed).
2. Tests: test_can_student_cancel_until_deadline_inclusive, test_slots_editable_only_before_booking_start (exactly at booking_start is NOT editable), test_soft_deleted_exam_never_open, test_assert_helpers_raise_window_error_with_codes (booking_closed, slot_creation_closed, slot_edit_locked, cancel_deadline_passed), test_window_state_reasons (switch off / not started / ended texts), test_from_local_input_kolkata_to_utc, test_to_input_value_roundtrip, test_bad_local_input_raises_value_error, test_now_utc_is_naive, test_no_module_imports_now_utc_by_name (walk app/ source files and assert none contains "import now_utc").
3. Use freeze_now for all clock-dependent cases; never call datetime.now().
DEBUGGING:
# print(f"[DEBUG] boundary case now={now} expected={expected} got={got}")
OFFLINE DOCKER TEST CASES:
- 30+ parametrised cases pass offline; making the end boundary exclusive makes at least one case fail.
"""
