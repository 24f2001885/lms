"""
FILE PURPOSE: Access control matrix across every /api/v1 rule and user role (TDR 6).
"""

import pytest


@pytest.mark.api
def test_api_routes_reject_anonymous_with_401_json(api):
    anon = api(None)
    for path in [
        "/api/v1/session",
        "/api/v1/examinations",
        "/api/v1/slots",
        "/api/v1/bookings",
        "/api/v1/examiners",
        "/api/v1/students",
        "/api/v1/stats/summary",
    ]:
        res = anon.get(path)
        assert res.status_code == 401
        assert res.mimetype == "application/json"
        assert res.get_json()["error"]["code"] == "unauthenticated"


@pytest.mark.api
def test_role_guard_precedence_and_rbac(api):
    pending = api("pending_examiner")
    inactive = api("inactive_student")
    must_change = api("admin_must_change_password")
    student = api("student")
    examiner = api("examiner")
    admin = api("admin")

    # Pending examiner on examiner/shared endpoint -> 403 not_approved
    r1 = pending.get("/api/v1/examinations")
    assert r1.status_code == 403
    assert r1.get_json()["error"]["code"] == "not_approved"

    # Pending examiner on admin-only endpoint -> 403 forbidden (role check before approval, TDR 6)
    r2 = pending.get("/api/v1/examiners")
    assert r2.status_code == 403
    assert r2.get_json()["error"]["code"] == "forbidden"

    # Inactive user -> 403 account_inactive
    r3 = inactive.get("/api/v1/examinations")
    assert r3.status_code == 403
    assert r3.get_json()["error"]["code"] == "account_inactive"

    # Admin with must_change_password -> 403 password_change_required
    r4 = must_change.get("/api/v1/stats/summary")
    assert r4.status_code == 403
    assert r4.get_json()["error"]["code"] == "password_change_required"

    # Student / Examiner on admin endpoints -> 403 forbidden
    assert student.get("/api/v1/stats/summary").status_code == 403
    assert examiner.get("/api/v1/students").status_code == 403
    assert student.post("/api/v1/examinations", data={}).status_code == 403
    assert admin.post("/api/v1/bookings", data={"slot_id": 1}).status_code == 403
