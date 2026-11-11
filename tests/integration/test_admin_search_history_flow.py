"""
FILE PURPOSE: Search, history tabs and the full Admin setup flow of Design Plan 4.4 (milestone acceptance).
DEPENDS ON: tests/conftest.py, freeze_now.
PROMPT FOR LLM IMPLEMENTATION:
1. Search/history: test_search_each_kind_renders, test_search_xss_escaped, test_search_invalid_kind_message, test_history_tabs_render_empty, test_history_shows_soft_deleted_exam, test_history_audit_tab_shows_course_create.
2. test_admin_setup_flow_end_to_end (acceptance): through the HTTP client only - create course; create examination with windows around the frozen now; add rubric criteria 60 and 40; register and approve an examiner through the UI routes; assign the examiner; open slot creation (status shows slot_creation); close it; open booking (status booking_open); close booking; assert each step's flash message, the final switches state and that the audit tab lists at least 8 rows in order.
3. test_setup_flow_blocked_steps: opening slot creation before assigning, opening booking before the rubric total is 100, each with the exact flash.
DEBUGGING:
# print(f"[DEBUG] flow step={step} status={response.status_code}")
OFFLINE DOCKER TEST CASES:
- The end-to-end test passes offline in under 5 seconds and leaves a consistent database (rubric total 100, switches closed).
"""
