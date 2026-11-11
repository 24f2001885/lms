"""
FILE PURPOSE: Tests for compute_status / refresh_status.
DEPENDS ON: app/services/exam_status.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_draft_before_any_window, test_slot_creation_when_open, test_booking_open_when_open, test_closed_after_booking_end_without_slots, test_completed_after_all_slots_past_and_evaluated, test_closed_when_one_booking_unevaluated, test_closed_when_a_slot_is_in_the_future, test_cancelled_slots_ignored, test_refresh_status_writes_one_audit_row_and_is_idempotent, test_deleted_exam_status_untouched, test_booking_open_wins_over_slot_creation_if_both_flags_on.
2. Build data with the conftest factories and freeze_now; no sleeping.
DEBUGGING:
# print(f"[DEBUG] status case {name}: expected={expected} got={got}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.
"""
