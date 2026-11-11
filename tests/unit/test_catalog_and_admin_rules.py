"""
FILE PURPOSE: Service-level tests for catalog_service and admin_service rules (no HTTP).
DEPENDS ON: app/services/catalog_service.py, admin_service.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Catalog tests: test_course_code_uppercased_and_unique, test_delete_course_blocked_when_in_use, test_exam_window_validation_messages, test_exam_cancellation_deadline_defaults, test_max_marks_cannot_drop_below_existing_evaluation, test_course_locked_after_slots, test_delete_exam_soft_and_switches_off, test_delete_exam_blocked_with_active_booking, test_toggle_slot_creation_needs_approved_examiner, test_toggle_booking_needs_rubric_total_100, test_closing_switches_has_no_preconditions, test_rubric_over_100_rejected, test_rubric_duplicate_name_rejected, test_rubric_locked_after_evaluation, test_assign_only_approved_active_examiners, test_assign_duplicate_rejected, test_unassign_blocked_with_slot.
2. Admin tests: test_approve_reject_deactivate_activate_cycle, test_cannot_deactivate_self, test_not_an_examiner_error, test_create_examiner_forces_password_change, test_temp_password_generated_and_hash_verifies, test_temp_password_not_in_audit_details, test_temp_password_refused_for_admin_target, test_change_slot_examiner_rules (not assigned, overlap, cancelled slot, same examiner, success), test_dashboard_totals_counts.
3. Every error test asserts the stable error code, not the message text.
DEBUGGING:
# print(f"[DEBUG] AppError code={exc_info.value.code}")
OFFLINE DOCKER TEST CASES:
- 26 tests pass offline.
"""
