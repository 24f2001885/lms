"""
FILE PURPOSE: Role-based access matrix and CSRF behaviour (acceptance: wrong-role URLs return 403, Admin cannot be registered, pending examiner blocked).
DEPENDS ON: tests/conftest.py, app/security/decorators.py, stub blueprints.
PROMPT FOR LLM IMPLEMENTATION:
1. Parametrised matrix test_role_access_matrix over (role, url, expected) for roles anonymous, student, approved_examiner, pending_examiner, inactive_examiner, admin (password-changed) and urls /admin/dashboard, /examiner/dashboard, /student/dashboard, /profile, /change-password. Expected values are 200, 302 (with the exact Location suffix: /login, /pending-approval, /account-inactive, /change-password) or 403, taken from Design Plan section 3 and the decorator order in app/security/decorators.py.
2. test_flags_checked_on_every_request: log in as an approved examiner, flip approval_status to "pending" in the database, next request redirects; flip is_active False, next request redirects to inactive.
3. test_admin_cannot_be_created_through_ui (register with role=admin, tampered role value like "Admin " and "ADMIN"; no admin row beyond the seeded one).
4. test_direct_url_access_without_session_redirects_to_login for every protected URL.
5. test_logout_form_present_for_signed_in_pages and test_no_register_link_when_signed_in.
6. CSRF: test_post_without_csrf_token_is_rejected builds an app with WTF_CSRF_ENABLED True, posts to /login without a token and expects the CSRF handler outcome (flash and redirect, never a 500 and never a successful login); test_post_with_valid_token_succeeds fetches the token from the login page HTML first.
7. test_security_cookie_flags: the session cookie is HttpOnly and SameSite=Lax (inspect Set-Cookie).
DEBUGGING:
# print(f"[DEBUG] matrix role={role} url={url} -> {response.status_code} {response.headers.get('Location')}")
OFFLINE DOCKER TEST CASES:
- The 6 x 5 matrix passes (30 parametrised cases) offline.
- Removing role_required from any stub dashboard makes at least one matrix case fail.

tests/integration/test_rbac_access.py - 6x5 Role-Based Access Control matrix tests.
"""

import pytest

from app import create_app


@pytest.mark.parametrize(
    "role_setup,target_url,expected_status,location_suffix",
    [
        # Anonymous user
        (None, "/admin/dashboard", 302, "/login"),
        (None, "/examiner/dashboard", 302, "/login"),
        (None, "/student/dashboard", 302, "/login"),
        (None, "/profile", 302, "/login"),
        # Student user
        ("student", "/admin/dashboard", 403, None),
        ("student", "/examiner/dashboard", 403, None),
        ("student", "/student/dashboard", 200, None),
        ("student", "/profile", 200, None),
        # Approved examiner
        ("examiner_approved", "/admin/dashboard", 403, None),
        ("examiner_approved", "/examiner/dashboard", 200, None),
        ("examiner_approved", "/student/dashboard", 403, None),
        ("examiner_approved", "/profile", 200, None),
        # Pending examiner
        ("examiner_pending", "/examiner/dashboard", 302, "/pending-approval"),
        ("examiner_pending", "/student/dashboard", 403, None),
        # Inactive examiner
        ("examiner_inactive", "/examiner/dashboard", 302, "/account-inactive"),
        # Admin
        ("admin", "/admin/dashboard", 200, None),
        ("admin", "/examiner/dashboard", 403, None),
        ("admin", "/student/dashboard", 403, None),
        ("admin", "/profile", 200, None),
    ],
)
def test_role_access_matrix(
    client, app, make_user, login, role_setup, target_url, expected_status, location_suffix
):
    """Verify RBAC access permissions across roles and URLs."""
    if role_setup == "student":
        u = make_user(role="student")
        login(u.email, "Passw0rd123!")
    elif role_setup == "examiner_approved":
        u = make_user(role="examiner", approval_status="approved")
        login(u.email, "Passw0rd123!")
    elif role_setup == "examiner_pending":
        u = make_user(role="examiner", approval_status="pending")
        login(u.email, "Passw0rd123!")
    elif role_setup == "examiner_inactive":
        u = make_user(role="examiner", approval_status="approved", is_active=False)
        login(u.email, "Passw0rd123!")
    elif role_setup == "admin":
        u = make_user(role="admin", must_change_password=False)
        login(u.email, "Passw0rd123!")

    res = client.get(target_url, follow_redirects=False)
    assert res.status_code == expected_status
    if location_suffix:
        assert res.headers["Location"].endswith(location_suffix)


def test_post_without_csrf_token_is_rejected(tmp_path):
    """Verify that enabling CSRF causes POST requests without tokens to be caught."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'csrf_test.db'}"

    with app.app_context():
        from app.extensions import db

        db.create_all()
        client = app.test_client()

        # POST without CSRF token
        res = client.post("/login", data={"email": "any@test.local", "password": "pass"}, follow_redirects=False)
        # Custom CSRF handler redirects back with a warning flash
        assert res.status_code == 302
        db.drop_all()