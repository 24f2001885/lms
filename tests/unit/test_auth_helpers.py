"""
FILE PURPOSE: Unit tests for pure helper functions in app/security/auth_helpers.py.
DEPENDS ON: app/security/auth_helpers.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_password_strength_rules (too short, no digit, no letter, valid), test_safe_redirect_accepts_relative_paths, test_safe_redirect_rejects_external_and_tricky (//evil.com, https://x, /\\x, javascript:, newline injection), test_verify_credentials_success_mixed_case_email, test_verify_credentials_wrong_password_returns_none, test_verify_credentials_unknown_email_returns_none, test_verify_credentials_runs_hash_for_unknown_email (monkeypatch check_password_hash and assert it was called once even for an unknown email), test_post_login_redirect_priority (must_change_password beats inactive beats pending beats role dashboard; use test_request_context for url_for).
2. Use the app fixture for application context; no HTTP calls in this file.
DEBUGGING:
# print(f"[DEBUG] redirect target for {user.role}: {post_login_redirect_url(user)}")
OFFLINE DOCKER TEST CASES:
- 8 tests pass offline; test_verify_credentials_runs_hash_for_unknown_email fails if the dummy-hash step is removed.

tests/unit/test_auth_helpers.py - Unit tests for security helpers in app/security/auth_helpers.py.
"""

from app.security.auth_helpers import (
    is_safe_redirect_target,
    post_login_redirect_url,
    validate_password_strength,
    verify_credentials,
)


def test_password_strength_rules():
    """Verify password strength validation criteria."""
    assert len(validate_password_strength("short1A")) > 0  # < 8 chars
    assert len(validate_password_strength("onlyletterslong")) > 0  # No digit
    assert len(validate_password_strength("1234567890")) > 0  # No letter
    assert len(validate_password_strength("Passw0rdValid!")) == 0


def test_safe_redirect_accepts_relative_paths():
    """Verify relative paths are accepted as safe targets."""
    assert is_safe_redirect_target("/student/dashboard") is True
    assert is_safe_redirect_target("/admin/courses?q=test") is True


def test_safe_redirect_rejects_external_and_tricky():
    """Verify phishing and open redirect targets are rejected."""
    assert is_safe_redirect_target("https://evil.com") is False
    assert is_safe_redirect_target("//evil.com") is False
    assert is_safe_redirect_target("/\\evil.com") is False
    assert is_safe_redirect_target("javascript:alert(1)") is False
    assert is_safe_redirect_target("/dashboard\nhttps://evil.com") is False


def test_verify_credentials_success_mixed_case_email(app, make_user):
    """Verify credentials check succeeds with mixed-case email input."""
    user = make_user(email="testuser@test.local", password="SecretPass123!")
    verified = verify_credentials("TestUser@Test.Local", "SecretPass123!")
    assert verified is not None
    assert verified.id == user.id


def test_verify_credentials_wrong_password_returns_none(app, make_user):
    """Verify wrong password returns None."""
    make_user(email="wrongpass@test.local", password="CorrectPass123!")
    assert verify_credentials("wrongpass@test.local", "WrongPass") is None


def test_verify_credentials_unknown_email_returns_none(app):
    """Verify unknown email returns None."""
    assert verify_credentials("nonexistent@test.local", "AnyPass") is None


def test_verify_credentials_runs_hash_for_unknown_email(app, monkeypatch):
    """Verify constant-time dummy hash check is executed for unknown emails."""
    calls = []

    def mock_check(p_hash, p_candidate):
        calls.append(True)
        return False

    monkeypatch.setattr("app.security.auth_helpers.check_password_hash", mock_check)
    verify_credentials("nobody@test.local", "SomePassword")
    assert len(calls) == 1


def test_post_login_redirect_priority(app, make_user, make_examiner):
    """Verify post-login redirect priority order."""
    with app.test_request_context():
        # 1. must_change_password beats all
        u1 = make_user(role="admin", must_change_password=True)
        assert post_login_redirect_url(u1).endswith("/change-password")

        # 2. Inactive account redirect
        u2 = make_user(role="student", is_active=False)
        assert post_login_redirect_url(u2).endswith("/account-inactive")

        # 3. Pending examiner redirect
        u3 = make_examiner(approved=False)
        assert post_login_redirect_url(u3).endswith("/pending-approval")

        # 4. Standard dashboard redirect
        u4 = make_user(role="student")
        assert post_login_redirect_url(u4).endswith("/student/dashboard")
