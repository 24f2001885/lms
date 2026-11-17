"""
Tests for Flask-Login integration, session fixation, idle timeout, absolute lifetime,
session identity token invalidation (R-21), and session protection (P11).
"""

import inspect
from datetime import timedelta

import pytest
from flask import g

from app.security import auth_helpers
from app.services import windows

pytestmark = pytest.mark.security


def test_helper_names_and_signatures_unchanged():
    """Verify legacy auth helper functions retain expected signatures."""
    assert callable(auth_helpers.login_user_session)
    assert callable(auth_helpers.logout_user_session)
    assert callable(auth_helpers.load_current_user)
    assert callable(auth_helpers.verify_credentials)
    assert callable(auth_helpers.post_login_redirect_url)

    sig_login = inspect.signature(auth_helpers.login_user_session)
    assert "user" in sig_login.parameters

    sig_verify = inspect.signature(auth_helpers.verify_credentials)
    assert "email" in sig_verify.parameters
    assert "password" in sig_verify.parameters


def test_g_user_still_set_for_authenticated_and_none_for_anonymous(client, make_student, login):
    """Verify g.user is populated when authenticated and None when anonymous."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert g.get("user") is None

    student = make_student(email="g_user@test.local", password="Passw0rd123!")
    login("g_user@test.local", "Passw0rd123!")

    client.get("/student/dashboard")
    assert g.user is not None
    assert g.user.id == student.id


def test_context_processor_current_user_none_for_anonymous(client):
    """Verify context processor returns None for anonymous users."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Log out" not in resp.data


