"""
FILE PURPOSE: HTTP-level tests for examiner/student management, slots overview, change slot examiner, bookings list.
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Examiners: test_pending_filter_and_approve, test_reject_then_login_shows_not_approved, test_deactivate_activate_effect_on_login, test_add_examiner_then_forced_password_change, test_temp_password_flash_once, test_approve_student_id_rejected.
2. Students: test_students_search_by_roll_number, test_student_detail_lists_all_booking_statuses, test_examiner_id_on_student_detail_404.
3. Slots: test_slots_filters, test_change_examiner_success_keeps_bookings, test_change_examiner_overlap_flash, test_change_examiner_forged_post_refused.
4. Bookings: test_bookings_filters_and_paging, test_bookings_list_query_count_bounded, test_booking_detail_no_action_buttons_in_p3, test_booking_detail_404.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')}")
OFFLINE DOCKER TEST CASES:
- 17 tests pass offline; the query-count test fails if eager loading is removed.
"""
