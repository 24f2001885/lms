"""
FILE PURPOSE: Unit tests for audit_service, search_service and slot_rules.
DEPENDS ON: app/services/audit_service.py, search_service.py, slot_rules.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. audit: test_log_action_not_committed_until_caller_commits, test_details_json_roundtrip_with_datetime, test_ip_stored_in_request_context_none_outside, test_history_for_newest_first.
2. search: test_student_search_case_insensitive, test_search_by_numeric_id_first, test_like_wildcards_escaped, test_invalid_kind_raises, test_empty_query_returns_hint, test_booking_search_by_student_email, test_examination_search_includes_deleted_flagged, test_search_never_returns_other_roles_in_student_kind.
3. slot_rules: test_overlap_detected, test_back_to_back_allowed, test_cancelled_slot_ignored, test_exclude_slot_id, test_overlap_across_examinations_same_examiner, test_different_examiners_never_overlap.
DEBUGGING:
# print(f"[DEBUG] result ids={[r.id for r in result.items]}")
OFFLINE DOCKER TEST CASES:
- 18 tests pass offline.
"""
