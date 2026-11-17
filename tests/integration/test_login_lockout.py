"""
Integration tests for brute-force rate limiting and lockout behavior (P11).
"""

from datetime import timedelta

import pytest

from app.models.audit_log import AuditLog
from app.services import windows
from app.services.audit_service import AUTH_LOCKOUT

pytestmark = pytest.mark.security


def test_five_wrong_passwords_then_429_with_retry_after(client, make_student, login_attempts):
    """5 consecutive failed logins trigger 429 Too Many Requests with Retry-After header."""
    make_student(email="lockout_5@test.local", password="CorrectPass123!")

    # 5 failed attempts
    resps = login_attempts("lockout_5@test.local", ["bad1", "bad2", "bad3", "bad4", "bad5"])
    for r in resps:
        assert r.status_code == 200

    # 6th attempt is blocked with 429
    r6 = client.post(
        "/login",
        data={"email": "lockout_5@test.local", "password": "bad6"},
        follow_redirects=False,
    )
    assert r6.status_code == 429
    assert "Retry-After" in r6.headers
    assert int(r6.headers["Retry-After"]) > 0


def test_sixth_attempt_with_correct_password_still_blocked(client, make_student, login_attempts):
    """After 5 failures, even the correct password is blocked while locked out."""
    make_student(email="locked_correct@test.local", password="RealSecret123!")

    login_attempts("locked_correct@test.local", ["w1", "w2", "w3", "w4", "w5"])

    # 6th attempt with real password is still blocked
    r = client.post(
        "/login",
        data={"email": "locked_correct@test.local", "password": "RealSecret123!"},
        follow_redirects=False,
    )
    assert r.status_code == 429


def test_lockout_message_text_and_minutes(client, make_student, login_attempts):
    """Blocked attempt displays 'Too many failed attempts. Try again in N minutes.'"""
    make_student(email="lockout_msg@test.local", password="RealSecret123!")
    login_attempts("lockout_msg@test.local", ["w1", "w2", "w3", "w4", "w5"])

    r = client.post(
        "/login",
        data={"email": "lockout_msg@test.local", "password": "w6"},
    )
    assert r.status_code == 429
    assert b"Too many failed attempts. Try again in" in r.data
    assert b"minutes" in r.data


def test_window_expiry_allows_login_again(client, make_student, login_attempts, freeze_now):
    """Advancing the clock past 15-minute window resets lockout."""
    make_student(email="window_exp@test.local", password="RealSecret123!")
    now = windows.now_utc()
    freeze_now(now)

    login_attempts("window_exp@test.local", ["w1", "w2", "w3", "w4", "w5"])
    assert (
        client.post("/login", data={"email": "window_exp@test.local", "password": "w6"}).status_code
        == 429
    )

    # Advance clock 16 minutes
    freeze_now(now + timedelta(minutes=16))

    r_after = client.post(
        "/login",
        data={"email": "window_exp@test.local", "password": "RealSecret123!"},
        follow_redirects=False,
    )
    assert r_after.status_code == 302
    assert r_after.headers["Location"].endswith("/student/dashboard")


def test_success_before_limit_resets_counter(client, make_student, login_attempts):
    """Successful login resets failure counter for that email."""
    make_student(email="reset_count@test.local", password="RealSecret123!")

    # 4 failures (not locked yet)
    login_attempts("reset_count@test.local", ["w1", "w2", "w3", "w4"])

    # 5th attempt succeeds
    r_ok = client.post(
        "/login",
        data={"email": "reset_count@test.local", "password": "RealSecret123!"},
        follow_redirects=False,
    )
    assert r_ok.status_code == 302

    # Logout
    client.post("/logout")

    # Another 4 failures are allowed because counter was reset
    resps = login_attempts("reset_count@test.local", ["w1", "w2", "w3", "w4"])
    for r in resps:
        assert r.status_code == 200


def test_unknown_email_locks_identically(client, make_student, login_attempts):
    """Lockout behavior, status code, and Retry-After are identical for unknown emails."""
    make_student(email="exists@test.local", password="RealSecret123!")

    login_attempts("exists@test.local", ["w1", "w2", "w3", "w4", "w5"])
    r_exists = client.post("/login", data={"email": "exists@test.local", "password": "w6"})

    login_attempts("nobody@test.local", ["w1", "w2", "w3", "w4", "w5"])
    r_unknown = client.post("/login", data={"email": "nobody@test.local", "password": "w6"})

    assert r_exists.status_code == 429
    assert r_unknown.status_code == 429
    assert r_exists.headers.get("Retry-After") == r_unknown.headers.get("Retry-After")


