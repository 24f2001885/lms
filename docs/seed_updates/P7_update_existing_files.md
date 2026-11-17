<!--
FILE PURPOSE: Update prompts for files already implemented in Tier 1 that P7 must change.
Apply the sections in order (decorators and errors first).
-->
# P7 Existing File Updates Summary

## SECTION 1: `app/__init__.py`
1. Import `api_bp` from `app.blueprints.api_v1` and register it with `url_prefix="/api/v1"` after the four existing HTML blueprints inside `create_app`.
2. Set `app.json.sort_keys = False` so JSON responses keep documented key order.

## SECTION 2: `app/security/decorators.py`
1. Make `login_required`, `role_required`, `approved_examiner_required`, `admin_required`, and `student_required` API-aware via a shared helper `_api_auth_error(code, message, status)`:
   - When `request.path.startswith("/api/")`, NEVER redirect and NEVER flash.
   - Return `error_response(code, message, status=status)` with:
     - Not signed in -> `401` `"unauthenticated"`
     - Inactive account -> `403` `"account_inactive"`
     - `must_change_password` -> `403` `"password_change_required"`
     - Wrong role -> `403` `"forbidden"`
     - Examiner `approval_status != "approved"` -> `403` `"not_approved"`
   - Check order remains identical to TDR Section 6 (login -> active -> role -> password change -> examiner approval).

## SECTION 3: `app/errors.py`
1. Add `ERROR_HTTP_STATUS` mapping error codes to HTTP statuses (409 conflicts, 422 validation/invalid values, 404 missing, 403 forbidden, 400 bad JSON/CSRF, 401 unauthenticated, 405 method not allowed, 415 unsupported media type, 500 internal error).
2. Add `error_response(code, message, status=None, fields=None)` returning `(jsonify(payload), resolved_status)`.
3. In handlers for `AppError`, `400`, `401`, `403`, `404`, `405`, `415`, `500`, and `CSRFError`, when `request.path.startswith("/api/")`, return JSON error responses including `request_id` (from `g.request_id`). Never expose stack traces or exception details in 500 JSON responses.

## SECTION 4: `app/templates/base.html`
1. Add footer link `<a href="{{ url_for('api_v1.api_docs') }}">API reference</a>` visible to everyone.

## SECTION 5: `tests/conftest.py`
1. Add `api` fixture (`api(role)` returning `ApiClientWrapper` with `.get()`, `.post()`, `.put()`, `.delete()`, automatic `Content-Type: application/json`, and automatic `X-CSRFToken` fetched from `GET /api/v1/session`).
2. Add assertion helpers `assert_error(response, status, code)`, `assert_shape(obj, shape)`, and `assert_page(response_json)`.

## SECTION 6: `pyproject.toml`, `Makefile`, `Dockerfile`, `requirements-dev.txt`, `README.md`
1. `pyproject.toml`: register `api: JSON API integration and contract tests` marker.
2. `Makefile`: add `test-api` target running `pytest -m api`.
3. `requirements-dev.txt`: start with `-r requirements-tier2.txt`.
4. `Dockerfile`: install `requirements-tier2.txt` if present, otherwise `requirements.txt`.
5. `README.md`: document Quick Start with `requirements-tier2.txt` and add JSON API overview section.
