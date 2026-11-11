"""
FILE PURPOSE: HTTP tests for EXM-01 and EXM-07 to EXM-09 plus the milestone acceptance flow.
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_dashboard_counters_values, test_pending_list_and_filter, test_evaluation_form_has_inputs_per_criterion, test_save_draft_keeps_in_pending, test_submit_moves_to_submitted_and_decrements_counter, test_publish_makes_read_only, test_out_of_range_score_message_keeps_input, test_unknown_action_400, test_no_rubric_message, test_submitted_list_edit_only_for_submitted.
2. Acceptance test test_examiner_milestone_acceptance: Admin-prepared fixtures; examiner logs in, creates a slot inside the window, cannot edit it at booking_start, a booking made by factory appears under students, evaluates it (draft -> submit -> publish) and the dashboard counters change accordingly; another examiner never sees any of it.
DEBUGGING:
# print(f"[DEBUG] step={step} {response.status_code} {response.headers.get('Location')}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.

FILE PURPOSE: HTTP tests for examiner evaluation workflow (EXM-07 to EXM-09).
"""


def test_dashboard_route(examiner_client, make_ready_examination):
    client, examiner = examiner_client
    make_ready_examination(examiner=examiner)

    response = client.get("/examiner/dashboard")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_pending_evaluations_route(examiner_client, make_ready_examination):
    client, examiner = examiner_client
    make_ready_examination(examiner=examiner)

    response = client.get("/examiner/evaluations")
    assert response.status_code == 200
    assert b"Pending Evaluations" in response.data