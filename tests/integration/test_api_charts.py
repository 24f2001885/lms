"""
tests/integration/test_api_charts.py - Integration tests for /api/v1/charts/* endpoints.
"""

import pytest

from app.blueprints.api_v1.docs import undocumented_endpoints
from app.services import chart_data, windows


@pytest.mark.api
@pytest.mark.charts
def test_each_endpoint_shape_for_allowed_roles(app, api, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    matrix = [
        ("/api/v1/charts/bookings-by-day", ["admin", "examiner", "student"]),
        ("/api/v1/charts/booking-status", ["admin", "examiner", "student"]),
        ("/api/v1/charts/participants-by-slot", ["admin", "examiner"]),
        ("/api/v1/charts/examiner-workload", ["admin", "examiner"]),
        ("/api/v1/charts/examination-completion", ["admin", "examiner"]),
        ("/api/v1/charts/results", ["admin", "examiner", "student"]),
    ]

    for endpoint, roles in matrix:
        for role in roles:
            if role == "examiner":
                user = data.examiner1
            elif role == "student":
                user = data.student1
            else:
                user = data.admin
            client = api(user)
            res = client.get(endpoint)
            assert res.status_code == 200, f"Failed on {endpoint} for {role}"
            body = res.get_json()
            assert "labels" in body
            assert "series" in body
            assert isinstance(body["labels"], list)
            assert isinstance(body["series"], list)
            for s in body["series"]:
                assert "name" in s
                assert "data" in s
                assert len(s["data"]) == len(body["labels"])


@pytest.mark.api
@pytest.mark.charts
def test_forbidden_roles_403_json(app, api, make_chart_dataset):
    data = make_chart_dataset()
    student_client = api(data.student1)

    for endpoint in (
        "/api/v1/charts/participants-by-slot",
        "/api/v1/charts/examiner-workload",
        "/api/v1/charts/examination-completion",
    ):
        res = student_client.get(endpoint)
        assert res.status_code == 403
        body = res.get_json()
        assert body["error"]["code"] == "forbidden"


@pytest.mark.api
@pytest.mark.charts
def test_anonymous_401_json(app, api):
    anon = api(None)
    for endpoint in (
        "/api/v1/charts/bookings-by-day",
        "/api/v1/charts/booking-status",
        "/api/v1/charts/participants-by-slot",
        "/api/v1/charts/examiner-workload",
        "/api/v1/charts/examination-completion",
        "/api/v1/charts/results",
    ):
        res = anon.get(endpoint)
        assert res.status_code == 401
        assert res.get_json()["error"]["code"] == "unauthenticated"


@pytest.mark.api
@pytest.mark.charts
def test_pending_examiner_403_not_approved(app, api, make_user):
    pending_ex = make_user(role="examiner", approval_status="pending")
    client = api(pending_ex)

    for endpoint in (
        "/api/v1/charts/bookings-by-day",
        "/api/v1/charts/booking-status",
        "/api/v1/charts/participants-by-slot",
        "/api/v1/charts/examiner-workload",
        "/api/v1/charts/examination-completion",
        "/api/v1/charts/results",
    ):
        res = client.get(endpoint)
        assert res.status_code == 403
        assert res.get_json()["error"]["code"] == "not_approved"


@pytest.mark.api
@pytest.mark.charts
def test_days_validation_422_with_field(app, api, make_chart_dataset):
    data = make_chart_dataset()
    client = api(data.admin)

    for bad in ("0", "181", "-5", "abc"):
        res = client.get(f"/api/v1/charts/bookings-by-day?days={bad}")
        assert res.status_code == 422
        body = res.get_json()
        assert body["error"]["code"] == "validation_error"
        assert "days" in body["error"]["fields"]


@pytest.mark.api
@pytest.mark.charts
def test_default_days_30_labels_count(app, api, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    client = api(data.admin)
    res = client.get("/api/v1/charts/bookings-by-day")
    assert res.status_code == 200
    assert len(res.get_json()["labels"]) == 30


@pytest.mark.api
@pytest.mark.charts
def test_endpoint_equals_service_output(app, api, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    client = api(data.admin)
    res = client.get("/api/v1/charts/booking-status")
    assert res.status_code == 200

    svc = chart_data.booking_status(data.admin)
    assert res.get_json() == svc


@pytest.mark.api
@pytest.mark.charts
def test_no_store_header_and_json_content_type(app, api, make_chart_dataset):
    data = make_chart_dataset()
    client = api(data.admin)

    res = client.get("/api/v1/charts/booking-status")
    assert res.status_code == 200
    assert res.headers.get("Cache-Control") == "no-store"
    assert "application/json" in res.headers.get("Content-Type", "")


@pytest.mark.api
@pytest.mark.charts
def test_no_identifying_fields_in_payload(app, api, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    forbidden_keys = {"id", "email", "password", "user_id", "password_hash"}

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in forbidden_keys
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    for endpoint in (
        "/api/v1/charts/bookings-by-day",
        "/api/v1/charts/booking-status",
        "/api/v1/charts/participants-by-slot",
        "/api/v1/charts/examiner-workload",
        "/api/v1/charts/examination-completion",
        "/api/v1/charts/results",
    ):
        client = api(data.admin)
        res = client.get(endpoint)
        if res.status_code == 200:
            _walk(res.get_json())


@pytest.mark.api
@pytest.mark.charts
def test_scoping_two_examiners_do_not_leak(app, api, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    client1 = api(data.examiner1)
    client2 = api(data.examiner2)

    res1 = client1.get("/api/v1/charts/participants-by-slot")
    res2 = client2.get("/api/v1/charts/participants-by-slot")

    assert res1.status_code == 200
    assert res2.status_code == 200
    # Examiner 1 has 2 upcoming slots, Examiner 2 has 1 upcoming slot
    assert len(res1.get_json()["labels"]) == 2
    assert len(res2.get_json()["labels"]) == 1


@pytest.mark.api
@pytest.mark.charts
def test_admin_totals_equal_sum_of_examiners(app, api, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    client_adm = api(data.admin)
    client1 = api(data.examiner1)
    client2 = api(data.examiner2)

    res_adm = client_adm.get("/api/v1/charts/participants-by-slot").get_json()
    res1 = client1.get("/api/v1/charts/participants-by-slot").get_json()
    res2 = client2.get("/api/v1/charts/participants-by-slot").get_json()

    adm_booked = sum(res_adm["series"][0]["data"])
    ex1_booked = sum(res1["series"][0]["data"])
    ex2_booked = sum(res2["series"][0]["data"])
    assert adm_booked == ex1_booked + ex2_booked


@pytest.mark.api
@pytest.mark.charts
def test_api_docs_lists_chart_endpoints(app):
    with app.app_context():
        assert undocumented_endpoints(app) == []
