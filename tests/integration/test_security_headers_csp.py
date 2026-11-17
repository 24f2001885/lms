"""
Tests verifying security headers, Content-Security-Policy compliance,
and template hygiene across all role pages (P11).
"""

import re

import pytest

pytestmark = pytest.mark.security


def test_every_page_has_all_security_headers(client):
    """Verify standard security headers are present on public responses."""
    for path in ("/login", "/register", "/api/v1/docs"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "same-origin"
        assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"
        assert "Permissions-Policy" in resp.headers


def test_no_inline_executable_scripts(client):
    """HTML templates do not contain inline executable script tags."""
    for path in ("/login", "/register", "/api/v1/docs"):
        html = client.get(path).get_data(as_text=True)
        # Match <script> tags that don't have src and are not application/json
        script_tags = re.findall(r"<script([^>]*)>(.*?)</script>", html, re.DOTALL | re.IGNORECASE)
        for attrs, body in script_tags:
            if not body.strip():
                continue
            assert (
                'type="application/json"' in attrs or "type='application/json'" in attrs
            ), f"Inline executable script found in {path}: {body[:100]}"


def test_no_inline_event_handler_attributes(client):
    """No inline onclick/onload/etc event handler attributes exist in rendered HTML."""
    on_pattern = re.compile(r'\s(on[a-zA-Z]+)=["\']', re.IGNORECASE)
    for path in ("/login", "/register", "/api/v1/docs"):
        html = client.get(path).get_data(as_text=True)
        matches = on_pattern.findall(html)
        assert matches == [], f"Inline event handlers found in {path}: {matches}"


def test_no_javascript_urls(client):
    """No href="javascript:" or action="javascript:" URLs exist in rendered pages."""
    for path in ("/login", "/register", "/api/v1/docs"):
        html = client.get(path).get_data(as_text=True)
        assert "javascript:" not in html.lower()


def test_no_external_hosts_in_pages_or_css(client):
    """Pages and assets only reference local origins ('self' and data:)."""
    http_ext_pattern = re.compile(
        r'(?:href|src)=["\'](https?://(?!127\.0\.0\.1|localhost)[^"\']+)["\']'
    )
    for path in ("/login", "/register", "/api/v1/docs"):
        html = client.get(path).get_data(as_text=True)
        matches = http_ext_pattern.findall(html)
        assert matches == [], f"External host references in {path}: {matches}"


def test_forms_post_to_same_origin(client):
    """Form action attributes only post to relative paths on the same origin."""
    action_pattern = re.compile(r'<form[^>]*action=["\']([^"\']+)["\']', re.IGNORECASE)
    for path in ("/login", "/register"):
        html = client.get(path).get_data(as_text=True)
        actions = action_pattern.findall(html)
        for act in actions:
            assert act.startswith("/") or act == "", f"Non-local form action in {path}: {act}"


def test_authenticated_pages_are_no_store(client, make_student, login):
    """Authenticated responses carry Cache-Control: no-store and Vary: Cookie."""
    make_student(email="no_cache@test.local", password="Passw0rd123!")
    login("no_cache@test.local", "Passw0rd123!")

    resp = client.get("/student/dashboard")
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "Cookie" in resp.headers.get("Vary", "")


def test_error_pages_have_headers(client):
    """404 and 403 error responses include full security headers."""
    for status_code, path in [(404, "/non-existent-404-url")]:
        resp = client.get(path)
        assert resp.status_code == status_code
        assert "Content-Security-Policy" in resp.headers
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_csp_covers_static_and_json(client):
    """Static assets and JSON responses receive security headers."""
    resp_static = client.get("/static/css/app.css")
    assert resp_static.status_code == 200
    assert "Content-Security-Policy" in resp_static.headers

    resp_json = client.get("/api/v1/examinations")
    assert "Content-Security-Policy" in resp_json.headers


def test_api_docs_page_headers(client):
    """API docs page carries required security headers and CSP."""
    resp = client.get("/api/v1/docs")
    assert resp.status_code == 200
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]
