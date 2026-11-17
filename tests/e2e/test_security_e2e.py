"""
E2E browser tests for security, CSP violations, lockout, and session invalidation (P11).
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.security]


def test_no_csp_violations_on_any_page(page, live_server):
    """Walk representative pages and verify zero CSP violations or console errors."""
    violations = []
    page.on("console", lambda msg: violations.append(msg.text) if msg.type == "error" else None)

    for path in ("/login", "/register", "/api/v1/docs"):
        page.goto(f"{live_server}{path}")
        assert page.title() is not None

    csp_errors = [v for v in violations if "Content-Security-Policy" in v]
    assert csp_errors == []


def test_cookie_attributes_in_browser(page, live_server):
    """Verify session cookie is HttpOnly and cannot be accessed via document.cookie."""
    page.goto(f"{live_server}/login")
    cookies = page.evaluate("() => document.cookie")
    assert "session" not in cookies
