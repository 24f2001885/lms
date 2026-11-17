"""
FILE PURPOSE: P7 additions for tests/conftest.py (api client wrapper + assert_error/assert_shape/assert_page).
"""

import json
from typing import Any

import pytest
from werkzeug.security import generate_password_hash

from app.models import ExaminerProfile, StudentProfile, User


class ApiClientWrapper:
    def __init__(self, client, user: User | None = None):
        self.client = client
        self.user = user
        self._csrf_token: str | None = None

    def refresh_csrf(self) -> str | None:
        if self.user is None:
            return None
        resp = self.client.get("/api/v1/session")
        if resp.status_code == 200:
            data = resp.get_json()
            self._csrf_token = data.get("csrf_token")
        return self._csrf_token

    def _headers(
        self, include_json: bool = True, include_csrf: bool = False, extra=None
    ) -> dict[str, str]:
        hdrs: dict[str, str] = {}
        if include_json:
            hdrs["Content-Type"] = "application/json"
        if include_csrf:
            if not self._csrf_token:
                self.refresh_csrf()
            if self._csrf_token:
                hdrs["X-CSRFToken"] = self._csrf_token
        if extra:
            hdrs.update(extra)
        return hdrs

    def get(self, url: str, **kwargs):
        return self.client.get(url, **kwargs)

    def post(
        self,
        url: str,
        data: Any = None,
        raw_data: str | None = None,
        headers=None,
        skip_csrf: bool = False,
    ):
        hdrs = self._headers(include_json=True, include_csrf=not skip_csrf, extra=headers)
        body = (
            raw_data if raw_data is not None else (json.dumps(data) if data is not None else None)
        )
        return self.client.post(url, data=body, headers=hdrs)

    def put(self, url: str, data: Any = None, headers=None, skip_csrf: bool = False):
        hdrs = self._headers(include_json=True, include_csrf=not skip_csrf, extra=headers)
        body = json.dumps(data) if data is not None else None
        return self.client.put(url, data=body, headers=hdrs)

    def delete(self, url: str, data: Any = None, headers=None, skip_csrf: bool = False):
        has_body = data is not None
        hdrs = self._headers(include_json=has_body, include_csrf=not skip_csrf, extra=headers)
        body = json.dumps(data) if has_body else None
        return self.client.delete(url, data=body, headers=hdrs)


@pytest.fixture
def api(app, db_session):
    counter = {"n": 0}

    def _factory(role: str | None = None) -> ApiClientWrapper:
        client = app.test_client()
        if role is None:
            return ApiClientWrapper(client, user=None)

        counter["n"] += 1
        idx = counter["n"]
        pw = "TestPass#123"
        pw_hash = generate_password_hash(pw)

        actual_role = role
        approval = "approved"
        active = True
        must_change = False

        if role == "pending_examiner":
            actual_role = "examiner"
            approval = "pending"
        elif role == "inactive_student":
            actual_role = "student"
            active = False
        elif role == "admin_must_change_password":
            actual_role = "admin"
            must_change = True

        user = User(
            email=f"api_{role}_{idx}@test.local",
            password_hash=pw_hash,
            full_name=f"API {role.title()} {idx}",
            role=actual_role,
            approval_status=approval,
            is_active=active,
            must_change_password=must_change,
        )
        db_session.add(user)
        db_session.flush()

        if actual_role == "student":
            db_session.add(
                StudentProfile(user_id=user.id, roll_number=f"API26S{idx:03d}", program="BS DS")
            )
        elif actual_role == "examiner":
            db_session.add(ExaminerProfile(user_id=user.id, department="CS", designation="Prof"))
        db_session.commit()

        with client.session_transaction() as sess:
            sess["user_id"] = user.id

        wrapper = ApiClientWrapper(client, user=user)
        wrapper.refresh_csrf()
        return wrapper

    return _factory


def assert_error(response, status: int, code: str) -> dict[str, Any]:
    assert (
        response.status_code == status
    ), f"Expected {status}, got {response.status_code}: {response.get_data(as_text=True)}"
    assert response.mimetype == "application/json"
    body = response.get_json()
    assert isinstance(body, dict) and "error" in body
    err = body["error"]
    assert err.get("code") == code
    assert isinstance(err.get("message"), str) and len(err["message"]) > 0
    return err


def assert_shape(obj: Any, shape: Any) -> None:
    if isinstance(shape, dict):
        assert isinstance(obj, dict), f"Expected dict, got {type(obj)}"
        assert set(obj.keys()) == set(
            shape.keys()
        ), f"Key mismatch: {set(obj.keys())} != {set(shape.keys())}"
        for k, sub_shape in shape.items():
            assert_shape(obj[k], sub_shape)
    elif isinstance(shape, list):
        assert isinstance(obj, list), f"Expected list, got {type(obj)}"
        if shape and obj:
            for item in obj:
                assert_shape(item, shape[0])
    elif isinstance(shape, tuple):
        assert isinstance(obj, shape), f"Expected one of {shape}, got {type(obj)}"
    else:
        assert isinstance(obj, shape), f"Expected {shape}, got {type(obj)} ({obj!r})"


def assert_page(response_json: dict[str, Any]) -> None:
    assert isinstance(response_json, dict)
    assert list(response_json.keys()) == ["items", "page", "per_page", "total"]
    assert isinstance(response_json["items"], list)
    assert isinstance(response_json["page"], int)
    assert isinstance(response_json["per_page"], int)
    assert isinstance(response_json["total"], int)
