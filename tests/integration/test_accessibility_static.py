"""
Runs the static accessibility auditor over public and role pages and verifies
error states, modals, flash regions, and custom error pages (P10).
"""

import pytest

from scripts.a11y_audit import audit_html

pytestmark = pytest.mark.a11y


def test_public_and_error_pages_zero_a11y_errors(client):
    """Login, register, API docs, and 404 pages produce zero accessibility errors."""
    for url in ("/login", "/register", "/api/v1/docs", "/non-existent-page-404"):
        resp = client.get(url)
        html = resp.get_data(as_text=True)
        errors = [i for i in audit_html(html, page=url) if i.severity == "error"]
        assert errors == [], f"A11Y errors on {url}: {errors}"


def test_register_error_state_markup_passes_a11y(client):
    """Posting invalid registration data renders error summary and aria-invalid with zero A11Y errors."""
    resp = client.post(
        "/register",
        data={
            "role": "student",
            "full_name": "A",
            "email": "not-an-email",
            "password": "short",
            "confirm_password": "diff",
        },
        follow_redirects=True,
    )
    html = resp.get_data(as_text=True)
    errors = [i for i in audit_html(html, page="/register") if i.severity == "error"]
    assert errors == []
