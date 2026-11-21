#!/usr/bin/env bash
# =====================================================================
# P7.sh - Phase P7: API Integration (Tier 2, Secondary)
# Course commit message : Milestone-7 EMP-API-Integration
# Branch                : phase/p7-api-integration
# Depends on            : P6 (tag p6-done) AND Gate A (tag tier1-complete)
# Screens               : PUB-08 API reference page (Design Plan 5.1)
# Source of truth       : PDR 3.3/5.7, TDR 5.2, Master Blueprint 3.2 (P7 row)
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P7_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P7"
BRANCH="phase/p7-api-integration"
PREV_TAG="p6-done"

# ---------------------------------------------------------------------
# Pre-flight checks (infrastructure only). Tier 2 is closed until Gate A.
# ---------------------------------------------------------------------
[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P6 first."; exit 1; }
git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || { echo "GATE A CLOSED: tag tier1-complete is missing. Run 'bash scripts/verify_gate_a.sh --tag' first."; exit 1; }
[ -f app/services/booking_engine.py ] || { echo "ERROR: app/services/booking_engine.py missing (Tier 1 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
bash scripts/check_gate.sh "$BRANCH" || { echo "ERROR: gate check refused this branch."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P7 needs)
# ---------------------------------------------------------------------
mkdir -p app/blueprints/api_v1 app/services app/templates/api
mkdir -p tests/unit tests/integration docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P7_update_existing_files.md
<!--
FILE PURPOSE: Update prompts for files already implemented in Tier 1 that P7 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file. Apply the sections in order.

SECTION 1: app/__init__.py
1. Import and register the api_v1 blueprint (app/blueprints/api_v1) with url_prefix "/api/v1" after the four existing blueprints, inside create_app.
2. Set app.json.sort_keys = False so JSON keeps the documented key order.
3. Nothing else changes; every Tier 1 test must stay green.

SECTION 2: app/security/decorators.py
1. Make login_required, role_required, approved_examiner_required, admin_required and student_required API-aware: when request.path starts with "/api/", NEVER redirect and NEVER flash; return a JSON error instead using the shape {"error": {"code", "message"}} with these codes and statuses: not signed in -> 401 "unauthenticated"; inactive account -> 403 "account_inactive"; must_change_password -> 403 "password_change_required"; wrong role -> 403 "forbidden"; examiner pending or rejected -> 403 "not_approved". The check ORDER is unchanged (TDR section 6). HTML behaviour for every other path is unchanged.
2. Put the JSON building in one small private helper so the decorators stay short; do not import blueprint modules.

SECTION 3: app/errors.py
1. Add the module-level mapping ERROR_HTTP_STATUS (error code -> HTTP status) with this policy: state conflicts are 409 (booking_closed, slot_full, duplicate_booking, slot_not_available, cancel_deadline_passed, booking_not_cancellable, booking_not_reschedulable, booking_has_evaluation, slot_creation_closed, slot_edit_locked, slot_started, slot_has_bookings, slot_has_evaluations, slot_not_cancellable, slot_not_changeable, examiner_overlap, exam_has_bookings, course_in_use, rubric_locked, evaluation_locked); invalid values are 422 (validation_error, slot_in_past, invalid_capacity, invalid_time_range, reason_required, total_exceeds_max, score_out_of_range, scores_incomplete, marks_below_existing, weightage_over_100, rubric_total_not_100, examiner_not_eligible, no_examiner_assigned); missing things are 404 (not_found, slot_not_found, booking_not_found, examination_not_found); forbidden is 403 (forbidden, not_approved, not_an_admin, account_inactive, password_change_required); 400 invalid_json and csrf_failed; 401 unauthenticated; 405 method_not_allowed; 415 unsupported_media_type; 500 internal_error. Unknown codes fall back to the exception's own http_status (default 400).
2. Fill the JSON branch that P2 left as a comment: when request.path starts with "/api/", the handlers for AppError (and subclasses), 400, 401, 403, 404, 405, 415, 500 and CSRFError return jsonify({"error": {"code", "message", optional "fields", "request_id"}}) with the mapped status. HTML paths behave exactly as before. The 500 JSON never contains exception text or a trace, only the request id.
3. Provide a public helper error_response(code, message, status=None, fields=None) used by the API blueprint so there is one place that builds the error shape.

SECTION 4: app/templates/base.html
1. Add a footer link "API reference" to /api/v1/docs (visible to everyone). No other change.

SECTION 5: tests/conftest.py
1. Add fixture api (callable per role): api(role) returns a small client wrapper that logs in a fresh user of that role (anonymous when role is None), has get/post/put/delete helpers that send JSON bodies with Content-Type application/json and, when CSRF is enabled in the app, an X-CSRFToken header taken from GET /api/v1/session, and returns the Flask response.
2. Add helpers assert_error(response, status, code) (checks the exact error shape and code), assert_shape(obj, shape) (a tiny hand-written shape checker: dict of key -> type or nested shape or list-of-shape; no external library), and assert_page(response_json) (items, page, per_page, total).

SECTION 6: pyproject.toml, Makefile, Dockerfile, requirements-dev.txt, README.md
1. pyproject.toml: register pytest marker "api". Makefile: add target test-api (pytest -m api).
2. requirements-dev.txt: the first line becomes "-r requirements-tier2.txt" (that file starts with "-r requirements.txt"), so one install covers Tier 1 and Tier 2.
3. Dockerfile: in the base stage copy requirements*.txt and install requirements-tier2.txt when it exists (it includes requirements.txt), otherwise requirements.txt, with the same offline-wheel rule as before.
4. README.md: Quick start installs "requirements-tier2.txt"; add a short "JSON API" section (base path /api/v1, session cookie auth, CSRF header, link to /api/v1/docs and docs/api_examples.md).
DEBUGGING:
# print("[DEBUG] applied P7 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the complete Tier 1 suite passes unchanged.
- GET /api/v1/examinations anonymous returns 401 JSON (not a redirect); GET /admin/dashboard anonymous still redirects to /login.
- An unknown /api/v1/nope returns the JSON 404 shape; an unknown /nope still renders the HTML 404 page.
-->
EOF

cat << 'EOF' > requirements-tier2.txt
# FILE PURPOSE: Tier 2 runtime dependencies on top of Tier 1. Created in P7; packages are added by the phase that needs them.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. First line of content must be "-r requirements.txt" so installing this one file gives Tier 1 plus Tier 2.
# 2. P7 adds NO package (the JSON API uses hand-written controllers on top of Flask and the existing services, no Flask-RESTful). Keep a comment block listing who adds what: P8 none (Chart.js is a vendored static file), P9 none, P10 none, P11 Flask-Login, P12 Flask-Mail and ReportLab.
# 3. Every package added later must be pinned with == to an exact stable version that supports Python 3.11 and 3.12, one per line, alphabetical under a "# Tier 2" comment.
# 4. Never add any Tier 3 package (razorpay) here.
# DEBUGGING:
# python -m pip check   (expect "No broken requirements found.")
# OFFLINE DOCKER TEST CASES:
# - pip install --no-index --find-links=wheels/ -r requirements-tier2.txt succeeds after scripts/vendor_wheels.sh.
# - scripts/check_gate.sh accepts this file because tier1-complete exists and refuses it on a repository without that tag.
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/api_queries.py
"""
FILE PURPOSE: Read-only, role-scoped queries behind the JSON API, so the API shows exactly the same data as the HTML screens (milestone acceptance: "role scoping identical to HTML routes"). Writes always go through the existing services.
DEPENDS ON: app/models, app/services/windows.py, app/services/admin_service.py (dashboard_totals), app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Every function takes the acting user object first and applies the role rule inside the query (never filter in Python after loading): admin sees everything; examiner sees only own assignments and own slots; student sees only what the student screens show. Return db.paginate results (page, per_page clamped to 1..100, error_out=False) for lists and the model object or None for single lookups (None becomes a 404, which also hides foreign rows).
2. list_examinations(user, q, course_id, status, include_deleted, page, per_page): admin all non-deleted (include_deleted only honoured for admin); examiner assigned examinations that are not deleted; student the SAME visibility rule as student_queries (not deleted, course active, status not draft OR at least one non-cancelled slot). Filters: q matches name or course code case-insensitively with escaped LIKE wildcards; course_id int; status must be one of EXAM_STATUSES (unknown value -> ValueError that the controller turns into 422). Order by booking_start then id.
3. get_examination(user, exam_id): same scoping or None.
4. list_slots(user, examination_id, status, page, per_page): admin all slots; examiner slots with examiner_id == user.id; student slots with status available or full, start_at in the future, belonging to examinations visible to students. get_slot(user, slot_id) with the same scoping.
5. list_bookings(user, status, examination_id, page, per_page): student bookings with student_id == user.id; examiner bookings whose CURRENT slot belongs to the examiner; admin all. Eager load slot, examination, student (and student profile) to avoid N+1. get_booking(user, booking_id) with the same scoping.
6. list_examiners(q, status, page, per_page) and list_students(q, page, per_page): admin only (the controller enforces the role; the functions never see non-admin callers). Examiner status filter reuses the HTML semantics: pending, approved (approved and active), inactive, rejected.
7. summary(): returns admin_service.dashboard_totals() as the plain dict {courses, examinations, examiners, students, slots, bookings}.
8. No commits, no writes, no flashing, no request access.
DEBUGGING:
# print(f"[DEBUG] api_queries {name} user={user.id}:{user.role} filters={filters} total={page.total}")
OFFLINE DOCKER TEST CASES:
- A student asking for examinations gets the same ids as the /student/examinations page for the same data; an examiner gets exactly their assigned examinations.
- list_slots for a student never contains cancelled, completed or past slots; for an examiner never another examiner's slot.
- list_bookings for a student never contains another student's booking; for an examiner never a booking of another examiner's slot.
- per_page=1000 is clamped to 100; status="bogus" raises ValueError.
- include_deleted is ignored for non-admin users.
"""
EOF

# ============================ API BLUEPRINT ==========================

cat << 'EOF' > app/blueprints/api_v1/__init__.py
"""
FILE PURPOSE: Defines the api_v1 blueprint (url_prefix /api/v1) and applies its shared request/response rules.
DEPENDS ON: app/blueprints/api_v1/common.py and the route modules listed below.
PROMPT FOR LLM IMPLEMENTATION:
1. Create api_bp = Blueprint("api_v1", __name__) (the factory registers it with url_prefix "/api/v1" from the P7 update).
2. before_request on the blueprint: for POST, PUT and PATCH requests require a JSON body: if Content-Type is not application/json return the 415 error shape ("unsupported_media_type"); a body that is not valid JSON, or not a JSON object, returns 400 "invalid_json". DELETE and GET need no body (DELETE may carry an optional JSON object, for the admin cancel reason). Exempt GET /docs from every check.
3. after_request: add Cache-Control: no-store to every JSON response, keep the X-Request-ID header from the logging hook, and set Content-Type application/json; charset utf-8 for JSON responses only (docs page is HTML).
4. At the bottom import the route modules so they register on api_bp: session, examinations, slots, bookings, people, stats, docs (each with "# noqa: E402,F401"). P8 adds charts.
5. No business logic here.
DEBUGGING:
# print(f"[DEBUG] api {request.method} {request.path} ct={request.content_type} user={getattr(g.user, 'id', None)}")
OFFLINE DOCKER TEST CASES:
- POST with form data returns 415; POST with broken JSON returns 400 invalid_json; POST with a JSON list returns 400.
- Every JSON response carries Cache-Control: no-store and an X-Request-ID header.
- GET /api/v1/docs is reachable without a session and returns HTML.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/common.py
"""
FILE PURPOSE: Shared helpers for all API controllers: response builders, pagination arguments, timestamps and the role guards.
DEPENDS ON: flask, app/errors.py (error_response, ERROR_HTTP_STATUS, AppError), app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. ok(data, status=200, headers=None) returns jsonify(data) with the status; created(data, location) returns 201 with a Location header; no_content() returns an empty 204 response.
2. list_response(page, serializer) returns {"items": [serializer(x) for x in page.items], "page": page.page, "per_page": page.per_page, "total": page.total} exactly as in TDR 5 conventions.
3. page_args(request.args) returns (page, per_page): page default 1, per_page default 20 (config DEFAULT_PAGE_SIZE), per_page above 100 is clamped to 100 (MAX_PAGE_SIZE); a value that is not an integer or is below 1 raises ApiValidationError with fields {"page": ["Must be a whole number of at least 1."]} (422), it is NOT silently ignored.
4. iso(dt) turns a naive UTC datetime into "YYYY-MM-DDTHH:MM:SSZ" (None stays None); parse_iso(text) accepts an ISO 8601 string with "Z" or an explicit offset, converts it to naive UTC and raises ValueError otherwise (a string without any zone is rejected so clients cannot send ambiguous local times).
5. json_body() returns the parsed JSON object (already checked by the blueprint hook); get_int_arg(name) / get_str_arg(name) helpers for query parameters with 422 on bad values.
6. Guards: re-export api_login_required, api_roles(*roles) as thin wrappers around the P2 decorators (which are API-aware after the P7 update) so controllers read cleanly; they must not duplicate any check.
7. translate_app_error(exc) maps an AppError to error_response(code, message) with the status from ERROR_HTTP_STATUS; controllers use it in one try/except around each service call (never repeat status numbers in controllers).
DEBUGGING:
# print(f"[DEBUG] api response status={status} keys={list(data)[:5] if isinstance(data, dict) else type(data)}")
OFFLINE DOCKER TEST CASES:
- iso(datetime(2030,1,10,4,30)) == "2030-01-10T04:30:00Z"; parse_iso("2030-01-10T10:00:00+05:30") gives 04:30 naive UTC; parse_iso("2030-01-10T10:00:00") raises ValueError.
- page_args({"per_page": "500"}) -> per_page 100; page_args({"page": "abc"}) raises the 422 validation error.
- list_response keeps key order items, page, per_page, total.
- translate_app_error(BookingError("slot_full", "...")) yields status 409 and the shape {"error": {"code": "slot_full", "message": "..."}}.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/validation.py
"""
FILE PURPOSE: Tiny schema validator for JSON request bodies (no external library) producing field-level 422 errors.
DEPENDS ON: app/blueprints/api_v1/common.py (parse_iso), app/models enumerations (EXAM_TYPES etc.).
PROMPT FOR LLM IMPLEMENTATION:
1. Class ApiValidationError(Exception) carrying fields: dict[str, list[str]]; the error handler of the blueprint turns it into 422 {"error": {"code": "validation_error", "message": "Some fields are invalid.", "fields": {...}}}.
2. validate(payload, schema, partial=False) -> dict of cleaned values. A schema is a dict field -> spec dict with keys: type ("str", "int", "bool", "datetime", "enum"), required (default False), min / max (length for str, value for int), choices (for enum), strip (default True for str), nullable (default False). Rules: unknown fields are rejected ("Unknown field.") so clients cannot set columns such as role or approval_status (mass-assignment protection); when partial is True required is ignored (PUT with a subset); bools are NOT accepted where an int is expected (True is not 1); ints must be real integers (no "5" strings, no floats like 5.0); strings are stripped and may not be empty when required; datetimes use parse_iso and are returned as naive UTC.
3. Every field error message is plain English, such as "This field is required.", "Must be at least 2 characters.", "Must be one of: viva, practical, project_demo, assessment.", "Must be a valid ISO 8601 date and time with a zone, for example 2030-01-10T04:30:00Z."
4. Export ready-made schemas: EXAMINATION_SCHEMA (course_id, name, description, exam_type, duration_minutes, max_marks, slot_creation_start, slot_creation_end, booking_start, booking_end, cancellation_deadline optional), SLOT_SCHEMA (examination_id, start_at, end_at, max_capacity), BOOKING_CREATE_SCHEMA (slot_id), CANCEL_SCHEMA (reason optional, 3 to 200 chars). Limits MUST equal the form limits of Tier 1 (name 2-150, description up to 2000, duration 1-1440, max_marks 1-1000, capacity 1-500); P9 later replaces the numbers by shared constants.
5. The validator only checks shape and ranges; business rules stay in the services (a 409/422 from a service is translated by common.translate_app_error).
DEBUGGING:
# print(f"[DEBUG] validate fields={list(payload)} partial={partial} errors={errors}")
OFFLINE DOCKER TEST CASES:
- {"slot_id": "5"} fails with "Must be a whole number." and {"slot_id": true} fails too; {"slot_id": 5} passes.
- An unknown field {"role": "admin"} is rejected with "Unknown field."
- Partial PUT {"name": "New"} passes; a missing required field on POST yields "This field is required." for each missing field at once (all errors in one response).
- "2030-01-10T10:00:00" (no zone) fails with the ISO message; "2030-01-10T04:30:00Z" passes and returns naive UTC.
- A name of 1 character and one of 151 characters both fail with the length messages.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/serializers.py
"""
FILE PURPOSE: Single place that turns model objects into JSON dictionaries (field names and visibility per role). No other module builds response dictionaries by hand.
DEPENDS ON: app/models, app/services/windows.py, app/blueprints/api_v1/common.py (iso).
PROMPT FOR LLM IMPLEMENTATION:
1. examination_to_dict(exam, viewer): id, course_id, course_code, name, description, exam_type, duration_minutes, max_marks, slot_creation_start, slot_creation_end, booking_start, booking_end, cancellation_deadline (all via iso), slot_creation_open, booking_open (the Admin switches), slot_creation_effective_open and booking_effective_open (windows.is_*_open, i.e. switch AND dates), status; is_deleted ONLY when the viewer is an admin.
2. slot_to_dict(slot, viewer): id, examination_id, examiner_id, examiner_name, start_at, end_at, max_capacity, booked_count, seats_left, status. Students do not receive examiner_id (name only).
3. booking_to_dict(booking, viewer): id, slot_id, examination_id, status, booked_at, cancelled_at; for admin and examiner also student_id, student_name and student_roll_number; for admin also cancelled_by and rescheduled_from_slot_id. Never any evaluation data.
4. examiner_to_dict(user): id, full_name, email, approval_status, is_active, department, designation, contact_phone. student_to_dict(user): id, full_name, email, is_active, roll_number, program. user_to_dict for the session endpoint: id, full_name, email, role, approval_status.
5. Hard rule: password_hash, must_change_password internals, audit data and IP addresses never appear in any dictionary; include a module-level FORBIDDEN_KEYS set used by the tests to assert this recursively.
6. All datetimes are ISO 8601 UTC strings ending in Z; booleans are real JSON booleans; no Decimal or datetime objects leak.
DEBUGGING:
# print(f"[DEBUG] serialize {type(obj).__name__}#{obj.id} for {viewer.role}")
OFFLINE DOCKER TEST CASES:
- An examination dictionary has the keys above in that order and no is_deleted for a student.
- A student booking dictionary has no student_id/student_name; an examiner's has student_name but no rescheduled_from_slot_id.
- A recursive walk over every serializer output finds none of FORBIDDEN_KEYS.
- Every datetime value matches ^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/session.py
"""
FILE PURPOSE: GET /api/v1/session: who am I, and the CSRF token that state-changing API calls must send (makes the API usable from scripts and the browser console).
DEPENDS ON: api_bp, common.py, serializers.py, flask_wtf.csrf.generate_csrf.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /api/v1/session requires a signed-in, active user (api_login_required): returns 200 {"user": user_to_dict(g.user), "csrf_token": generate_csrf()}. Anonymous callers get 401 "unauthenticated" from the guard.
2. Document in a comment that the token must be sent as the X-CSRFToken header on POST, PUT and DELETE, and that the session cookie is the only credential (TDR 5.2); there is no token authentication in Tier 2.
3. This endpoint is an addition to the TDR list (recorded in the P7 decisions).
DEBUGGING:
# print(f"[DEBUG] session endpoint user={g.user.id} token_len={len(token)}")
OFFLINE DOCKER TEST CASES:
- Signed-in student gets their own user dictionary and a non-empty csrf_token; no password hash key anywhere.
- Anonymous gets 401 with code unauthenticated.
- With CSRF enabled, a POST /api/v1/bookings carrying this token succeeds and one without it returns 400 csrf_failed.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/examinations.py
"""
FILE PURPOSE: /api/v1/examinations: list, read, create, update and soft-delete examinations (TDR 5.2).
DEPENDS ON: api_bp, common.py, validation.py, serializers.py, app/services/api_queries.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /api/v1/examinations (any signed-in role, scoped by api_queries): query parameters course_id, status, q, include_deleted (admin only), page, per_page; returns list_response with examination_to_dict. An invalid status or page gives 422 validation_error.
2. GET /api/v1/examinations/<id>: scoped lookup; not visible or missing -> 404 "examination_not_found" (identical for both so existence is not leaked).
3. POST /api/v1/examinations (admin only): body validated by EXAMINATION_SCHEMA; call catalog_service.create_examination(actor_id, data) with datetimes already naive UTC; respond 201 with the object and a Location header /api/v1/examinations/<id>; service errors via translate_app_error (window problems -> 422, unknown course -> 422).
4. PUT /api/v1/examinations/<id> (admin only): partial validation; merge the provided fields over the current values and call catalog_service.update_examination; 200 with the object. The rules of Tier 1 (max marks below existing evaluations, course locked once slots exist, window validation) are enforced by the service and surface as 409/422.
5. DELETE /api/v1/examinations/<id> (admin only): catalog_service.delete_examination (soft delete) -> 204; refused with 409 exam_has_bookings when booked or completed bookings exist.
6. Non-admin write attempts return 403 "forbidden" before any validation runs. No rule logic in this module.
DEBUGGING:
# print(f"[DEBUG] api examinations {request.method} id={exam_id} user={g.user.id} body_keys={list(body)}")
OFFLINE DOCKER TEST CASES:
- Admin POST with valid body -> 201 + Location and the same fields as GET; a second POST with booking_end before booking_start -> 422 with a message naming the window.
- Student GET list returns the same ids as the HTML list; student POST -> 403; examiner PUT -> 403; anonymous -> 401.
- PUT {"max_marks": 10} with an existing evaluation total of 20 -> 409/422 with code marks_below_existing.
- DELETE twice: first 204, second 404; DELETE with a booked booking -> 409 exam_has_bookings.
- GET /examinations/9999 and a draft examination for a student both return the same 404 shape.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/slots.py
"""
FILE PURPOSE: /api/v1/slots: list and read for every role, create/update/delete for the owning examiner (TDR 5.2).
DEPENDS ON: api_bp, common.py, validation.py, serializers.py, app/services/api_queries.py, app/services/slot_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /api/v1/slots (any signed-in role, scoped by api_queries.list_slots): filters examination_id and status; GET /api/v1/slots/<id> (scoped; missing or foreign -> 404 "slot_not_found"). The single-slot GET is an addition to the TDR list so the Location header of POST is resolvable (recorded in the P7 decisions).
2. POST /api/v1/slots (approved examiner only): SLOT_SCHEMA; call slot_service.create_slot(g.user.id, examination_id, start_at, end_at, max_capacity); 201 with the slot and Location. Window, overlap, capacity and assignment rules come from the service (409 slot_creation_closed, 409 examiner_overlap, 422 invalid_capacity, 404 examination_not_found ...).
3. PUT /api/v1/slots/<id> (owning examiner only): partial body from start_at, end_at, max_capacity (examination_id is NOT updatable: unknown/forbidden field -> 422); merge with current values; slot_service.update_slot; 200 with the object (409 slot_edit_locked, 409 slot_has_bookings).
4. DELETE /api/v1/slots/<id> (owning examiner only): slot_service.delete_slot -> 204 (the service decides hard delete vs cancelled status).
5. Another examiner's slot id always returns 404 (ownership in the query, never 403). Admin and student write attempts return 403.
DEBUGGING:
# print(f"[DEBUG] api slots {request.method} id={slot_id} user={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Examiner A creates a slot inside the window: 201; outside the window: 409 slot_creation_closed with the Tier 1 message.
- Examiner B gets 404 for A's slot on GET, PUT and DELETE; admin POST -> 403; student GET list shows only available future slots.
- PUT with {"examination_id": 2} -> 422 naming the field; PUT after booking_start -> 409 slot_edit_locked.
- Overlapping create -> 409 examiner_overlap; capacity 0 -> 422 validation_error from the schema.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/bookings.py
"""
FILE PURPOSE: /api/v1/bookings: scoped list/read, book (student), cancel (student own or admin with reason) (TDR 5.2).
DEPENDS ON: api_bp, common.py, validation.py, serializers.py, app/services/api_queries.py, app/services/booking_engine.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /api/v1/bookings (any signed-in role): student own, examiner bookings of own slots, admin all; filters status and examination_id; GET /api/v1/bookings/<id> scoped (missing or foreign -> 404 "booking_not_found"; addition to the TDR list).
2. POST /api/v1/bookings (student only): BOOKING_CREATE_SCHEMA {slot_id}; call booking_engine.book_slot(g.user.id, slot_id); 201 with {"id", "slot_id", "examination_id", "status", "booked_at"} (exactly the TDR response) and Location; engine errors translate to 409 booking_closed / slot_full / duplicate_booking / slot_not_available and 404 slot_not_found. The API never reimplements a rule.
3. DELETE /api/v1/bookings/<id>: a student cancels their OWN booking with booking_engine.cancel_booking (no body needed) -> 200 {"id": <id>, "status": "cancelled"}; 409 cancel_deadline_passed / booking_not_cancellable; another student's id -> 404. An admin cancels ANY booking with booking_engine.admin_cancel_booking and a JSON body {"reason": "..."} (3 to 200 characters, CANCEL_SCHEMA; missing reason -> 422); same 200 response. Examiners get 403.
4. No PUT here (rescheduling stays an Admin HTML action in Tier 2); document that in the API reference as intentionally absent.
DEBUGGING:
# print(f"[DEBUG] api bookings {request.method} id={booking_id} user={g.user.id}:{g.user.role}")
OFFLINE DOCKER TEST CASES:
- Student books a slot: 201 with the exact five keys; the same student booking again -> 409 duplicate_booking; last seat taken -> 409 slot_full.
- Student cancels own booking -> 200 cancelled and the slot seat is released; after the deadline -> 409 cancel_deadline_passed.
- Admin DELETE without a reason -> 422; with a reason -> 200 and an audit row booking.admin_cancel exists.
- Examiner DELETE -> 403; student DELETE of another student's booking -> 404.
- The list for an examiner never contains a booking from another examiner's slot.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/people.py
"""
FILE PURPOSE: /api/v1/examiners and /api/v1/students (admin only, read-only) (TDR 5.2).
DEPENDS ON: api_bp, common.py, serializers.py, app/services/api_queries.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /api/v1/examiners (admin only): query status (pending, approved, inactive, rejected), q, page, per_page; list_response with examiner_to_dict.
2. GET /api/v1/students (admin only): query q (name, email, roll number, numeric id), page, per_page; list_response with student_to_dict.
3. No write methods in Tier 2: examiner approval and temporary passwords stay HTML actions. POST/PUT/DELETE on these paths return 405 with the JSON "method_not_allowed" shape.
4. Everyone except an admin gets 403 "forbidden" (students and examiners) or 401 (anonymous) BEFORE any query runs.
DEBUGGING:
# print(f"[DEBUG] api people {request.path} q={request.args.get('q')!r} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Admin lists examiners filtered by status=pending and gets only pending ones; the output has no password hash.
- Student and examiner requests -> 403; anonymous -> 401; POST -> 405 JSON.
- per_page=3 over 10 students returns 3 items and total 10.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/stats.py
"""
FILE PURPOSE: GET /api/v1/stats/summary: the six dashboard totals as JSON (admin only).
DEPENDS ON: api_bp, common.py, app/services/api_queries.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /api/v1/stats/summary (admin only): 200 {"courses": n, "examinations": n, "examiners": n, "students": n, "slots": n, "bookings": n} from api_queries.summary(); the numbers use the same definitions as the Admin dashboard (examinations exclude deleted, slots exclude cancelled, bookings count booked and completed).
2. Other roles get 403, anonymous 401.
DEBUGGING:
# print(f"[DEBUG] api stats summary {totals}")
OFFLINE DOCKER TEST CASES:
- The six numbers equal the figures shown on /admin/dashboard for the same data.
- The response has exactly six integer keys.
"""
EOF

cat << 'EOF' > app/blueprints/api_v1/docs.py
"""
FILE PURPOSE: PUB-08 API reference page at GET /api/v1/docs (public, static content built from one data list).
DEPENDS ON: api_bp, app/templates/api/docs.html.
PROMPT FOR LLM IMPLEMENTATION:
1. Define the module constant API_REFERENCE: a list of dictionaries, one per endpoint, with keys method, path, roles (text), query (list of names), body (list of field names or "none"), success (status and short shape), errors (list of codes). It must describe EVERY rule registered under /api/v1 (session, examinations, slots, bookings, examiners, students, stats; P8 appends the chart endpoints).
2. GET /api/v1/docs renders api/docs.html with API_REFERENCE plus the general sections (authentication, CSRF header, pagination, timestamps, error shape and the status-code policy table). No login required; nothing secret on the page.
3. Provide a function undocumented_endpoints(app) returning the /api/v1 rules that are missing from API_REFERENCE (used by a test as a drift guard so the page can never lag behind the code).
DEBUGGING:
# print(f"[DEBUG] api docs endpoints={len(API_REFERENCE)} undocumented={undocumented_endpoints(current_app)}")
OFFLINE DOCKER TEST CASES:
- GET /api/v1/docs returns 200 HTML for an anonymous visitor.
- undocumented_endpoints(app) is an empty list.
- The page lists at least 4 different HTTP methods (GET, POST, PUT, DELETE) as required by the milestone.
"""
EOF

cat << 'EOF' > app/templates/api/docs.html
<!--
FILE PURPOSE: PUB-08 API reference screen (Design Plan 5.1), a short developer-facing page.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "API reference"; intro sentence "Base path /api/v1. JSON in, JSON out. Sign in through the normal login page; the session cookie is the credential."
2. Sections with h2: Authentication (cookie, GET /api/v1/session returns the CSRF token, send it as X-CSRFToken on POST, PUT, DELETE), Conventions (ISO 8601 UTC timestamps ending in Z, pagination parameters page and per_page with default 20 and maximum 100, list shape items/page/per_page/total), Errors (shape {"error": {"code", "message", "fields"}} and a table of status codes: 400, 401, 403, 404, 405, 409, 415, 422, 500 with the meaning of each), Endpoints.
3. Endpoints: a responsive table (table-responsive) with columns Method (badge), Path (monospace), Who, Query/body, Success, Possible errors; rows from API_REFERENCE; headers use th scope="col". One short curl example in a pre/code block showing: fetch the session token, then POST /api/v1/bookings.
4. A closing note listing what is intentionally absent (no PUT on bookings, no write endpoints for examiners and students).
5. Offline-safe: no external fonts, scripts or images.
DEBUGGING:
DEBUG (add as an HTML comment while debugging): endpoint rows {{ endpoints|length }}
OFFLINE DOCKER TEST CASES:
- The page has one h1, every table header has scope=col, and the HTML contains no http:// or https:// asset URL.
- Every endpoint path in API_REFERENCE appears in the rendered page.
-->
EOF

cat << 'EOF' > docs/api_examples.md
<!--
FILE PURPOSE: Copy-paste examples for the viva demo and for testers (curl and browser console).
PROMPT FOR LLM IMPLEMENTATION:
1. Title "JSON API examples". Prerequisites: run make demo-data, start the server, log in once in the browser or with curl.
2. Section "Sign in with curl": step by step with a cookie jar: GET /login to receive the cookie and read the csrf_token hidden input (show the grep/sed one-liner), then POST /login as form data with csrf_token, email and password; then GET /api/v1/session to read the API csrf token.
3. Section "Browser console": fetch examples with credentials same-origin for GET /api/v1/examinations and POST /api/v1/bookings with headers Content-Type and X-CSRFToken.
4. One worked example per verb required by the course (GET list, POST booking, PUT slot, DELETE booking) showing the request, the expected status and a trimmed response; plus one error example for each of 401, 403, 409, 422.
5. Keep it under 120 lines; all example emails use the demo accounts (student01@demo.local, examiner1@demo.local) and the DEMO_PASSWORD placeholder, never a real password.
DEBUGGING:
(none: documentation file) Verify by running every command on a fresh demo database.
OFFLINE DOCKER TEST CASES:
- Every command in the file succeeds against the demo database with the documented status code.
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_api_validation_serializers.py
"""
FILE PURPOSE: Unit tests for the API validator, helpers and serializers.
DEPENDS ON: app/blueprints/api_v1/validation.py, common.py, serializers.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Validator: test_required_fields_all_reported_at_once, test_unknown_field_rejected, test_partial_ignores_required, test_int_rejects_bool_string_float, test_str_strip_and_length_bounds, test_enum_choices_message, test_datetime_requires_zone, test_datetime_converted_to_naive_utc, test_nullable_field, test_cancel_schema_reason_length.
2. Helpers: test_iso_format, test_parse_iso_offsets, test_page_args_defaults_clamp_and_errors, test_list_response_key_order, test_translate_app_error_status_map (loop over ERROR_HTTP_STATUS and assert each code yields its status and the exact shape).
3. Serializers: test_examination_fields_and_order, test_is_deleted_only_for_admin, test_student_booking_hides_student_fields, test_examiner_booking_shows_student_name_not_admin_fields, test_slot_hides_examiner_id_for_student, test_forbidden_keys_never_present_recursively, test_all_datetimes_are_iso_z, test_no_decimal_or_datetime_objects_leak (json.dumps with no default must succeed).
DEBUGGING:
# print(f"[DEBUG] validator case {name}: errors={errors}")
OFFLINE DOCKER TEST CASES:
- 28 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_api_access_matrix.py
"""
FILE PURPOSE: Proves every /api/v1 endpoint is locked to the right roles with the right status codes (role scoping identical to HTML).
DEPENDS ON: tests/conftest.py (api fixture, factories), app.url_map.
PROMPT FOR LLM IMPLEMENTATION:
1. Collect every rule under /api/v1 from app.url_map at collection time (excluding /docs) and drive a table EXPECTED[(method, rule)] -> {role: status} written in the test (roles: anonymous, student, examiner, pending_examiner, inactive_student, admin_must_change_password, admin). Examples: GET /api/v1/examinations -> anonymous 401, others 200 (pending examiner 403 not_approved, inactive 403 account_inactive, admin with forced password change 403 password_change_required); POST /api/v1/examinations -> admin 4xx-or-201 depending on payload, everyone else 403; GET /api/v1/examiners -> admin 200, everyone else 403.
2. A completeness check: every collected rule+method has an EXPECTED entry, so a new endpoint without a matrix row fails the test.
3. Every denied response is JSON with the error shape and never a redirect or HTML page; a pending examiner hitting an admin endpoint gets 403 forbidden (role check before approval, TDR 6).
4. CSRF: with CSRF enabled, POST/PUT/DELETE without X-CSRFToken returns 400 csrf_failed JSON; with the token from /api/v1/session the request reaches the controller.
DEBUGGING:
# print(f"[DEBUG] {method} {rule} as {role} -> {response.status_code} {response.get_json(silent=True)}")
OFFLINE DOCKER TEST CASES:
- All parametrised cases pass offline (about 80); adding an undeclared endpoint makes the completeness check fail.
"""
EOF

cat << 'EOF' > tests/integration/test_api_examinations_slots.py
"""
FILE PURPOSE: Behaviour tests for the examinations and slots endpoints (CRUD, scoping, error mapping).
DEPENDS ON: tests/conftest.py, freeze_now.
PROMPT FOR LLM IMPLEMENTATION:
1. Examinations: test_list_scoped_by_role_matches_html_ids, test_list_filters_and_paging, test_invalid_status_422, test_get_one_and_foreign_404_identical, test_admin_create_201_location_and_fields, test_create_validation_fields_422, test_create_window_order_422_message, test_update_partial_200, test_update_marks_below_existing_conflict, test_update_course_locked_after_slots, test_delete_204_then_404, test_delete_with_bookings_409, test_include_deleted_admin_only, test_non_admin_writes_403_before_validation.
2. Slots: test_list_student_only_future_available, test_examiner_list_only_own, test_create_201_in_window, test_create_outside_window_409, test_create_overlap_409, test_create_unassigned_examination_404, test_update_200_and_locked_409, test_update_examination_id_422, test_delete_204, test_other_examiner_404_on_get_put_delete, test_admin_and_student_writes_403, test_get_slot_location_resolvable.
3. Use freeze_now to control windows; assert both status and the exact error code.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.get_json()}")
OFFLINE DOCKER TEST CASES:
- 26 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_api_bookings_people_stats.py
"""
FILE PURPOSE: Behaviour tests for bookings, examiners, students, stats and session endpoints.
DEPENDS ON: tests/conftest.py (api fixture, make_open_booking_setup).
PROMPT FOR LLM IMPLEMENTATION:
1. Bookings: test_student_books_201_exact_keys, test_book_duplicate_409, test_book_full_409, test_book_closed_409, test_book_unknown_slot_404, test_book_schema_422 (string id, bool, missing), test_student_cancel_200_releases_seat, test_cancel_after_deadline_409, test_cancel_foreign_booking_404, test_admin_cancel_requires_reason_422, test_admin_cancel_200_audited, test_examiner_delete_403, test_list_scoped_student_examiner_admin, test_get_one_scoped, test_no_put_route_405.
2. People/stats/session: test_examiners_list_status_filter, test_students_search_by_roll_number_and_id, test_people_non_admin_403, test_people_write_methods_405_json, test_stats_summary_matches_dashboard, test_session_returns_user_and_csrf, test_session_anonymous_401, test_no_password_hash_in_any_response (walk every endpoint response as admin).
3. Equivalence test test_api_and_html_book_same_outcome: the same booking attempt through the HTML route and the API produces the same engine error code for each failure case.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.get_json()}")
OFFLINE DOCKER TEST CASES:
- 25 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_api_contract_errors.py
"""
FILE PURPOSE: Contract tests (TDR 10): response shapes, error shape, status policy and the API reference page.
DEPENDS ON: tests/conftest.py (assert_shape, assert_error, assert_page).
PROMPT FOR LLM IMPLEMENTATION:
1. Shapes: for each endpoint family call it once as the allowed role and check the exact shape with assert_shape (types of every field, nullable fields, key sets); list endpoints with assert_page.
2. Error shape: test_every_error_response_has_error_code_message (loop over representative failures: 401, 403, 404 unknown API path, 405, 409, 415, 422 with fields, 400 invalid_json, 400 csrf_failed, forced 500 via a test-only route that raises: the body has code internal_error, a request_id and no trace text).
3. Policy: test_status_policy_table (a representative failure per mapped code returns the status in ERROR_HTTP_STATUS).
4. Isolation: test_html_routes_unchanged_by_json_branch (HTML 404 and 403 pages still render; anonymous HTML route still redirects).
5. Docs: test_docs_page_public_200, test_docs_lists_every_endpoint (undocumented_endpoints is empty), test_docs_mentions_four_methods, test_docs_no_external_urls.
6. Headers: test_json_responses_no_store_and_request_id.
DEBUGGING:
# print(f"[DEBUG] contract case {name}: {response.status_code} {response.get_json(silent=True)}")
OFFLINE DOCKER TEST CASES:
- 22 tests pass offline; the drift-guard test fails if an /api/v1 rule is added without an API_REFERENCE row.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P7 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P7_update_existing_files.md in ORDER (decorators and errors first) with the CURRENT files."
echo "2. Run 'docker compose --profile test run --rm test' (or 'make test-core' and 'make test-api'), then try the examples in docs/api_examples.md against 'make demo-data'."
echo "3. Run 'git add . && git commit -m \"wip: P7 JSON API\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p7-api-integration && git commit -m \"Milestone-7 EMP-API-Integration\" && git tag p7-done && git push origin main --tags'."
echo "5. Decisions to confirm: manual JSON controllers (no Flask-RESTful); extra endpoints GET /api/v1/session, GET /api/v1/slots/<id>, GET /api/v1/bookings/<id>; 409 for state conflicts and 422 for invalid values."
echo "6. Execute P8.sh"
echo "====================================================="
