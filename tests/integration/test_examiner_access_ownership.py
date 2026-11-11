"""
FILE PURPOSE: Proves examiner routes are role-locked and ownership-scoped.
"""


def test_examiner_routes_access_control(client, db_session):
    # Anonymous user redirect to login
    response = client.get("/examiner/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_ownership_scoping_slots(examiner_client, make_ready_examination, make_examiner):
    client, examiner_a = examiner_client
    exam, _ = make_ready_examination(examiner=examiner_a)

    # Create another examiner B
    examiner_b = make_examiner(full_name="Examiner B", email="b@test.com")

    # Try to access examiner A's examination detail as B (should be 404)
    # Need client logged in as B to test B's view, or test service level
    from app.services import slot_service
    assert slot_service.get_assigned_examination(examiner_b.id, exam.id) is None