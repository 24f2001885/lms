"""
FILE PURPOSE: HTTP-level tests for ADM-01 to ADM-08 CRUD screens.
DEPENDS ON: tests/conftest.py (admin_client, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. Dashboard: test_dashboard_six_totals_values, test_dashboard_pending_link.
2. Courses: test_course_create_edit_delete_flow, test_course_duplicate_code_message, test_course_delete_blocked_message, test_course_list_filters_and_paging (25 rows).
3. Examinations: test_exam_create_converts_local_time_to_utc, test_exam_create_invalid_window_shows_errors, test_exam_edit_prefills_local_times, test_exam_delete_soft_hides_from_list, test_exam_show_deleted_flag, test_exam_detail_shows_window_reasons, test_toggle_slot_creation_flow, test_toggle_booking_blocked_without_rubric_100_flash, test_assign_and_remove_examiner_flow.
4. Rubrics: test_rubric_add_progress_text, test_rubric_over_100_flash, test_rubric_locked_hides_forms, test_rubric_foreign_id_404.
5. Every test uses admin_client and asserts both the flash text and the database state.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 22 tests pass offline.
"""
