#!/usr/bin/env bash
# =====================================================================
# P3.sh - Milestone M3: Admin Dashboard & Examination Management (Tier 1)
# Course commit message : Milestone-3 EMP-Admin-Dashboard-Exams
# Branch                : phase/p3-admin-dashboard-exams
# Depends on            : P2 (tag p2-done)
# Screens               : ADM-01 to ADM-15, ADM-17, ADM-18 (Design Plan 5.2)
# NOT in P3            : ADM-16 reschedule screen and admin cancel (they need
#                        booking_engine, built in P5/P6). See notes at the end.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are described in
# docs/seed_updates/P3_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P3"
BRANCH="phase/p3-admin-dashboard-exams"
PREV_TAG="p2-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P2 first."; exit 1; }
[ -f app/security/decorators.py ] || { echo "ERROR: app/security/decorators.py missing (P2 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P3 needs)
# ---------------------------------------------------------------------
mkdir -p app/services app/forms app/blueprints/admin
mkdir -p app/templates/admin app/templates/macros
mkdir -p tests/unit tests/integration docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P3_update_existing_files.md
<!--
FILE PURPOSE: One update prompt per file that earlier phases already implemented and P3 must change. Do NOT regenerate these files from scratch. For each section give the LLM the section text plus the CURRENT file.
HOW TO USE: process the sections one at a time; after all are applied run the whole test suite.

SECTION 1: app/__init__.py
1. Register two Jinja filters: localdt (format a naive-UTC datetime with app.services.windows.format_local, empty string for None) and money_marks (strip trailing zeros from Decimal/float marks).
2. Do not register new blueprints (the admin blueprint already exists) and do not add other globals: badges are rendered by the macro in templates/macros/status_badge.html. Keep all P1/P2 behaviour.

SECTION 2: app/blueprints/admin/__init__.py (stub from P2)
1. Keep admin_bp = Blueprint("admin", __name__, url_prefix="/admin").
2. DELETE the stub dashboard route and the auth/role_landing_stub.html rendering for admin.
3. At the bottom import the route modules so they register on admin_bp: dashboard, courses, examinations, rubrics, examiners, students, slots, bookings, search, history (each with "# noqa: E402,F401").
4. No logic in this file besides the blueprint object and the imports.

SECTION 3: app/templates/base.html
1. Wrap the default top navbar in {% block site_nav %}...{% endblock %} and wrap the main element in {% block layout %}...{% endblock %} so role bases can replace them (admin sidebar, examiner/student top navs later).
2. Move the flash-message loop into a new partial templates/_flash.html (same markup: aria-live polite region, alert role) and include it from base.html inside the default layout block. Role bases that override layout must include _flash.html themselves.
3. Keep the skip-link target id main-content on whatever element holds the page content. Keep the csrf meta tag and all existing behaviour.

SECTION 4: app/static/css/app.css
1. Add styles for the admin shell: .admin-shell (flex layout), .admin-sidebar (width 240px, background #14283B, light text with 4.5:1 contrast, sticky), .admin-sidebar a.active (left border 4px primary), .admin-content (padding, min-width 0).
2. Add .stat-card (white card, large number, muted label), .timeline-switch (inline status + button row), .table-filter-bar (flex wrap, gap), .badge-outline-warning for the "Closed" examination badge (amber outline).
3. Below 992px the sidebar becomes a collapsed block above the content (full off-canvas drawer is P10).

SECTION 5: tests/conftest.py
1. Add factories make_assignment(examination, examiner, assigned_by=None) and make_evaluation(booking, examiner, status="draft", total=0, scores=None).
2. Add fixture freeze_now(dt): monkeypatches app.services.windows.now_utc to return dt and returns a helper to move the clock. This works ONLY because services call windows.now_utc() through the module (never "from ... import now_utc").
3. Add fixture admin_client: creates a seeded-like admin (must_change_password False), logs in via POST /login and returns the logged-in test client.

SECTION 6: tests/integration/test_rbac_access.py
1. The admin row of the matrix now expects 200 from /admin/dashboard with the real dashboard (content contains "Dashboard"); other roles' expectations are unchanged.
DEBUGGING:
# print("[DEBUG] applied P3 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections: the whole P0-P2 suite still passes (make test-core).
- GET /admin/dashboard as admin returns 200 and renders the sidebar; anonymous still 302 to /login; student 403.
-->
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/windows.py
"""
FILE PURPOSE: The ONLY place that knows the time and evaluates examination time windows (risk R-3: timezone and boundary bugs).
DEPENDS ON: app/models/examination.py, app/errors.py (WindowError, BOOKING_CLOSED, CANCEL_DEADLINE_PASSED), zoneinfo, app config APP_TIMEZONE.
PROMPT FOR LLM IMPLEMENTATION:
1. now_utc() returns the current time as a NAIVE UTC datetime (datetime.now(timezone.utc).replace(tzinfo=None)). It is the single clock of the whole project. Every other module must call it as windows.now_utc() through the module object, NEVER "from app.services.windows import now_utc", so tests can monkeypatch one attribute. Put this rule in a comment.
2. Timezone helpers using zoneinfo.ZoneInfo(current_app.config["APP_TIMEZONE"]): to_local(dt) (naive UTC -> aware local), from_local_input(text) (parse an HTML datetime-local string such as "2030-01-10T10:00", treat it as APP_TIMEZONE local time, return naive UTC, raise ValueError on bad text), format_local(dt, fmt="%d %b %Y, %H:%M") (empty string for None), to_input_value(dt) (naive UTC -> "YYYY-MM-DDTHH:MM" local, for pre-filling forms).
3. Constants for error codes defined here: SLOT_CREATION_CLOSED = "slot_creation_closed", SLOT_EDIT_LOCKED = "slot_edit_locked"; BOOKING_CLOSED and CANCEL_DEADLINE_PASSED come from app/errors.py.
4. Predicates, all taking (exam, now=None) and using now_utc() when now is None; boundaries are INCLUSIVE on both ends (start <= now <= end) as in TDR 3.3 step 3:
   - is_slot_creation_open: exam.slot_creation_open is True AND slot_creation_start <= now <= slot_creation_end AND not exam.is_deleted.
   - is_booking_open: exam.booking_open is True AND booking_start <= now <= booking_end AND not exam.is_deleted.
   - can_student_cancel: now <= exam.cancellation_deadline (the booking status check is the engine's job).
   - slots_editable: now < exam.booking_start (examiners may update or remove slots only BEFORE student booking starts, PDR 5.3).
5. Assertion helpers that raise WindowError(code, message): assert_slot_creation_open, assert_booking_open, assert_slots_editable, assert_can_cancel. Messages are plain English and include the relevant local date when useful ("Slot creation opens on 10 Jan 2030, 10:00.", "Booking is closed.").
6. window_state(exam, now=None) returns a dict for the UI: {"slot_creation": {"open": bool, "label": "Open"/"Closed"/"Scheduled", "reason": str}, "booking": {...}, "cancel": {...}} where reason explains WHY it is closed (switch off, not started yet with the start date, ended, deleted). This feeds the disabled-button reason lines required by Design Plan principle 3.
7. No database access in this file other than reading attributes of the Examination object passed in.
DEBUGGING:
# print(f"[DEBUG] windows now={now} booking={exam.booking_start}->{exam.booking_end} flag={exam.booking_open} open={result}")
OFFLINE DOCKER TEST CASES:
- is_booking_open is False when the switch is off even inside the dates, False when the switch is on but now is 1 second before booking_start, True exactly at booking_start and exactly at booking_end, False 1 second after booking_end.
- from_local_input("2030-01-10T10:00") with APP_TIMEZONE Asia/Kolkata returns 2030-01-10 04:30 (naive UTC); to_input_value reverses it.
- from_local_input("not a date") raises ValueError.
- window_state reason mentions the start date when booking has not started.
- grep over app/ finds no "from app.services.windows import now_utc".
"""
EOF

cat << 'EOF' > app/services/audit_service.py
"""
FILE PURPOSE: Single writer of audit_logs rows (append-only history of important actions).
DEPENDS ON: app/models/audit_log.py, app/extensions.py, flask (request for the IP).
PROMPT FOR LLM IMPLEMENTATION:
1. log_action(actor_id, action, entity_type, entity_id=None, details=None, ip_address=None) creates an AuditLog row and adds it to db.session WITHOUT committing, so it commits or rolls back together with the business change that caused it. details is a dict serialised with json.dumps(sort_keys=True, default=str); None stays NULL. When ip_address is None and a request context exists, use request.remote_addr.
2. Define action-name constants (strings, dotted lower case) that all later phases reuse: COURSE_CREATE, COURSE_UPDATE, COURSE_DELETE, EXAM_CREATE, EXAM_UPDATE, EXAM_DELETE, EXAM_SLOT_CREATION_TOGGLE, EXAM_BOOKING_TOGGLE, RUBRIC_ADD, RUBRIC_UPDATE, RUBRIC_DELETE, EXAM_EXAMINER_ASSIGN, EXAM_EXAMINER_UNASSIGN, USER_EXAMINER_CREATE, USER_APPROVE, USER_REJECT, USER_DEACTIVATE, USER_ACTIVATE, USER_TEMP_PASSWORD, SLOT_EXAMINER_CHANGE. (Later phases add BOOKING_*, SLOT_*, EVALUATION_*, SYSTEM_* constants in their own phases.)
3. NEVER put passwords, hashes, tokens or the generated temporary password in details; log only ids, field names changed and short reasons.
4. history_for(entity_type, entity_id) returns the rows newest first (used by detail pages and the history view); recent(limit=50) returns the newest rows overall.
DEBUGGING:
# print(f"[DEBUG] audit {action} {entity_type}#{entity_id} actor={actor_id} details={details}")
OFFLINE DOCKER TEST CASES:
- log_action followed by db.session.rollback() leaves no row (not committed by the helper).
- details with a datetime value is stored as valid JSON text; details=None stores NULL.
- A request-context call stores the client IP; a call outside a request stores NULL.
- history_for returns rows newest first.
"""
EOF

cat << 'EOF' > app/services/slot_rules.py
"""
FILE PURPOSE: Shared slot rule(s) used by Admin (P3 change examiner) and Examiner (P4 slot create/update) so the rule exists once.
DEPENDS ON: app/models/slot.py.
PROMPT FOR LLM IMPLEMENTATION:
1. has_overlap(examiner_id, start_at, end_at, exclude_slot_id=None) -> bool: True when the examiner already has a slot whose status is NOT "cancelled" that overlaps the half-open interval [start_at, end_at). Two slots overlap when existing.start_at < end_at AND existing.end_at > start_at; back-to-back slots (end == next start) do NOT overlap. The check spans ALL examinations of that examiner. exclude_slot_id removes the slot being edited from the comparison.
2. find_overlapping(examiner_id, start_at, end_at, exclude_slot_id=None) returns the first conflicting slot or None, so error messages can show its time.
3. Read-only queries; no commits; no flashing; no exceptions.
DEBUGGING:
# print(f"[DEBUG] overlap check examiner={examiner_id} {start_at}->{end_at} exclude={exclude_slot_id} conflict={conflict and conflict.id}")
OFFLINE DOCKER TEST CASES:
- 10:00-11:00 vs existing 10:30-11:30 overlaps; vs existing 11:00-12:00 does not; vs existing 09:00-10:00 does not.
- A cancelled slot never conflicts.
- exclude_slot_id lets a slot be moved within its own time span.
- Overlap is detected across two different examinations of the same examiner, but not between two different examiners.
"""
EOF

cat << 'EOF' > app/services/exam_status.py
"""
FILE PURPOSE: Derives and stores the lifecycle status of an examination (draft, slot_creation, booking_open, closed, completed). Used lazily on reads in P3; the scheduled job that calls sync_all arrives in P6.
DEPENDS ON: app/services/windows.py, app/models (Examination, ExaminationSlot, Booking, Evaluation), app/services/audit_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. compute_status(exam, now=None) -> str, evaluated in THIS order (first match wins): (a) exam.is_deleted -> keep the stored status; (b) booking effectively open (windows.is_booking_open) -> "booking_open"; (c) slot creation effectively open (windows.is_slot_creation_open) -> "slot_creation"; (d) now > exam.booking_end: if the examination has at least one non-cancelled slot AND every non-cancelled slot has end_at < now AND no booking with status in (booked, completed) lacks an evaluation with status submitted or published -> "completed", otherwise "closed"; (e) otherwise "draft" (nothing opened yet, or between windows).
2. refresh_status(exam, actor_id=None, now=None) -> bool: compute, and if different from exam.status set it, write an audit row (action "exam.status_change", details {"from":..,"to":..}) via audit_service.log_action, and return True. It adds changes to the session without committing (caller commits).
3. status_label(status) returns the human text used in badges ("Slot creation", "Booking open", ...).
4. sync_all(now=None) is declared but only documented here ("implemented in P6 as the sync-exam-status job: loop non-deleted examinations, call refresh_status, mark past slots/bookings completed"); in P3 it may raise NotImplementedError.
5. Keep it side-effect free apart from the status column and the audit row.
DEBUGGING:
# print(f"[DEBUG] exam {exam.id} status {exam.status} -> {new_status} at {now}")
OFFLINE DOCKER TEST CASES:
- New exam with both switches off, now before every window: "draft".
- Switch on and inside the booking dates: "booking_open"; same dates with the switch off and now after booking_end: "closed".
- After booking_end with one past slot and one published evaluation per booking: "completed"; with one booking still unevaluated: "closed".
- No slots at all after booking_end: "closed" (never "completed").
- refresh_status twice in a row changes the status once and writes exactly one audit row.
"""
EOF

cat << 'EOF' > app/services/search_service.py
"""
FILE PURPOSE: Admin search over students, examiners, examinations and bookings by NAME or ID (PDR 5.1).
DEPENDS ON: app/models, app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. escape_like(text) escapes the LIKE wildcards % and _ and the escape character itself, and every query uses .ilike(pattern, escape="\\") with the pattern %text%. No string-built SQL anywhere.
2. search(kind, q, page=1, per_page=20) where kind is one of "student", "examiner", "examination", "booking" (whitelist; anything else raises ValueError). q is stripped and limited to 100 characters; an empty q returns an empty result with a hint message flag instead of dumping all rows. Returns a pagination object from db.paginate(..., max_per_page=100, error_out=False).
3. Matching rules: if q is all digits also match id == int(q) (OR with the text match). student/examiner: users.full_name, users.email, plus student roll_number / examiner department (joined profiles), restricted by role. examination: name, description and course code/name (joined), INCLUDING soft-deleted rows but flagged. booking: booking id, student full name or email, examination name; joined so each result row has student, examination, slot time and status.
4. Order: exact id match first, then name ascending. Every result row is a plain model object; the template decides what to show. Never return password hashes to templates (templates must not print them).
DEBUGGING:
# print(f"[DEBUG] search kind={kind} q={q!r} digits={q.isdigit()} total={result.total}")
OFFLINE DOCKER TEST CASES:
- Searching "ana" finds students named Ana and Diana (case-insensitive) but no examiners.
- Searching "7" returns the user with id 7 as the first student result.
- Searching "100%" does not match everything (wildcard escaped).
- kind="invoice" raises ValueError; empty q returns zero rows and the hint flag.
- Booking search by student email finds that student's bookings across statuses.
"""
EOF

cat << 'EOF' > app/services/catalog_service.py
"""
FILE PURPOSE: Business rules for courses, examinations, rubrics, examiner assignment and the two timeline switches. Blueprints call these functions; they never write rules themselves.
DEPENDS ON: app/models, app/services/windows.py, app/services/exam_status.py, app/services/audit_service.py, app/errors.py (AppError).
PROMPT FOR LLM IMPLEMENTATION:
1. General contract: every function takes actor_id first, validates, mutates via db.session, writes ONE audit row, commits once, and returns the object. Rule violations raise AppError(code, message) with a stable lowercase code. IntegrityError from unique constraints is caught and converted (duplicate course code -> "duplicate_course_code").
2. COURSES: create_course(actor_id, code, name, description, status) normalises code to UPPERCASE and strips. update_course(...). delete_course(actor_id, course_id): hard delete ONLY when the course has no examinations, otherwise raise AppError("course_in_use", "This course has examinations. Set it to inactive instead."). set status inactive is done through update_course.
3. EXAMINATIONS: create_examination(actor_id, data) and update_examination(actor_id, exam_id, data) where data holds the fields from TDR 4.1 with datetimes already converted to naive UTC by the form layer. Validate in Python BEFORE hitting the CHECK constraints and give field-level messages: creation start < end, booking start < end, slot_creation_end <= booking_start, cancellation_deadline >= booking_start (default booking_end when missing), duration > 0, max_marks > 0, course exists and is active (for new exams). update rules: max_marks cannot go below the largest total_marks of an existing evaluation ("marks_below_existing"); course cannot change once the examination has slots ("course_locked"). After create/update call exam_status.refresh_status.
4. delete_examination(actor_id, exam_id): SOFT delete (is_deleted = True) allowed only when no booking with status booked or completed exists; otherwise AppError("exam_has_bookings", ...). Also switches both Admin switches off. Never hard delete.
5. TOGGLES: toggle_slot_creation(actor_id, exam_id, open: bool) and toggle_booking(actor_id, exam_id, open: bool). Opening slot creation requires at least one assigned examiner who is approved and active ("no_examiner_assigned"). Opening booking requires rubric_weightage_total == 100 within 0.01 ("rubric_total_not_100") and a non-deleted examination. Closing never has preconditions. The switch is only a flag: effective openness also needs the dates (windows.py); return the exam so the UI can show window_state. Audit actions exam.slot_creation_toggle / exam.booking_toggle with {"open": bool}. Refresh status after each toggle.
6. RUBRICS: rubric_weightage_total(exam_id) returns a Decimal; add_rubric, update_rubric, delete_rubric(actor_id, ...). Rules: each weightage 0..100 and max_score > 0 (form + service); criterion_name unique per examination (friendly error "duplicate_criterion"); NO rubric change once any evaluation exists for the examination ("rubric_locked"); a criterion referenced by evaluation_scores can never be deleted. Adding a criterion that would push the total above 100 is rejected ("weightage_over_100"); the total may be below 100 while editing (it is only enforced when opening booking). rubric_max_score_total(exam_id) is provided for the UI warning when it differs from exam.max_marks (informational only).
7. ASSIGNMENT: assign_examiner(actor_id, exam_id, examiner_id) only for users with role examiner, approval_status approved and is_active ("examiner_not_eligible"); duplicate -> "already_assigned". unassign_examiner(actor_id, exam_id, examiner_id) is refused while that examiner owns a non-cancelled slot of this examination ("examiner_has_slots": change the slot examiner first).
8. List helpers with filters and pagination for the Admin screens: list_courses(q, status, page), list_examinations(q, course_id, exam_type, status, include_deleted, page). Use db.paginate, per_page 20.
DEBUGGING:
# print(f"[DEBUG] catalog {function_name} exam={exam_id} total_weight={total} open={open}")
OFFLINE DOCKER TEST CASES:
- Creating two courses with codes "cs101" and "CS101" fails the second with duplicate_course_code; stored code is "CS101".
- delete_course with an examination raises course_in_use; without one it deletes.
- create_examination with booking_end before booking_start gives a field-level error and no row.
- toggle_slot_creation(open=True) without an assigned approved examiner raises no_examiner_assigned.
- toggle_booking(open=True) with rubric weightages 60+30 raises rubric_total_not_100; with 60+40 succeeds and the status becomes "booking_open" when now is inside the dates.
- add_rubric after an evaluation exists raises rubric_locked.
- delete_examination with one booked booking raises exam_has_bookings; with only cancelled bookings it soft-deletes and both switches are off.
- unassign_examiner with an active slot raises examiner_has_slots.
"""
EOF

cat << 'EOF' > app/services/admin_service.py
"""
FILE PURPOSE: Admin rules for people and slots: examiner approval lifecycle, temporary passwords, changing a slot's examiner, and the dashboard totals.
DEPENDS ON: app/models, app/services/slot_rules.py, app/services/audit_service.py, app/errors.py, werkzeug.security.
PROMPT FOR LLM IMPLEMENTATION:
1. dashboard_totals() returns a dict of six main numbers plus sub-numbers: courses (all), examinations (not soft-deleted), examiners (all examiner accounts; sub: pending_approval), students (all), slots (not cancelled), bookings (status booked or completed; sub: cancelled). Use COUNT queries only (no row loading).
2. Examiner lifecycle (each audits and commits once): approve_examiner(actor_id, user_id) pending or rejected -> approved, profile status active; reject_examiner(...) pending -> rejected; deactivate_user(...) sets users.is_active False and, for examiners, examiner_profiles.status "inactive" (an Admin cannot deactivate themselves: AppError "cannot_deactivate_self"); activate_user(...) reverses it. Only role examiner is approvable; calling approve on a student raises AppError("not_an_examiner").
3. create_examiner(actor_id, full_name, email, phone, department, designation, temporary_password): creates an APPROVED, active examiner with must_change_password True plus the profile row; email normalised lowercase and unique ("email_taken"). The temporary password is validated with validate_password_strength.
4. set_temporary_password(actor_id, user_id, new_password=None) works for examiners and students only (never for another admin): when new_password is None generate one with secrets.token_urlsafe(9); store the hash, set must_change_password True, audit "user.temp_password" WITHOUT the password, and RETURN the plain password once so the view can flash it a single time. Note in a comment: existing signed cookies stay valid until they expire (stateless sessions); accepted limitation, revisited in P11.
5. change_slot_examiner(actor_id, slot_id, new_examiner_id): slot status must be available or full (not cancelled or completed: "slot_not_changeable"); the new examiner must be assigned to the slot's examination (examination_examiners), approved and active ("examiner_not_eligible"); must differ from the current one; slot_rules.has_overlap must be False ("examiner_overlap" with the conflicting time in the message). Update slot.examiner_id, audit "slot.examiner_change" with {"from": old, "to": new}. Existing bookings and evaluations stay attached; evaluations.examiner_id keeps the examiner who actually evaluated (TDR 3.4). P6 moves this logic into booking_engine.change_examiner and leaves this function as a thin wrapper.
6. Every function raises AppError with stable codes; none flashes or redirects.
DEBUGGING:
# print(f"[DEBUG] admin_service {name} actor={actor_id} target={target_id}")
OFFLINE DOCKER TEST CASES:
- approve_examiner flips pending to approved; the examiner's next request reaches /examiner/dashboard (integration test).
- deactivate_user on the Admin's own id raises cannot_deactivate_self.
- create_examiner stores must_change_password True and the examiner can log in and is forced to /change-password.
- set_temporary_password returns a string of at least 12 characters, the stored hash verifies against it, and no audit row contains it.
- change_slot_examiner to an unassigned examiner raises examiner_not_eligible; to an examiner with an overlapping slot raises examiner_overlap; success keeps booked_count and bookings unchanged.
- dashboard_totals returns six integers matching hand-counted fixtures.
"""
EOF

# =============================== FORMS ===============================

cat << 'EOF' > app/forms/common.py
"""
FILE PURPOSE: Tiny shared forms used by every role (CSRF-only POST actions and list filters).
DEPENDS ON: flask_wtf, wtforms.
PROMPT FOR LLM IMPLEMENTATION:
1. ConfirmForm(FlaskForm) with no fields: used for every state-changing POST that needs no input (approve, delete, toggle, book, cancel). It exists so each such button is a real form carrying the CSRF token; the view calls form.validate_on_submit().
2. FilterForm base: a FlaskForm subclass with meta csrf = False for GET filter bars, plus helper parse_page(request.args) returning an int >= 1 (default 1) and per_page clamped to 1..100 (default 20). Invalid values fall back to the defaults, never raise.
3. Nothing else; no business rules.
DEBUGGING:
# print(f"[DEBUG] ConfirmForm valid={form.validate_on_submit()} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- A POST without a CSRF token fails ConfirmForm validation when WTF_CSRF_ENABLED is True.
- parse_page({"page": "abc"}) returns page 1; per_page "500" is clamped to 100; per_page "0" to 1.
"""
EOF

cat << 'EOF' > app/forms/course.py
"""
FILE PURPOSE: WTForms for creating and editing a course (ADM-03).
DEPENDS ON: flask_wtf, wtforms, app/models/course.py.
PROMPT FOR LLM IMPLEMENTATION:
1. CourseForm fields: code (DataRequired, Length 2-20, filter strip+upper, Regexp letters digits and - _ only), name (DataRequired, Length 2-150), description (Optional, Length max 2000, TextAreaField), status (SelectField choices from COURSE_STATUSES, default "active").
2. A constructor argument course_id lets validate_code skip the course being edited when checking duplicates (case-insensitive). Duplicate message: "A course with this code already exists."
3. Labels match the PDR: "Course code", "Course name", "Description", "Status".
DEBUGGING:
# print(f"[DEBUG] CourseForm errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- Code "cs 101" (space) is invalid; "cs101" is stored as "CS101".
- Editing a course and keeping its own code is valid; using another course's code is not.
"""
EOF

cat << 'EOF' > app/forms/examination.py
"""
FILE PURPOSE: WTForms for creating and editing an examination (ADM-05) with datetime-local inputs.
DEPENDS ON: flask_wtf, wtforms, app/models/examination.py, app/models/course.py, app/services/windows.py (from_local_input, to_input_value).
PROMPT FOR LLM IMPLEMENTATION:
1. ExaminationForm fields: course_id (SelectField of ACTIVE courses, coerce int), name (DataRequired, Length 2-150), description (Optional TextArea), exam_type (SelectField from EXAM_TYPES with labels Viva, Practical, Project demo, Assessment), duration_minutes (IntegerField, NumberRange 1-1440), max_marks (IntegerField, NumberRange 1-1000), slot_creation_start, slot_creation_end, booking_start, booking_end, cancellation_deadline (StringField rendered as type datetime-local; cancellation_deadline Optional).
2. A method to_service_data() converts the five datetime strings with windows.from_local_input into naive UTC and returns the dict for catalog_service; invalid text produces a field error "Enter a valid date and time".
3. A method populate_from(exam) fills the form for editing using windows.to_input_value.
4. Cross-field validation (mirror of the service, for early feedback; the service remains authoritative): slot creation end after start, booking end after booking start, slot creation end not after booking start, cancellation deadline not before booking start. Each message names the two fields involved.
5. HTML5 attributes (required, min, max) are added in the template; no JavaScript.
DEBUGGING:
# print(f"[DEBUG] ExaminationForm data={form.data} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- booking_end earlier than booking_start fails with a message naming both fields.
- Submitting local "2030-01-10T10:00" with Asia/Kolkata results in to_service_data()["booking_start"] == 2030-01-10 04:30.
- Blank cancellation_deadline is accepted and the service fills booking_end.
- An inactive course is not offered in the course select.
"""
EOF

cat << 'EOF' > app/forms/rubric.py
"""
FILE PURPOSE: WTForms for adding and editing a rubric criterion (ADM-07).
DEPENDS ON: flask_wtf, wtforms.
PROMPT FOR LLM IMPLEMENTATION:
1. RubricForm fields: criterion_name (DataRequired, Length 2-100, strip), description (Optional, Length max 500), weightage (DecimalField places 2, NumberRange 0-100), max_score (DecimalField places 2, NumberRange min 0.01), position (IntegerField Optional, default next position).
2. Labels: "Criterion", "Description", "Weightage (%)", "Maximum score".
3. No cross-criterion logic here (total-100 and uniqueness are service rules).
DEBUGGING:
# print(f"[DEBUG] RubricForm errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- weightage 100.01 and -1 are rejected; max_score 0 is rejected; 12.5 is accepted.
"""
EOF

cat << 'EOF' > app/forms/admin_actions.py
"""
FILE PURPOSE: Small Admin-only forms (assign examiner, change slot examiner, create examiner, temporary password, search).
DEPENDS ON: flask_wtf, wtforms, app/security/auth_helpers.py (validate_password_strength).
PROMPT FOR LLM IMPLEMENTATION:
1. AssignExaminerForm: examiner_id SelectField (coerce int) filled by the view with approved, active, not-yet-assigned examiners.
2. ChangeSlotExaminerForm: examiner_id SelectField filled by the view with approved, active examiners assigned to the slot's examination, excluding the current one.
3. ExaminerCreateForm: full_name, email (Email, lowercase), contact_phone Optional, department Optional, designation Optional, temporary_password (PasswordField with strength validation; label "Temporary password (the examiner must change it)").
4. TemporaryPasswordForm: new_password Optional (blank means "generate one"); when given, it must pass validate_password_strength.
5. AdminSearchForm (GET, csrf disabled): q (StringField, Length max 100), kind (SelectField student/examiner/examination/booking, default student).
6. All forms inherit from FlaskForm; none echo password values back.
DEBUGGING:
# print(f"[DEBUG] admin form {type(form).__name__} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- ExaminerCreateForm rejects a weak temporary password and an invalid email.
- AdminSearchForm rejects kind="invoice".
- ChangeSlotExaminerForm choices never include the slot's current examiner.
"""
EOF

# ======================= BLUEPRINT ROUTE MODULES =====================

cat << 'EOF' > app/blueprints/admin/dashboard.py
"""
FILE PURPOSE: ADM-01 Admin dashboard (six totals; charts are added in P8).
DEPENDS ON: app/blueprints/admin/__init__.py (admin_bp), app/security/decorators.py (admin_required), app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/dashboard (endpoint dashboard), decorated with admin_required. Call admin_service.dashboard_totals() and render admin/dashboard.html with totals plus the five most recent audit rows from audit_service.recent(5).
2. Also compute pending examiner approvals (from totals) for a highlighted call-to-action card linking to /admin/examiners?status=pending.
3. No other routes here. No queries in the route itself.
DEBUGGING:
# print(f"[DEBUG] dashboard totals={totals}")
OFFLINE DOCKER TEST CASES:
- Admin gets 200 with six stat cards labelled Courses, Examinations, Examiners, Students, Slots, Bookings and numbers equal to the fixtures.
- Student and examiner get 403; anonymous 302 to /login.
- Pending approval card shows the right number and links to the filtered examiner list.
"""
EOF

cat << 'EOF' > app/blueprints/admin/courses.py
"""
FILE PURPOSE: ADM-02 and ADM-03 course list, create, edit, delete.
DEPENDS ON: admin_bp, admin_required, app/forms/course.py, app/forms/common.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes (TDR 5.1): GET /admin/courses (list; filters q and status from query string; pagination), GET /admin/courses/new (empty form), POST /admin/courses (create), GET /admin/courses/<id>/edit, POST /admin/courses/<id>/update, POST /admin/courses/<id>/delete. Unknown id -> 404.
2. Each POST validates the form (or ConfirmForm for delete), calls catalog_service, flashes success ("Course created.") or the AppError message (category danger) and redirects (post/redirect/get). On form errors re-render the form with status 200.
3. Delete is offered as a danger button that opens a confirm modal (macro in macros/modals.html); the list shows an "Examinations" count column.
4. Pass actor_id=g.user.id to every service call. No rule logic in this file.
DEBUGGING:
# print(f"[DEBUG] courses {request.method} {request.path} user={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Create, edit and delete a course through the client; each step flashes the right message.
- Deleting a course with an examination flashes "Set it to inactive instead." and the course remains.
- Duplicate code shows "A course with this code already exists." on the form.
- Non-admin POSTs are rejected with 403 and change nothing.
"""
EOF

cat << 'EOF' > app/blueprints/admin/examinations.py
"""
FILE PURPOSE: ADM-04, ADM-05, ADM-06, ADM-08 examination list, create/edit, detail with timeline switches and the assigned-examiners panel.
DEPENDS ON: admin_bp, admin_required, app/forms/examination.py, app/forms/admin_actions.py, app/forms/common.py, app/services/catalog_service.py, app/services/windows.py, app/services/exam_status.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examinations (list; filters q, course_id, exam_type, status, show_deleted; pagination), GET /admin/examinations/new, POST /admin/examinations (create), GET /admin/examinations/<id> (detail), GET /admin/examinations/<id>/edit, POST /admin/examinations/<id>/update, POST /admin/examinations/<id>/delete, POST /admin/examinations/<id>/slot-creation/toggle, POST /admin/examinations/<id>/booking/toggle, POST /admin/examinations/<id>/examiners (assign), POST /admin/examinations/<id>/examiners/<examiner_id>/remove.
2. Detail page (ADM-06) loads: the examination with course, rubric summary (total weightage with an OK / needs-100 indicator), assigned examiners panel (ADM-08), slot count and booking counts, and windows.window_state(exam) to render the TWO timeline switches with their status text and the reason line. Call exam_status.refresh_status(exam) and commit before rendering so the badge is current (lazy status).
3. Toggle routes read the desired state from a hidden field "open" ("1" or "0") inside a ConfirmForm-style form, call catalog_service.toggle_*; errors (no_examiner_assigned, rubric_total_not_100) are flashed and the page redirects back to the detail view.
4. Assign form (AssignExaminerForm) is populated in the view with approved, active, not-yet-assigned examiners; if there are none show a muted message and a link to /admin/examiners?status=pending.
5. Datetimes shown with the localdt filter; forms pre-filled via populate_from.
6. Edit/delete errors are flashed with the AppError message; no rule logic in the route.
DEBUGGING:
# print(f"[DEBUG] exam {exam.id} status={exam.status} state={windows.window_state(exam)}")
OFFLINE DOCKER TEST CASES:
- Admin setup flow: create exam -> add rubric -> assign examiner -> open slot creation -> page shows "Open" with the dates; closing sets it back to "Closed".
- Opening booking with rubrics totalling 90 flashes the rubric_total_not_100 message and the switch stays closed.
- Detail page for a soft-deleted examination is reachable by Admin and shows a "Deleted" badge; the list hides it unless show_deleted is on.
- Remove-examiner refused while the examiner has a slot, with the examiner_has_slots message.
"""
EOF

cat << 'EOF' > app/blueprints/admin/rubrics.py
"""
FILE PURPOSE: ADM-07 rubric management for one examination.
DEPENDS ON: admin_bp, admin_required, app/forms/rubric.py, app/forms/common.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examinations/<id>/rubrics (list + add form + running total), POST /admin/examinations/<id>/rubrics (add), GET /admin/examinations/<id>/rubrics/<rid>/edit, POST /admin/examinations/<id>/rubrics/<rid>/update, POST /admin/examinations/<id>/rubrics/<rid>/delete.
2. The page shows a progress bar of the weightage total toward 100 (text "Total 90 of 100: add 10 more" or "Total 100: ready"), the sum of max scores with the informational warning when it differs from the examination's maximum marks, and a lock notice when rubric_locked applies (evaluations exist).
3. All rules come from catalog_service; flash AppError messages; a rubric id that does not belong to the examination in the URL is a 404.
DEBUGGING:
# print(f"[DEBUG] rubrics exam={exam_id} total={total} max_total={max_total}")
OFFLINE DOCKER TEST CASES:
- Adding criteria 60 and 40 shows "Total 100: ready"; adding another 10 is rejected with weightage_over_100.
- Duplicate criterion name shows the friendly message.
- After an evaluation exists the add/edit/delete forms are hidden and POSTs are refused.
- Mismatch between sum of max scores and max marks shows a warning but does not block anything.
"""
EOF

cat << 'EOF' > app/blueprints/admin/examiners.py
"""
FILE PURPOSE: ADM-09 and ADM-10 examiner list and detail, approval lifecycle, creating examiners and setting temporary passwords (also for students).
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py, app/forms/common.py, app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examiners (filters status = pending/approved/inactive/rejected and q; pagination), GET /admin/examiners/<id> (detail), GET /admin/examiners/new and POST /admin/examiners (create approved examiner), POST /admin/examiners/<id>/approve, /reject, /deactivate, /activate, and POST /admin/users/<id>/temporary-password (works for examiners and students).
2. Filter semantics: pending = approval_status pending; approved = approved and is_active; inactive = is_active False; rejected = approval_status rejected.
3. Detail shows profile data, assigned examinations, number of slots and of booked students (counts only), the audit history of that user, and the action buttons that apply to the current state (Approve/Reject only when pending; Deactivate when active; Activate when inactive).
4. The temporary password is shown ONCE: store it in flash with category warning and a "copy now" text ("Temporary password for <name>: <password>. It will not be shown again.") and never log it.
5. Error messages from AppError are flashed; all POSTs are CSRF-protected forms.
DEBUGGING:
# print(f"[DEBUG] examiners {request.method} {request.path} target={user_id}")
OFFLINE DOCKER TEST CASES:
- Pending examiner appears under ?status=pending; Approve moves them to approved and the audit history shows the action.
- Deactivate then next request by that examiner lands on /account-inactive; Activate restores access.
- Temp password flash appears once and the user is forced to /change-password on next login.
- POST approve on a student id returns the not_an_examiner message and changes nothing.
"""
EOF

cat << 'EOF' > app/blueprints/admin/students.py
"""
FILE PURPOSE: ADM-11 and ADM-12 student list and detail (read-only plus temporary password).
DEPENDS ON: admin_bp, admin_required, app/forms/common.py, app/forms/admin_actions.py, app/services/search_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/students (q filter by name, email, roll number or id; pagination) and GET /admin/students/<id> (detail, 404 if the user is not a student).
2. Detail shows profile data, all bookings of the student with status badges (any status), examination history and the audit history; empty states say "No bookings yet." (bookings appear from P5 on).
3. The temporary-password form posts to /admin/users/<id>/temporary-password (route lives in examiners.py).
4. Read-only otherwise: Admin cannot edit or delete students in this milestone.
DEBUGGING:
# print(f"[DEBUG] students list q={q!r} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Searching by roll number finds the student; paging works with 25 students.
- Detail of an examiner id returns 404.
- Detail lists cancelled and completed bookings too.
"""
EOF

cat << 'EOF' > app/blueprints/admin/slots.py
"""
FILE PURPOSE: ADM-13 slots overview and ADM-14 change slot examiner.
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py, app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/slots (filters examination_id, examiner_id, status, date_from, date_to; pagination; columns: examination, examiner, start, end, seats booked/capacity, status badge), GET /admin/slots/<id> (detail with the list of booked students), GET /admin/slots/<id>/examiner (change form) and POST /admin/slots/<id>/examiner (TDR 5.1).
2. Change form lists only eligible examiners (assigned, approved, active, not the current one). POST calls admin_service.change_slot_examiner; flash AppError messages (examiner_overlap, examiner_not_eligible, slot_not_changeable) or "Examiner changed."; redirect to the slot detail.
3. Reschedule and cancel controls are NOT here (ADM-16 and admin cancel arrive in P6).
DEBUGGING:
# print(f"[DEBUG] slot {slot.id} examiner {slot.examiner_id} -> {new_id}")
OFFLINE DOCKER TEST CASES:
- Filtering by status "full" shows only full slots; date filters use local dates converted to UTC.
- Changing to an unassigned examiner is impossible (not in the select) and a forged POST is refused with examiner_not_eligible.
- After a successful change the slot detail shows the new examiner and the audit history contains slot.examiner_change.
"""
EOF

cat << 'EOF' > app/blueprints/admin/bookings.py
"""
FILE PURPOSE: ADM-15 bookings overview (read-only in P3).
DEPENDS ON: admin_bp, admin_required, app/forms/common.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/bookings (filters status, examination_id, student q, slot_id, date range; pagination; columns: booking id, student, examination, slot time, examiner, status badge, booked_at, cancelled_at) and GET /admin/bookings/<id> (detail: all fields, evaluation status if any, audit history for the booking).
2. Read-only: the reschedule and cancel buttons are added in P6. Leave a visible but empty "Actions" area only when P6 lands; do not render placeholders now.
3. Use eager loading (joinedload/selectinload) for student, slot, examination to avoid N+1 queries; cap per_page at 100.
DEBUGGING:
# print(f"[DEBUG] bookings list filters={filters} total={page.total}")
OFFLINE DOCKER TEST CASES:
- With 30 fixtures the list pages correctly and the status filter returns only matching rows.
- Booking detail of a missing id returns 404.
- The list view issues a bounded number of SQL queries (assert with a query counter: fewer than 8 for 20 rows).
"""
EOF

cat << 'EOF' > app/blueprints/admin/search.py
"""
FILE PURPOSE: ADM-17 search across students, examiners, examinations and bookings.
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py (AdminSearchForm), app/services/search_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/search with query parameters q, kind, page. Validate with AdminSearchForm (GET). Invalid kind -> 400-style message on the page, never a 500.
2. Render admin/search_results.html with the result page, grouped display per kind (table columns differ), and links to the matching detail pages (student, examiner, examination, booking).
3. Empty q shows the instruction "Enter a name or ID to search."; no-result shows "No results for <q>" with q escaped by Jinja autoescape.
DEBUGGING:
# print(f"[DEBUG] search kind={kind} q={q!r}")
OFFLINE DOCKER TEST CASES:
- /admin/search?kind=student&q=ana lists matching students with links.
- kind=booking&q=<booking id> finds that booking first.
- q containing <script> is displayed escaped (the raw tag never appears in the HTML).
- Non-admin gets 403.
"""
EOF

cat << 'EOF' > app/blueprints/admin/history.py
"""
FILE PURPOSE: ADM-18 historical data view (PDR: Admin can view all historical data).
DEPENDS ON: admin_bp, admin_required, app/services/audit_service.py, app/models.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/history with query parameter tab = examinations | bookings | evaluations | audit (default examinations) plus filters (examination_id, student q, date range) and pagination.
2. Tabs: examinations (all, INCLUDING soft-deleted with a Deleted badge, with status and window dates); bookings (all statuses with booked_at, cancelled_at, cancelled_by, rescheduled_from); evaluations (status, total, examiner, submitted/published times); audit (action, entity, actor, time, details formatted from the JSON, newest first).
3. Read-only; no export in this milestone. Never display password hashes or temporary passwords (they are never stored in audit details anyway).
DEBUGGING:
# print(f"[DEBUG] history tab={tab} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Each of the four tabs returns 200 for Admin and 403 for other roles.
- A soft-deleted examination appears on the examinations tab with a Deleted badge.
- Audit tab shows the course.create row written during the same test.
- An unknown tab value falls back to examinations.
"""
EOF

# ============================= TEMPLATES =============================

cat << 'EOF' > app/templates/macros/status_badge.html
<!--
FILE PURPOSE: One macro that renders every status badge from Design Plan section 6 (text plus colour, never colour alone).
PROMPT FOR LLM IMPLEMENTATION:
1. Macro badge(domain, state) where domain is one of examination, slot, booking, account, evaluation, switch, generic and state is the stored lowercase value. Output span class "badge " plus the Bootstrap class from the Design Plan table: examination draft secondary, slot_creation primary, booking_open success, closed amber outline (class badge-outline-warning), completed dark; slot available success, full badge-full, cancelled secondary, completed dark; booking booked success, completed dark, cancelled secondary; account pending warning (dark text), approved success, rejected danger, inactive danger (label "Deactivated"); evaluation draft secondary, submitted primary, published success; switch open success, closed secondary.
2. Visible text is a human label ("Slot creation", "Booking open", "Full", "Deactivated"), looked up in a dict inside the macro; unknown states render the raw value in a secondary badge.
3. Also macro deleted_badge() rendering a dark "Deleted" badge.
DEBUGGING:
<!-- DEBUG: badge domain={{ domain }} state={{ state }} -->
OFFLINE DOCKER TEST CASES:
- badge("slot","full") output contains class badge-full and the text "Full".
- badge("examination","closed") contains badge-outline-warning.
- Every badge has visible text content (no empty spans).
-->
EOF

cat << 'EOF' > app/templates/macros/pagination.html
<!--
FILE PURPOSE: Bootstrap pager for db.paginate results, preserving all current query parameters.
PROMPT FOR LLM IMPLEMENTATION:
1. Macro pager(page, endpoint, **fixed_args): renders a nav aria-label="Pagination" with Previous, up to 5 numbered links around the current page (use page.iter_pages), Next, and a text "Page X of Y (N results)". The current page has aria-current="page"; disabled links use aria-disabled and tabindex -1.
2. Links are built with url_for(endpoint, **dict(request.args, page=n), **fixed_args) so filters survive paging.
3. Render nothing when page.pages <= 1.
DEBUGGING:
<!-- DEBUG: page {{ page.page }} of {{ page.pages }} total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- With 45 rows and per_page 20 the pager shows 3 pages and Page 2 links keep ?status=booked.
- A single page renders no pager at all.
-->
EOF

cat << 'EOF' > app/templates/macros/modals.html
<!--
FILE PURPOSE: Reusable confirm modal for destructive or irreversible actions (Design Plan: danger buttons always confirm).
PROMPT FOR LLM IMPLEMENTATION:
1. Macro confirm_action(modal_id, button_label, title, message, action_url, form, button_class="btn btn-outline-danger btn-sm", hidden=None): renders a trigger button (data-bs-toggle modal) and a Bootstrap modal with aria-labelledby, a body message, a Cancel button and a POST form to action_url containing form.hidden_tag() (CSRF) and any hidden name/value pairs from the hidden dict, plus a confirm submit button.
2. The modal works with the vendored Bootstrap bundle only (no custom JS); focus handling is Bootstrap's default trap.
3. modal_id must be unique per row: callers pass something like "delete-course-" ~ course.id.
DEBUGGING:
<!-- DEBUG: modal {{ modal_id }} -> {{ action_url }} -->
OFFLINE DOCKER TEST CASES:
- Rendered HTML contains a form with method post, a csrf_token input and the given action URL.
- Two modals in one page have different ids.
-->
EOF

cat << 'EOF' > app/templates/admin/base_admin.html
<!--
FILE PURPOSE: Admin shell: left sidebar plus top bar (Design Plan section 2). Extends base.html by overriding the site_nav and layout blocks introduced in the P3 update.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html. Override block site_nav with a slim top bar showing the brand, the Admin's name and a Logout POST form with csrf.
2. Override block layout with .admin-shell: an aside.admin-sidebar containing a nav aria-label="Admin" with groups and links: Overview (Dashboard), Courses, Examinations, Examiners, Students, Slots, Bookings, Search, History. Mark the current item with class active and aria-current="page" using request.endpoint. Then main#main-content.admin-content with the _flash.html include, a page header block (h1 from block page_title plus optional actions block) and block content.
3. Do NOT add Tests, Proctoring or Payments entries (Tier 3). Do not add Evaluations (P6 adds it).
4. On screens under 992px the sidebar is a normal collapsed block above content (off-canvas arrives in P10).
5. Blocks provided to children: title, page_title, page_actions, content.
DEBUGGING:
<!-- DEBUG: admin shell endpoint={{ request.endpoint }} -->
OFFLINE DOCKER TEST CASES:
- The sidebar has exactly the 9 links above and the current page link has aria-current.
- Page has one h1 (from page_title) and the skip link target exists.
-->
EOF

cat << 'EOF' > app/templates/admin/dashboard.html
<!--
FILE PURPOSE: ADM-01 dashboard with six total cards.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend admin/base_admin.html; page_title "Dashboard". A responsive grid (3 columns on lg, 2 on md, 1 on xs) of six .stat-card elements: Courses, Examinations, Examiners (sub-line "N pending approval" as a link when N > 0), Students, Slots, Bookings (sub-line "N cancelled"). Each card is a link to the matching list page.
2. Below: "Recent activity" table of the last five audit rows (time via localdt, actor name or "System", action, entity).
3. Reserve an empty div id="charts-widget" for P8 (comment only, no content).
DEBUGGING:
<!-- DEBUG: totals {{ totals }} -->
OFFLINE DOCKER TEST CASES:
- Six cards present with the right numbers; the pending-approval link points to /admin/examiners?status=pending.
-->
EOF

cat << 'EOF' > app/templates/admin/courses_list.html
<!--
FILE PURPOSE: ADM-02 courses table.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Courses"; page_actions: primary button "New course". Filter bar (GET): search q, status select, Filter button.
2. Table table-hover align-middle with th scope=col: Code, Name, Status badge, Examinations (count), Actions (Edit link, Delete via confirm_action modal). Use macros pager and badge. Empty state "No courses yet." with a New course button.
3. Delete modal message explains that courses with examinations cannot be deleted.
DEBUGGING:
<!-- DEBUG: courses total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- 25 courses show a pager; Delete opens a modal whose form posts to /admin/courses/<id>/delete.
-->
EOF

cat << 'EOF' > app/templates/admin/course_form.html
<!--
FILE PURPOSE: ADM-03 create/edit course form.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "New course" or "Edit course" (variable). Form posts to /admin/courses (create) or /admin/courses/<id>/update (edit), csrf included, fields via render_field: Course code, Course name, Description, Status. Buttons: Save (primary) and Cancel (link to the list).
DEBUGGING:
<!-- DEBUG: course form errors {{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- Editing pre-fills all fields; a validation error keeps the user's input and shows the message beside the field.
-->
EOF

cat << 'EOF' > app/templates/admin/examinations_list.html
<!--
FILE PURPOSE: ADM-04 examinations table with filters.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Examinations"; page_actions "New examination". Filter bar: q, course select, type select, status select, "Show deleted" checkbox.
2. Table: Name (link to detail), Course code, Type, Status badge (examination domain), Booking window (localdt start - end), Slot creation and Booking switch badges (switch domain, effective state from window_state), Actions (Edit, Delete via modal). Deleted rows show the Deleted badge and no actions except View.
3. Cards instead of table rows under 576px are handled in P10; for now keep the table inside .table-responsive.
DEBUGGING:
<!-- DEBUG: exams total {{ page.total }} filters {{ filters }} -->
OFFLINE DOCKER TEST CASES:
- Default list hides deleted examinations; show_deleted=1 reveals them with the badge.
- Status filter "booking_open" returns only matching rows.
-->
EOF

cat << 'EOF' > app/templates/admin/examination_form.html
<!--
FILE PURPOSE: ADM-05 create/edit examination form.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html. Sections (fieldsets with legends): Basics (course, name, description, type), Scoring (duration in minutes, maximum marks), Slot creation window (start, end), Booking window (start, end, cancellation deadline with help text "Defaults to the booking end").
2. Date fields are input type datetime-local with the HTML5 required attribute and a help text showing the timezone from config ("Times are in Asia/Kolkata").
3. Buttons Save and Cancel; the form posts to /admin/examinations (create) or /admin/examinations/<id>/update (edit). Cross-field errors appear in an alert at the top of the form AND beside the fields.
DEBUGGING:
<!-- DEBUG: exam form errors {{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- Each date input has a label and type datetime-local; submitting an invalid window shows the combined message.
- Editing shows the stored times converted back to local time.
-->
EOF

cat << 'EOF' > app/templates/admin/examination_detail.html
<!--
FILE PURPOSE: ADM-06 examination detail with timeline controls and ADM-08 assigned-examiners panel.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title is the examination name with the status badge; page_actions Edit and Delete (modal).
2. Summary card: course, type, duration, maximum marks, the five dates (localdt).
3. Timeline panel with TWO rows (.timeline-switch): "Slot creation" and "Student booking". Each shows the effective state badge (switch domain), the dates, the reason line from window_state (for example "Booking opens on 12 Dec, 10:00") and a single toggle button inside a POST form (hidden input open = 1 or 0; label "Open slot creation" / "Close slot creation", "Open booking" / "Close booking"). Buttons that are certain to fail (no examiner assigned, rubric total not 100) stay enabled but a muted hint line explains the requirement.
4. Rubric summary card: total weightage with ready/needs-100 indicator and a link to /admin/examinations/<id>/rubrics.
5. Assigned examiners panel: table of examiners (name, email, number of own slots, Remove via modal) and the assign form (select + Assign button); empty state text.
6. Counters: slots, active bookings, evaluations submitted (counts only).
DEBUGGING:
<!-- DEBUG: window_state {{ window_state }} -->
OFFLINE DOCKER TEST CASES:
- The two toggle forms post to the slot-creation and booking toggle URLs with a csrf_token.
- The reason line mentions the date when the window has not started.
- With no assigned examiner the examiners panel shows its empty state.
-->
EOF

cat << 'EOF' > app/templates/admin/rubrics.html
<!--
FILE PURPOSE: ADM-07 rubric management page.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Rubric: <examination name>". Progress bar toward 100 percent weightage with the text from the view and an aria-valuenow; separate muted line comparing the sum of max scores with the examination's maximum marks (warning style when different).
2. Table of criteria: Order, Criterion, Description, Weightage (%), Max score, Actions (Edit link, Delete modal). Add-criterion form below (fields via render_field). When rubric_locked show an info alert and hide forms and action buttons.
DEBUGGING:
<!-- DEBUG: rubric total {{ total }} locked {{ locked }} -->
OFFLINE DOCKER TEST CASES:
- Total 100 shows the ready state; total 90 shows "add 10 more".
- Locked state renders no form elements.
-->
EOF

cat << 'EOF' > app/templates/admin/examiners_list.html
<!--
FILE PURPOSE: ADM-09 examiners list with filters.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Examiners"; page_actions "Add examiner". Filter bar: q and status (All, Pending, Approved, Inactive, Rejected) shown as pill links with counts.
2. Table: Name (link), Email, Department, Account badge (account domain), Registered date, Quick actions (Approve for pending). Empty state per filter.
DEBUGGING:
<!-- DEBUG: examiner filter {{ status }} total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- The pending pill shows the pending count and the list shows only pending rows when selected.
- Approve button posts to /admin/examiners/<id>/approve with csrf.
-->
EOF

cat << 'EOF' > app/templates/admin/examiner_detail.html
<!--
FILE PURPOSE: ADM-10 examiner detail (also reused for the same layout of user actions).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title examiner name with the account badge. Profile card (email, phone, department, designation, registered, last login).
2. Action buttons by state: Approve and Reject (pending), Deactivate (active, confirm modal), Activate (inactive). A separate card "Temporary password" with the TemporaryPasswordForm and text "Leave blank to generate one. The user must change it at next login."
3. Cards: assigned examinations, counts of slots and booked students, and the audit history list for this user.
DEBUGGING:
<!-- DEBUG: examiner {{ user.id }} approval={{ user.approval_status }} active={{ user.is_active }} -->
OFFLINE DOCKER TEST CASES:
- Pending examiner shows Approve and Reject only; active shows Deactivate only.
- The temp-password form posts to /admin/users/<id>/temporary-password.
-->
EOF

cat << 'EOF' > app/templates/admin/examiner_form.html
<!--
FILE PURPOSE: Form for the Admin to add an examiner directly (approved, forced password change).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Add examiner"; ExaminerCreateForm fields via render_field; help text on the temporary password; Save and Cancel.
DEBUGGING:
<!-- DEBUG: examiner create errors {{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- Duplicate email shows the email_taken message; success redirects to the examiner detail.
-->
EOF

cat << 'EOF' > app/templates/admin/students_list.html
<!--
FILE PURPOSE: ADM-11 students list.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Students"; search box q (name, email, roll number, ID). Table: ID, Name (link), Email, Roll number, Program, Registered; pager; empty state.
DEBUGGING:
<!-- DEBUG: students total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Student rows link to /admin/students/<id>; paging keeps the q parameter.
-->
EOF

cat << 'EOF' > app/templates/admin/student_detail.html
<!--
FILE PURPOSE: ADM-12 student detail with bookings and history.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; profile card; table "Bookings and history" (examination, slot time, examiner, status badge, booked, cancelled); evaluation summary column only when published; audit history card; Temporary password card as in the examiner detail.
2. Empty state "No bookings yet."
DEBUGGING:
<!-- DEBUG: student {{ user.id }} bookings {{ bookings|length }} -->
OFFLINE DOCKER TEST CASES:
- Cancelled and completed bookings are listed with their badges.
-->
EOF

cat << 'EOF' > app/templates/admin/slots_list.html
<!--
FILE PURPOSE: ADM-13 slots list.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Slots"; filter bar (examination, examiner, status, from date, to date). Table: Examination, Examiner, Start, End, Seats (booked / capacity with a small progress bar and text), Status badge (slot domain), Actions (View, Change examiner link when status is available or full). Pager and empty state.
DEBUGGING:
<!-- DEBUG: slots total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- A full slot shows "5 / 5" with the Full badge; the Change examiner link is hidden for cancelled slots.
-->
EOF

cat << 'EOF' > app/templates/admin/slot_detail.html
<!--
FILE PURPOSE: Slot detail (ADM-13 detail) listing booked students.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; summary (examination, examiner, time, capacity, status); table of bookings in this slot (student link, booking status badge, booked_at); link Change examiner; audit history list.
DEBUGGING:
<!-- DEBUG: slot {{ slot.id }} bookings {{ slot.bookings|length }} -->
OFFLINE DOCKER TEST CASES:
- Detail shows all bookings including cancelled ones.
-->
EOF

cat << 'EOF' > app/templates/admin/slot_change_examiner.html
<!--
FILE PURPOSE: ADM-14 change slot examiner.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; summary of the slot and the current examiner; ChangeSlotExaminerForm (select of eligible examiners) with POST to /admin/slots/<id>/examiner; note "Existing bookings stay with this slot." When there are no eligible examiners show a message and a link to the examination's assigned-examiners panel.
DEBUGGING:
<!-- DEBUG: eligible examiners {{ form.examiner_id.choices }} -->
OFFLINE DOCKER TEST CASES:
- The current examiner is not in the options; the empty state appears when none are eligible.
-->
EOF

cat << 'EOF' > app/templates/admin/bookings_list.html
<!--
FILE PURPOSE: ADM-15 bookings list (read-only in P3).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Bookings"; filter bar (status, examination, student q, slot id, date range). Table: ID, Student (link), Examination, Slot time, Examiner, Status badge, Booked, Cancelled, View link. Pager; empty state "No bookings match these filters."
DEBUGGING:
<!-- DEBUG: bookings total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Status filter and pager work together (page 2 keeps the filter).
-->
EOF

cat << 'EOF' > app/templates/admin/booking_detail.html
<!--
FILE PURPOSE: Booking detail for the Admin (read-only in P3; P6 adds reschedule and cancel actions).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; summary card (student link, examination, slot, examiner, status badge, booked, cancelled and by whom, rescheduled-from slot); evaluation summary when present (status badge, total, remarks only for Admin); audit history list for entity booking.
2. Wrap the actions area in a Jinja block named booking_actions that is empty in P3, so the P6 update only fills the block.
DEBUGGING:
<!-- DEBUG: booking {{ booking.id }} status {{ booking.status }} -->
OFFLINE DOCKER TEST CASES:
- All booking fields render; the page has no action buttons in P3.
-->
EOF

cat << 'EOF' > app/templates/admin/search_results.html
<!--
FILE PURPOSE: ADM-17 search results.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Search". A GET form at the top (AdminSearchForm: kind select + q input + Search button, no csrf).
2. Results table with columns depending on kind (student: ID, name, email, roll; examiner: ID, name, email, department, account badge; examination: ID, name, course, status badge, Deleted badge when applicable; booking: ID, student, examination, slot time, status badge). Every row links to the detail page. Pager preserves q and kind.
3. States: empty q instruction, no-results message with escaped q, hint text "Tip: enter a number to search by ID".
DEBUGGING:
<!-- DEBUG: search kind {{ kind }} q {{ q }} total {{ page.total if page else 0 }} -->
OFFLINE DOCKER TEST CASES:
- Each kind renders the right headers; the q value is escaped in the input and in messages.
-->
EOF

cat << 'EOF' > app/templates/admin/history.html
<!--
FILE PURPOSE: ADM-18 historical data view with four tabs.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "History". Bootstrap nav-tabs built from links (?tab=...) with aria-current on the active tab; per-tab table as described in app/blueprints/admin/history.py; filter bar and pager preserving tab and filters.
2. Audit tab formats the details JSON as short "key: value" pairs, never raw JSON dumps longer than 200 characters.
DEBUGGING:
<!-- DEBUG: history tab {{ tab }} total {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Switching tabs keeps filters; all four tabs render with an empty database (empty states only).
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_windows.py
"""
FILE PURPOSE: Boundary tests for the time-window helper (risk R-3).
DEPENDS ON: app/services/windows.py, tests/conftest.py (freeze_now, make_examination).
PROMPT FOR LLM IMPLEMENTATION:
1. Parametrised boundary tests for is_booking_open and is_slot_creation_open: one second before start, exactly at start, mid window, exactly at end, one second after end, each with the switch on and off (switch off is always closed).
2. Tests: test_can_student_cancel_until_deadline_inclusive, test_slots_editable_only_before_booking_start (exactly at booking_start is NOT editable), test_soft_deleted_exam_never_open, test_assert_helpers_raise_window_error_with_codes (booking_closed, slot_creation_closed, slot_edit_locked, cancel_deadline_passed), test_window_state_reasons (switch off / not started / ended texts), test_from_local_input_kolkata_to_utc, test_to_input_value_roundtrip, test_bad_local_input_raises_value_error, test_now_utc_is_naive, test_no_module_imports_now_utc_by_name (walk app/ source files and assert none contains "import now_utc").
3. Use freeze_now for all clock-dependent cases; never call datetime.now().
DEBUGGING:
# print(f"[DEBUG] boundary case now={now} expected={expected} got={got}")
OFFLINE DOCKER TEST CASES:
- 30+ parametrised cases pass offline; making the end boundary exclusive makes at least one case fail.
"""
EOF

cat << 'EOF' > tests/unit/test_exam_status.py
"""
FILE PURPOSE: Tests for compute_status / refresh_status.
DEPENDS ON: app/services/exam_status.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_draft_before_any_window, test_slot_creation_when_open, test_booking_open_when_open, test_closed_after_booking_end_without_slots, test_completed_after_all_slots_past_and_evaluated, test_closed_when_one_booking_unevaluated, test_closed_when_a_slot_is_in_the_future, test_cancelled_slots_ignored, test_refresh_status_writes_one_audit_row_and_is_idempotent, test_deleted_exam_status_untouched, test_booking_open_wins_over_slot_creation_if_both_flags_on.
2. Build data with the conftest factories and freeze_now; no sleeping.
DEBUGGING:
# print(f"[DEBUG] status case {name}: expected={expected} got={got}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_audit_search_slot_rules.py
"""
FILE PURPOSE: Unit tests for audit_service, search_service and slot_rules.
DEPENDS ON: app/services/audit_service.py, search_service.py, slot_rules.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. audit: test_log_action_not_committed_until_caller_commits, test_details_json_roundtrip_with_datetime, test_ip_stored_in_request_context_none_outside, test_history_for_newest_first.
2. search: test_student_search_case_insensitive, test_search_by_numeric_id_first, test_like_wildcards_escaped, test_invalid_kind_raises, test_empty_query_returns_hint, test_booking_search_by_student_email, test_examination_search_includes_deleted_flagged, test_search_never_returns_other_roles_in_student_kind.
3. slot_rules: test_overlap_detected, test_back_to_back_allowed, test_cancelled_slot_ignored, test_exclude_slot_id, test_overlap_across_examinations_same_examiner, test_different_examiners_never_overlap.
DEBUGGING:
# print(f"[DEBUG] result ids={[r.id for r in result.items]}")
OFFLINE DOCKER TEST CASES:
- 18 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_catalog_and_admin_rules.py
"""
FILE PURPOSE: Service-level tests for catalog_service and admin_service rules (no HTTP).
DEPENDS ON: app/services/catalog_service.py, admin_service.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Catalog tests: test_course_code_uppercased_and_unique, test_delete_course_blocked_when_in_use, test_exam_window_validation_messages, test_exam_cancellation_deadline_defaults, test_max_marks_cannot_drop_below_existing_evaluation, test_course_locked_after_slots, test_delete_exam_soft_and_switches_off, test_delete_exam_blocked_with_active_booking, test_toggle_slot_creation_needs_approved_examiner, test_toggle_booking_needs_rubric_total_100, test_closing_switches_has_no_preconditions, test_rubric_over_100_rejected, test_rubric_duplicate_name_rejected, test_rubric_locked_after_evaluation, test_assign_only_approved_active_examiners, test_assign_duplicate_rejected, test_unassign_blocked_with_slot.
2. Admin tests: test_approve_reject_deactivate_activate_cycle, test_cannot_deactivate_self, test_not_an_examiner_error, test_create_examiner_forces_password_change, test_temp_password_generated_and_hash_verifies, test_temp_password_not_in_audit_details, test_temp_password_refused_for_admin_target, test_change_slot_examiner_rules (not assigned, overlap, cancelled slot, same examiner, success), test_dashboard_totals_counts.
3. Every error test asserts the stable error code, not the message text.
DEBUGGING:
# print(f"[DEBUG] AppError code={exc_info.value.code}")
OFFLINE DOCKER TEST CASES:
- 26 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_admin_access_control.py
"""
FILE PURPOSE: Proves EVERY /admin route is closed to everyone but a ready Admin (risk R-4).
DEPENDS ON: tests/conftest.py, app/__init__.py (url_map).
PROMPT FOR LLM IMPLEMENTATION:
1. Build the list of admin URLs by iterating app.url_map.iter_rules() for rules starting with /admin, filling path variables with the id of a real fixture row (use a converter map: <int:id> -> 1). Keep GET and POST separate.
2. Parametrised tests: anonymous -> 302 to /login for every URL and method; student -> 403; approved examiner -> 403; pending examiner -> 403 (role mismatch comes before the pending redirect); admin with must_change_password True -> 302 to /change-password; admin ready -> never 403 or 500 (200/302/404 allowed for POST with empty data).
3. test_admin_post_without_csrf_rejected (CSRF enabled app) for three representative POST routes.
4. test_no_admin_route_missing_decorator: fail if any /admin rule's view function is not wrapped (check the wrapped marker set by the decorators).
DEBUGGING:
# print(f"[DEBUG] {method} {url} as {role} -> {response.status_code}")
OFFLINE DOCKER TEST CASES:
- The parametrised matrix covers every admin rule found at collection time; adding a new admin route automatically adds cases.
"""
EOF

cat << 'EOF' > tests/integration/test_admin_courses_exams_rubrics.py
"""
FILE PURPOSE: HTTP-level tests for ADM-01 to ADM-08 CRUD screens.
DEPENDS ON: tests/conftest.py (admin_client, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. Dashboard: test_dashboard_six_totals_values, test_dashboard_pending_link.
2. Courses: test_course_create_edit_delete_flow, test_course_duplicate_code_message, test_course_delete_blocked_message, test_course_list_filters_and_paging (25 rows).
3. Examinations: test_exam_create_converts_local_time_to_utc, test_exam_create_invalid_window_shows_errors, test_exam_edit_prefills_local_times, test_exam_delete_soft_hides_from_list, test_exam_show_deleted_flag, test_exam_detail_shows_window_reasons, test_toggle_slot_creation_flow, test_toggle_booking_blocked_without_rubric_100_flash, test_assign_and_remove_examiner_flow.
4. Rubrics: test_rubric_add_progress_text, test_rubric_over_100_flash, test_rubric_locked_hides_forms, test_rubric_foreign_id_404.
5. Every test uses admin_client and asserts both the flash text and the database state.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 22 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_admin_examiners_students_slots.py
"""
FILE PURPOSE: HTTP-level tests for examiner/student management, slots overview, change slot examiner, bookings list.
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Examiners: test_pending_filter_and_approve, test_reject_then_login_shows_not_approved, test_deactivate_activate_effect_on_login, test_add_examiner_then_forced_password_change, test_temp_password_flash_once, test_approve_student_id_rejected.
2. Students: test_students_search_by_roll_number, test_student_detail_lists_all_booking_statuses, test_examiner_id_on_student_detail_404.
3. Slots: test_slots_filters, test_change_examiner_success_keeps_bookings, test_change_examiner_overlap_flash, test_change_examiner_forged_post_refused.
4. Bookings: test_bookings_filters_and_paging, test_bookings_list_query_count_bounded, test_booking_detail_no_action_buttons_in_p3, test_booking_detail_404.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')}")
OFFLINE DOCKER TEST CASES:
- 17 tests pass offline; the query-count test fails if eager loading is removed.
"""
EOF

cat << 'EOF' > tests/integration/test_admin_search_history_flow.py
"""
FILE PURPOSE: Search, history tabs and the full Admin setup flow of Design Plan 4.4 (milestone acceptance).
DEPENDS ON: tests/conftest.py, freeze_now.
PROMPT FOR LLM IMPLEMENTATION:
1. Search/history: test_search_each_kind_renders, test_search_xss_escaped, test_search_invalid_kind_message, test_history_tabs_render_empty, test_history_shows_soft_deleted_exam, test_history_audit_tab_shows_course_create.
2. test_admin_setup_flow_end_to_end (acceptance): through the HTTP client only - create course; create examination with windows around the frozen now; add rubric criteria 60 and 40; register and approve an examiner through the UI routes; assign the examiner; open slot creation (status shows slot_creation); close it; open booking (status booking_open); close booking; assert each step's flash message, the final switches state and that the audit tab lists at least 8 rows in order.
3. test_setup_flow_blocked_steps: opening slot creation before assigning, opening booking before the rubric total is 100, each with the exact flash.
DEBUGGING:
# print(f"[DEBUG] flow step={step} status={response.status_code}")
OFFLINE DOCKER TEST CASES:
- The end-to-end test passes offline in under 5 seconds and leaves a consistent database (rubric total 100, switches closed).
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P3 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P3_update_existing_files.md section by section (app/__init__.py, admin/__init__.py, base.html, app.css, conftest.py, test_rbac_access.py) with the CURRENT files."
echo "2. Run 'docker compose --profile test run --rm test' (or 'make test-core'), then 'flask --app app run --debug' and walk the setup flow in the browser as Admin."
echo "3. Run 'git add . && git commit -m \"wip: P3 admin dashboard\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p3-admin-dashboard-exams && git commit -m \"Milestone-3 EMP-Admin-Dashboard-Exams\" && git tag p3-done && git push origin main --tags'."
echo "5. Decisions to confirm (not in the PDR): booking needs rubric total 100; slot creation needs an approved assigned examiner; Admin can add and reject examiners; reschedule and admin cancel are in P6."
echo "6. Execute P4.sh"
echo "====================================================="