def test_unauthorized_html_redirects_with_same_flash(client):
    """Verify unauthenticated access to protected view redirects to login with flash."""
    resp = client.get("/student/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Please log in to continue." in resp.data


def test_unauthorized_api_returns_json_401(client):
    """Verify unauthenticated API request returns JSON 401 unauthenticated."""
    resp = client.get("/api/v1/examinations")
    assert resp.status_code == 401
    assert resp.is_json
    data = resp.get_json()
    assert data["error"]["code"] == "unauthenticated"


def test_inactive_user_can_reach_inactive_page(client, make_student):
    """Verify inactive user session can access /account-inactive."""
    make_student(email="inactive@test.local", password="Passw0rd123!", is_active=False)
    resp = client.post(
        "/login",
        data={"email": "inactive@test.local", "password": "Passw0rd123!"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account-inactive")

    page = client.get("/account-inactive")
    assert page.status_code == 200
    assert b"Account Inactive" in page.data


def test_no_remember_cookie_ever_set(client, make_student, login):
    """Verify no remember_token or remember me cookie is ever issued."""
    make_student(email="no_remember@test.local", password="Passw0rd123!")
    resp = login("no_remember@test.local", "Passw0rd123!")
    cookies = [header for k, header in resp.headers if k.lower() == "set-cookie"]
    cookie_str = " ".join(cookies)
    assert "remember_token" not in cookie_str


def test_session_fixation_pre_login_data_removed(client, make_student, login):
    """Verify pre-existing session keys are purged upon login."""
    with client.session_transaction() as sess:
        sess["fixation_probe"] = "stolen_data"

    make_student(email="fixation_test@test.local", password="Passw0rd123!")
    login("fixation_test@test.local", "Passw0rd123!")

    with client.session_transaction() as sess:
        assert "fixation_probe" not in sess
        assert "_user_id" in sess


def test_idle_timeout_30_minutes_rolling(client, make_student, login, freeze_now):
    """Verify 30-minute idle session timeout expires with inactivity."""
    make_student(email="timeout@test.local", password="Passw0rd123!")
    now = windows.now_utc()
    freeze_now(now)

    login("timeout@test.local", "Passw0rd123!")

    # Advance 15 minutes: active, session survives
    freeze_now(now + timedelta(minutes=15))
    resp = client.get("/student/dashboard")
    assert resp.status_code == 200

    # Advance another 35 minutes without request: session expires
    freeze_now(now + timedelta(minutes=50))
    resp_expired = client.get("/student/dashboard", follow_redirects=False)
    assert resp_expired.status_code == 302
    assert resp_expired.headers["Location"].endswith("/login")


def test_absolute_lifetime_ends_session_even_when_active(client, make_student, login, freeze_now):
    """Verify absolute session lifetime (8 hours = 480 minutes) terminates session even if active."""
    make_student(email="absolute@test.local", password="Passw0rd123!")
    now = windows.now_utc()
    freeze_now(now)

    login("absolute@test.local", "Passw0rd123!")

    # Maintain activity every 20 minutes up to 7 hours (420 mins)
    for mins in range(20, 440, 20):
        freeze_now(now + timedelta(minutes=mins))
        resp = client.get("/student/dashboard")
        assert resp.status_code == 200

    # Request at 8 hours and 5 minutes (485 mins): expired by absolute lifetime
    freeze_now(now + timedelta(minutes=485))
    resp_expired = client.get("/student/dashboard", follow_redirects=False)
    assert resp_expired.status_code == 302
    assert resp_expired.headers["Location"].endswith("/login")


def test_cookie_flags_httponly_samesite_and_secure_in_prod_config():
    """Verify ProdConfig sets Secure, HttpOnly, and __Host- cookie name."""
    from app.config import ProdConfig

    assert ProdConfig.SESSION_COOKIE_HTTPONLY is True
    assert ProdConfig.SESSION_COOKIE_SAMESITE == "Lax"
    assert ProdConfig.SESSION_COOKIE_SECURE is True
    assert ProdConfig.SESSION_COOKIE_NAME == "__Host-emp-session"


def test_prod_cookie_name_prefix():
    """Verify ProdConfig cookie name starts with __Host- prefix."""
    from app.config import ProdConfig

    assert ProdConfig.SESSION_COOKIE_NAME.startswith("__Host-")


def test_password_change_kills_other_sessions_but_keeps_current(app, make_student):
    """R-21: Password change invalidates session B while keeping session A alive."""
    make_student(email="r21_multi@test.local", password="OldPassword123!")

    client_a = app.test_client()
    client_b = app.test_client()

    client_a.post("/login", data={"email": "r21_multi@test.local", "password": "OldPassword123!"})
    client_b.post("/login", data={"email": "r21_multi@test.local", "password": "OldPassword123!"})

    assert client_a.get("/student/dashboard").status_code == 200
    assert client_b.get("/student/dashboard").status_code == 200

    # Change password in Client A
    resp_change = client_a.post(
        "/change-password",
        data={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword123!",
            "confirm_new_password": "NewPassword123!",
        },
        follow_redirects=False,
    )
    assert resp_change.status_code == 302

    # Client A remains authenticated
    assert client_a.get("/student/dashboard").status_code == 200

    # Client B is invalidated because its session fingerprint does not match the new password hash
    resp_b = client_b.get("/student/dashboard", follow_redirects=False)
    assert resp_b.status_code == 302
    assert resp_b.headers["Location"].endswith("/login")


def test_admin_temporary_password_kills_user_sessions(app, make_student, make_admin):
    """Admin setting temporary password invalidates user active sessions."""
    student = make_student(email="temp_pw_victim@test.local", password="UserSecret123!")
    make_admin(email="temp_admin@test.local", password="AdminSecret123!")

    client_user = app.test_client()
    client_admin = app.test_client()

    client_user.post(
        "/login", data={"email": "temp_pw_victim@test.local", "password": "UserSecret123!"}
    )
    assert client_user.get("/student/dashboard").status_code == 200

    client_admin.post(
        "/login", data={"email": "temp_admin@test.local", "password": "AdminSecret123!"}
    )
    resp = client_admin.post(
        f"/admin/users/{student.id}/temporary-password", follow_redirects=False
    )
    assert resp.status_code == 302

    # Student session is dead
    resp_user_after = client_user.get("/student/dashboard", follow_redirects=False)
    assert resp_user_after.status_code == 302
    assert resp_user_after.headers["Location"].endswith("/login")


def test_deactivation_blocks_next_request(client, make_student, login, db_session):
    """Deactivated user is redirected to account_inactive on next request."""
    student = make_student(email="deactivate_me@test.local", password="Passw0rd123!")
    login("deactivate_me@test.local", "Passw0rd123!")
    assert client.get("/student/dashboard").status_code == 200

    student.is_active = False
    db_session.commit()

    resp = client.get("/student/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account-inactive")


def test_approval_flip_blocks_next_request(client, make_examiner, login, db_session):
    """Approved examiner whose approval status changes to rejected is blocked."""
    examiner = make_examiner(approved=True, email="flip_ex@test.local", password="Passw0rd123!")
    login("flip_ex@test.local", "Passw0rd123!")
    assert client.get("/examiner/dashboard").status_code == 200

    examiner.approval_status = "rejected"
    db_session.commit()

    resp = client.get("/examiner/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/pending-approval")


def test_logout_clears_session_and_token_not_reusable(client, make_student, login):
    """Logout clears session and user becomes anonymous."""
    make_student(email="logout_clear@test.local", password="Passw0rd123!")
    login("logout_clear@test.local", "Passw0rd123!")

    client.post("/logout")
    resp = client.get("/student/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_strong_protection_user_agent_change_signs_out(app, make_student):
    """Strong session protection logs out user if User-Agent changes."""
    make_student(email="strong_ua@test.local", password="Passw0rd123!")
    client = app.test_client()

    client.post(
        "/login",
        data={"email": "strong_ua@test.local", "password": "Passw0rd123!"},
        headers={"User-Agent": "BrowserOne/1.0"},
    )

    # Same User-Agent: allowed
    res1 = client.get("/student/dashboard", headers={"User-Agent": "BrowserOne/1.0"})
    assert res1.status_code == 200

    # Changed User-Agent with strong protection: signed out
    res2 = client.get(
        "/student/dashboard",
        headers={"User-Agent": "BrowserTwo/2.0"},
        follow_redirects=False,
    )
    assert res2.status_code == 302
    assert res2.headers["Location"].endswith("/login")