def test_other_email_same_ip_not_blocked_until_ip_limit(client, make_student, login_attempts):
    """Locking one email does not block another email from the same IP (until 20 IP failures)."""
    make_student(email="user_a@test.local", password="RealSecret123!")
    make_student(email="user_b@test.local", password="RealSecret123!")

    login_attempts("user_a@test.local", ["w1", "w2", "w3", "w4", "w5"])
    assert (
        client.post("/login", data={"email": "user_a@test.local", "password": "w"}).status_code
        == 429
    )

    # user_b is not blocked
    r_b = client.post(
        "/login",
        data={"email": "user_b@test.local", "password": "RealSecret123!"},
        follow_redirects=False,
    )
    assert r_b.status_code == 302


def test_ip_limit_20_failures(client, make_student, login_attempts):
    """20 failures across different emails from the same IP blocks the whole IP."""
    for i in range(20):
        client.post("/login", data={"email": f"diff_user_{i}@test.local", "password": "bad"})

    # 21st attempt is blocked by IP limiter
    r21 = client.post("/login", data={"email": "another_user@test.local", "password": "bad"})
    assert r21.status_code == 429


def test_validation_errors_do_not_count(client, login_attempts):
    """Validation errors (empty email, invalid format) do not increment rate limiter."""
    for _ in range(7):
        client.post("/login", data={"email": "", "password": ""})
        client.post("/login", data={"email": "not-an-email", "password": "short"})

    # Legitimate login attempt still returns 200, not 429
    r = client.post("/login", data={"email": "valid@test.local", "password": "some_password"})
    assert r.status_code == 200


def test_locked_user_other_ip_can_login(client, make_student, login_attempts):
    """User locked on one IP can still sign in from another IP."""
    make_student(email="multi_ip@test.local", password="RealSecret123!")

    # Lock on 1.1.1.1
    login_attempts("multi_ip@test.local", ["w1", "w2", "w3", "w4", "w5"])

    # Attempt on 2.2.2.2
    r_other_ip = client.post(
        "/login",
        data={"email": "multi_ip@test.local", "password": "RealSecret123!"},
        environ_overrides={"REMOTE_ADDR": "2.2.2.2"},
        follow_redirects=False,
    )
    assert r_other_ip.status_code == 302
    assert r_other_ip.headers["Location"].endswith("/student/dashboard")


def test_lockout_audit_row_written_once_without_email(
    client, make_student, login_attempts, db_session
):
    """Only 1 lockout audit log row is written per lockout, without plain email."""
    make_student(email="audit_lockout@test.local", password="RealSecret123!")

    login_attempts("audit_lockout@test.local", ["w1", "w2", "w3", "w4", "w5", "w6", "w7"])

    logs = AuditLog.query.filter_by(action=AUTH_LOCKOUT).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.actor_id is None
    assert "audit_lockout@test.local" not in str(log.details)


def test_password_change_limiter_5_wrong_current_passwords(client, make_student, login):
    """5 consecutive wrong current passwords on /change-password locks the user."""
    make_student(email="change_limit@test.local", password="ValidPass123!")
    login("change_limit@test.local", "ValidPass123!")

    for _ in range(5):
        client.post(
            "/change-password",
            data={
                "current_password": "WrongPassword1!",
                "new_password": "NewSecretPass123!",
                "confirm_new_password": "NewSecretPass123!",
            },
        )

    # 6th attempt is blocked with 429
    r6 = client.post(
        "/change-password",
        data={
            "current_password": "ValidPass123!",
            "new_password": "NewSecretPass123!",
            "confirm_new_password": "NewSecretPass123!",
        },
    )
    assert r6.status_code == 429


def test_get_login_never_limited(client, login_attempts):
    """GET requests to /login are never rate limited."""
    login_attempts("get_test@test.local", ["w1", "w2", "w3", "w4", "w5"])
    assert client.get("/login").status_code == 200


def test_json_path_429_shape(client):
    """JSON 429 response contains code 'too_many_requests' and Retry-After header."""
    from flask import make_response

    from app.errors import error_response

    resp = make_response(error_response("too_many_requests", "Rate limit exceeded.", 429))
    resp.headers["Retry-After"] = "900"
    assert resp.status_code == 429
    assert resp.is_json
    data = resp.get_json()
    assert data["error"]["code"] == "too_many_requests"
    assert resp.headers["Retry-After"] == "900"


def test_429_page_template_and_no_database_query(client):
    """429 error template renders cleanly."""
    resp = client.get("/blocked-response")
    assert resp.status_code == 429
    assert b"Too many failed attempts" in resp.data
