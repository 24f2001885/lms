"""
FILE PURPOSE: Integration tests for registration, login, logout, change password and the pending/inactive notices (milestone M2 acceptance).
DEPENDS ON: tests/conftest.py, app/blueprints/auth/routes.py, app/forms/auth.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Register tests: test_student_register_success, test_examiner_register_pending_with_profile, test_register_admin_role_rejected_no_user_created, test_register_duplicate_email_case_insensitive, test_register_password_mismatch, test_register_weak_password, test_register_stores_hash_not_plaintext, test_signed_in_user_redirected_from_register.
2. Login tests: test_login_student_redirects_to_student_dashboard, test_login_wrong_password_generic_message, test_login_unknown_email_same_response_as_wrong_password (compare normalised bodies), test_login_pending_examiner_goes_to_pending_page, test_login_rejected_examiner_sees_not_approved, test_login_inactive_user_goes_to_inactive_page, test_login_updates_last_login_at, test_login_next_param_external_ignored, test_session_fixation_old_session_value_removed.
3. Admin flow: test_seeded_admin_must_change_password_then_dashboard (run init-db helpers or make_admin(must_change_password=True), login, expect redirect to /change-password, change it, expect /admin/dashboard), test_change_password_wrong_current_rejected, test_change_password_same_as_old_rejected, test_change_password_clears_flag.
4. Logout tests: test_logout_requires_post (GET returns 405), test_logout_clears_session_and_redirects, test_protected_page_after_logout_redirects_to_login.
5. Notice pages: test_pending_page_redirects_non_examiners, test_pending_examiner_approved_in_db_gets_dashboard_next_request, test_inactive_page_redirects_active_users.
6. Use client.post with data dicts and follow_redirects=False so redirect targets can be asserted exactly.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')} flashes={list(get_flashed_messages(with_categories=True))}")
OFFLINE DOCKER TEST CASES:
- All 26 tests pass with no network.
- Running the file twice in a row passes both times (no state leaks between tests).

tests/integration/test_auth_register_login.py - Registration, Login, and Session flow tests.
"""

from app.models import ExaminerProfile, StudentProfile, User


def test_student_register_success(client, app):
    """Verify student registration creates user and student_profile rows."""
    res = client.post(
        "/register",
        data={
            "role": "student",
            "full_name": "Alice Student",
            "email": "alice@student.test",
            "password": "Passw0rdAlice1",
            "confirm_password": "Passw0rdAlice1",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/login")

    user = User.query.filter_by(email="alice@student.test").first()
    assert user is not None
    assert user.role == "student"
    assert user.approval_status == "approved"
    assert StudentProfile.query.filter_by(user_id=user.id).first() is not None


def test_examiner_register_pending_with_profile(client, app):
    """Verify examiner registration creates user with pending status and examiner_profile."""
    res = client.post(
        "/register",
        data={
            "role": "examiner",
            "full_name": "Bob Examiner",
            "email": "bob@examiner.test",
            "password": "Passw0rdBob123",
            "confirm_password": "Passw0rdBob123",
            "department": "Computer Science",
            "contact_phone": "+91 98765 43210",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302

    user = User.query.filter_by(email="bob@examiner.test").first()
    assert user is not None
    assert user.role == "examiner"
    assert user.approval_status == "pending"

    profile = ExaminerProfile.query.filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.department == "Computer Science"


def test_register_admin_role_rejected(client, app):
    """Verify admin role cannot be registered through UI."""
    client.post(
        "/register",
        data={
            "role": "admin",
            "full_name": "Attacker",
            "email": "hacker@test.local",
            "password": "Passw0rdHack1!",
            "confirm_password": "Passw0rdHack1!",
        },
    )
    assert User.query.filter_by(email="hacker@test.local").first() is None


def test_login_student_redirects_to_student_dashboard(client, make_student, login):
    """Verify student login redirects to /student/dashboard."""
    make_student(email="s1@test.local", password="Passw0rd123!")
    res = login("s1@test.local", "Passw0rd123!")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/student/dashboard")


def test_login_wrong_password_generic_message(client, make_student, login):
    """Verify wrong password returns 200 with generic error message."""
    make_student(email="s2@test.local", password="CorrectPass123!")
    res = login("s2@test.local", "WrongPassword!")
    assert res.status_code == 200
    assert b"Invalid email or password" in res.data


def test_login_pending_examiner_goes_to_pending_page(client, make_examiner, login):
    """Verify unapproved examiner is redirected to /pending-approval."""
    make_examiner(approved=False, email="ex_pend@test.local", password="Passw0rd123!")
    res = login("ex_pend@test.local", "Passw0rd123!")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/pending-approval")


def test_logout_requires_post(client, make_student, login):
    """Verify GET /logout returns 405 Method Not Allowed."""
    make_student(email="logout_test@test.local", password="Passw0rd123!")
    login("logout_test@test.local", "Passw0rd123!")

    # GET is rejected
    get_res = client.get("/logout")
    assert get_res.status_code == 405

    # POST succeeds
    post_res = client.post("/logout", follow_redirects=False)
    assert post_res.status_code == 302
    assert post_res.headers["Location"].endswith("/login")


def test_seeded_admin_must_change_password_flow(client, make_admin, login):
    """Verify seeded admin is forced to change password before dashboard access."""
    make_admin(
        email="seed_admin@test.local", password="SeedPassword123!", must_change_password=True
    )
    res = login("seed_admin@test.local", "SeedPassword123!")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/change-password")

    # Update password
    update_res = client.post(
        "/change-password",
        data={
            "current_password": "SeedPassword123!",
            "new_password": "NewAdminPass123!",
            "confirm_new_password": "NewAdminPass123!",
        },
        follow_redirects=False,
    )
    assert update_res.status_code == 302
    assert update_res.headers["Location"].endswith("/admin/dashboard")

    admin = User.query.filter_by(email="seed_admin@test.local").first()
    assert admin.must_change_password is False


def test_session_fixation_old_session_value_removed(client, make_student, login):
    """Verify session fixation prevention: pre-login session data is cleared, Flask-Login key is set."""
    student = make_student(email="fixation@test.local", password="Passw0rd123!")

    with client.session_transaction() as sess:
        sess["pre_login_key"] = "attacker_value"

    login("fixation@test.local", "Passw0rd123!")

    with client.session_transaction() as sess:
        assert "pre_login_key" not in sess
        assert "_user_id" in sess
        assert sess["_user_id"].startswith(f"{student.id}:")
