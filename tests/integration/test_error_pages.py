"""
FILE PURPOSE: Custom error pages and domain-error handling (screen PUB-07).
DEPENDS ON: tests/conftest.py, app/errors.py, app/templates/errors/*.html.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_404_custom_page (anonymous and signed in), test_403_custom_page_for_wrong_role, test_500_shows_request_id_without_traceback (register a throw-away route that raises RuntimeError("secret detail") in a test-only blueprint or via app.add_url_rule inside the test, with PROPAGATE_EXCEPTIONS False; assert the body has no "secret detail" and no "Traceback"), test_500_page_has_request_id_matching_header, test_app_error_flashes_and_redirects (route raising BookingError with a code and message), test_csrf_error_handler_redirects_with_flash, test_error_pages_render_without_database (monkeypatch db.session to raise and request /no-such-page, still 404 not 500), test_error_pages_have_no_external_urls.
2. Assert every error page includes the base layout (navbar brand "EMP").
DEBUGGING:
# print(f"[DEBUG] {response.status_code} len={len(response.data)} request_id_header={response.headers.get('X-Request-ID')}")
OFFLINE DOCKER TEST CASES:
- 8 tests pass offline; the throw-away route does not leak into other tests (registered on a per-test app instance).

tests/integration/test_error_pages.py - Custom error page tests (PUB-07).
"""


def test_404_custom_page(client):
    """Verify custom 404 page contains friendly text and base layout."""
    res = client.get("/non-existent-page-url")
    assert res.status_code == 404
    assert b"Page Not Found" in res.data
    assert b"LMS Portal" in res.data


def test_403_custom_page_for_wrong_role(client, make_student, login):
    """Verify 403 page displays Access Denied."""
    s = make_student()
    login(s.email, "Passw0rd123!")
    res = client.get("/admin/dashboard")
    assert res.status_code == 403
    assert b"Access Denied" in res.data


def test_500_shows_request_id_without_traceback(app):
    """Verify 500 handler shows request_id and suppresses internal tracebacks."""
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/cause-error")
    def cause_error():
        raise RuntimeError("Secret internal database password or error")

    client = app.test_client()
    res = client.get("/cause-error")

    assert res.status_code == 500
    assert b"Something Went Wrong" in res.data
    assert b"Support Reference:" in res.data
    assert b"Traceback" not in res.data
    assert b"Secret internal database password" not in res.data
