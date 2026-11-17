"""
FILE PURPOSE: Contract tests for JSON error shapes, headers, HTML isolation, and PUB-08 API reference page.
"""

import pytest

from app.blueprints.api_v1.docs import undocumented_endpoints


@pytest.mark.api
def test_docs_page_public_and_drift_guard(app, api):
    with app.app_context():
        assert undocumented_endpoints(app) == []

    anon = api(None)
    res = anon.get("/api/v1/docs")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "<h1>API reference</h1>" in html
    assert "http://" not in html
    assert "https://" not in html
    for verb in ("GET", "POST", "PUT", "DELETE"):
        assert verb in html


@pytest.mark.api
def test_media_type_invalid_json_and_headers(api):
    student = api("student")

    # Wrong Content-Type -> 415
    res_ct = student.client.post(
        "/api/v1/bookings",
        data="slot_id=1",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": student._csrf_token,
        },
    )
    assert res_ct.status_code == 415
    assert res_ct.get_json()["error"]["code"] == "unsupported_media_type"
    assert res_ct.headers.get("Cache-Control") == "no-store"

    # Broken JSON -> 400 invalid_json
    res_bad = student.post("/api/v1/bookings", raw_data="{not-json")
    assert res_bad.status_code == 400
    assert res_bad.get_json()["error"]["code"] == "invalid_json"

    # Unknown API path -> 404 JSON; unknown HTML path -> 404 HTML
    res_404_api = student.get("/api/v1/nonexistent")
    assert res_404_api.status_code == 404
    assert res_404_api.mimetype == "application/json"

    res_404_html = student.get("/nonexistent-page")
    assert res_404_html.status_code == 404
    assert res_404_html.mimetype == "text/html"
