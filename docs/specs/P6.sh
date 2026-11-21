#!/usr/bin/env bash
# =====================================================================
# P6.sh - Milestone M6: Booking History & Evaluation Tracking (Tier 1)
# Course commit message : Milestone-6 EMP-Booking-History-Tracking
# Branch                : phase/p6-booking-history-tracking
# Depends on            : P5 (tag p5-done)
# Screens               : ADM-16 (reschedule), admin cancel/publish actions,
#                         admin evaluations tracking, history timelines
# This is the LAST Tier 1 phase: when it is merged and green, Gate A can be
# verified with scripts/verify_gate_a.sh and the tag tier1-complete created.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P6_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P6"
BRANCH="phase/p6-booking-history-tracking"
PREV_TAG="p5-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P5 first."; exit 1; }
[ -f app/services/booking_engine.py ] || { echo "ERROR: app/services/booking_engine.py missing (P5 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P6 needs)
# ---------------------------------------------------------------------
mkdir -p app/services app/forms app/blueprints/admin
mkdir -p app/templates/admin
mkdir -p scripts docs docs/seed_updates
mkdir -p tests/unit tests/integration tests/e2e

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P6_update_existing_files.md
<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P6 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file. Apply the sections in order: sections 1 and 2 are the engine hardening that the concurrency test depends on.

SECTION 1: app/extensions.py (SQLite write lock, TDR 3.2)
1. Inside register_sqlite_pragmas (keep it idempotent and sqlite-only), ADD BOTH halves together: in the existing Engine "connect" listener set dbapi_connection.isolation_level = None BEFORE the pragmas, and attach ONE new listener on sqlalchemy.engine.Engine for the "begin" event that executes conn.exec_driver_sql("BEGIN IMMEDIATE") when the dialect is sqlite. Setting only one half would silently break transactions, which is why P1 left both out.
2. Effect: every SQLAlchemy transaction now takes SQLite's write lock at its first statement, so check-then-write sequences in the booking engine are atomic. Document the trade-off in a comment: reads also take the lock, concurrent requests queue behind it, and PRAGMA busy_timeout = 5000 makes them wait instead of failing; keep transactions short and rely on Flask-SQLAlchemy removing the session at the end of each request.
3. Add a module-level helper write_lock_enabled() returning True when the begin listener is attached (used by a test).
4. Everything else (naming convention, csrf, TimestampMixin) is unchanged. All P1-P5 tests must still pass.

SECTION 2: app/services/booking_engine.py (hardening + new operations)
1. Do not change the behaviour or messages of book_slot and cancel_booking. Add to the module docstring a short explanation of why BEGIN IMMEDIATE plus the guarded UPDATE statements make the engine race-free, and make every public function start by refreshing the slot rows it uses with db.session.refresh (or populate_existing) so values loaded earlier in the same request are never stale.
2. reschedule_booking(booking_id, new_slot_id, actor_id, now=None) -> Booking (Admin only; the caller route enforces the role, the engine additionally checks that actor is an active admin: "not_an_admin"). One transaction. Checks in order: booking exists ("booking_not_found"); status is "booked" ("booking_not_reschedulable"); the booking has NO evaluation of any status ("booking_has_evaluation"); target slot exists ("slot_not_found"); target slot is not the current slot ("same_slot"); target slot belongs to the same examination ("different_examination"); target slot status "full" -> SLOT_FULL, "cancelled" or "completed" -> SLOT_NOT_AVAILABLE; target start_at is in the future (SLOT_NOT_AVAILABLE). Admin override: the booking window and the student's cancellation deadline are NOT checked. Then: claim a seat on the target with the same guarded UPDATE as book_slot; set status "full" there when it reaches capacity; release the seat on the old slot with the guarded decrement and re-open it when it was "full"; set booking.slot_id = new slot and booking.rescheduled_from_slot_id = old slot; audit BOOKING_RESCHEDULE {from_slot, to_slot, by}; commit. Booking id, booked_at and evaluation links stay unchanged.
3. admin_cancel_booking(booking_id, actor_id, reason, now=None) -> Booking: Admin only ("not_an_admin"); booking status must be "booked" ("booking_not_cancellable"); refuse when an evaluation with status submitted or published exists ("booking_has_evaluation"; a draft evaluation is allowed); reason is required, 3 to 200 characters ("reason_required"); NO deadline check. Reuse the _release_seat helper with cancelled_by = actor; audit BOOKING_ADMIN_CANCEL with {"reason": reason}; commit; after the commit run hooks.run_post_cancel with actor_id set.
4. cancel_slot(slot_id, actor_id, reason, now=None) -> int (number of bookings cancelled): actor is the owning examiner (approved, active, slot.examiner_id == actor) or an admin; otherwise "slot_not_found". Slot status must be available or full ("slot_not_cancellable"); slot.start_at must be in the future ("slot_started"); no booking of this slot may have an evaluation with status submitted or published ("slot_has_evaluations"); reason 3 to 200 characters. One transaction: for every booking with status "booked" call _release_seat (cancelled_by = actor), then set slot.status "cancelled" and booked_count 0 (assert it reached 0); audit SLOT_CANCEL {"bookings_cancelled": n, "reason": reason}; commit; after the commit run post-cancel hooks once per cancelled booking.
5. change_examiner(slot_id, new_examiner_id, actor_id) -> ExaminationSlot: the same rules as admin_service.change_slot_examiner from P3 (slot status available or full; new examiner assigned to the examination, approved and active; different from the current one; slot_rules.has_overlap False) but executed inside the write-locked transaction. Audit SLOT_EXAMINER_CHANGE {"from": old, "to": new}. Existing bookings and evaluations stay untouched.
6. Every function raises BookingError (or AppError with a stable code), never flashes, never uses the request. Keep each function under about 60 lines by sharing helpers (_claim_seat, _release_seat, _load_slot_locked).

SECTION 3: app/services/admin_service.py
1. Replace the body of change_slot_examiner(actor_id, slot_id, new_examiner_id) with a one-line delegation to booking_engine.change_examiner(slot_id, new_examiner_id, actor_id) and keep the signature, docstring and the P3 tests green. Remove the now-duplicated validation code.

SECTION 4: app/services/exam_status.py
1. Implement sync_all(now=None) -> dict (it raised NotImplementedError in P3). For every non-deleted examination, in its own transaction: (a) mark slots with end_at < now and status available or full as "completed"; (b) mark bookings with status "booked" in those slots as "completed"; (c) call refresh_status. Write ONE audit row per examination that changed anything (actor NULL, action SYSTEM_STATUS_SYNC, details {"slots_completed": n, "bookings_completed": m, "status": new}). Return a summary {"examinations": n, "slots_completed": n, "bookings_completed": n, "status_changes": n}. The function is idempotent: a second run with the same clock changes nothing and writes no audit rows. Never touch cancelled slots or bookings.

SECTION 5: app/services/evaluation_service.py
1. Add admin_publish(actor_id, evaluation_id): Admin publishes a SUBMITTED evaluation (status submitted -> published, published_at = now); draft -> "evaluation_not_submitted"; already published -> "evaluation_locked"; audit EVALUATION_ADMIN_PUBLISH. Admin cannot edit scores or remarks.
2. Add list_evaluation_tracking(status=None, examiner_id=None, examination_id=None, q=None, page=1): paginated rows for EVERY evaluable booking (status booked or completed, slot not cancelled) with a derived tracking state: "not_started" (no evaluation), "draft", "submitted", "published"; filters by that state, examiner (slot examiner), examination and student name. Add pending_by_examiner() returning a list of (examiner, count of bookings not yet submitted) for the summary strip.

SECTION 6: app/services/audit_service.py
1. Add constants: BOOKING_RESCHEDULE = "booking.reschedule", BOOKING_ADMIN_CANCEL = "booking.admin_cancel", SLOT_CANCEL = "slot.cancel", EVALUATION_ADMIN_PUBLISH = "evaluation.admin_publish", SYSTEM_STATUS_SYNC = "system.status_sync", SYSTEM_PURGE = "system.purge".

SECTION 7: app/cli.py
1. Add a click group "jobs" (flask --app app jobs <name>) registered by register_cli with two commands: sync-exam-status (calls exam_status.sync_all and prints the summary) and purge-soft-deleted (option --days, default 90; calls maintenance.purge_soft_deleted and prints the number of examinations purged). Both exit 0 on success and non-zero with a clear message on errors; both are safe to run repeatedly and from cron.

SECTION 8: app/blueprints/admin/__init__.py
1. Add imports of the two new route modules booking_actions and evaluations next to the existing ones (with "# noqa: E402,F401").

SECTION 9: app/blueprints/admin/bookings.py and app/templates/admin/booking_detail.html
1. In the booking detail route additionally load history_service.booking_timeline(booking_id, viewer_role="admin", viewer_id=g.user.id) and pass it to the template.
2. Template: fill the Jinja block booking_actions (empty since P3) with: "Reschedule" button (link to /admin/bookings/<id>/reschedule) and "Cancel booking" (confirm modal with a reason textarea posting to /admin/bookings/<id>/cancel), shown only for status booked; "Publish evaluation" button (POST /admin/evaluations/<evaluation_id>/publish) when the evaluation is submitted. Render the timeline as an ordered list under "History".

SECTION 10: app/templates/admin/base_admin.html and tests
1. Add the sidebar link "Evaluations" (endpoint admin.evaluations_list) between Bookings and Search; the sidebar now has 10 links.
2. Update the P3 sidebar test expectation from 9 to 10 links.

SECTION 11: app/blueprints/examiner/slots.py, templates/examiner/slots_list.html, templates/examiner/slot_students.html
1. Add POST /examiner/slots/<id>/cancel (ConfirmForm plus a reason field): slot via slot_service.get_owned_slot (404 otherwise), call booking_engine.cancel_slot(slot_id, g.user.id, reason); flash "Slot cancelled. N bookings were cancelled." or the error message; redirect to /examiner/slots.
2. In both templates show a "Cancel slot" confirm-modal button (with a reason textarea) when the slot status is available or full and it has active bookings or edit/delete are locked; keep the existing Edit/Delete rules unchanged.

SECTION 12: app/blueprints/student/bookings.py and templates/student/booking_detail.html
1. In the booking detail route load history_service.booking_timeline(booking_id, viewer_role="student", viewer_id=g.user.id) and render it under "History" (booked, rescheduled, cancelled, result published). Students never see admin reasons or other people's ids; the service already redacts them.

SECTION 13: tests/conftest.py
1. Add helper run_in_threads(app, functions, barrier=True) that runs each callable in its own thread inside app.app_context(), releases them together with a threading.Barrier, always calls db.session.remove() in a finally block, and returns the list of results or exceptions in order. Requires the file-based SQLite database the app fixture already uses.
2. Add fixture clock: monkeypatches app.services.windows.now_utc to a mutable instance with set(datetime) and advance(timedelta); used by e2e tests where the server runs in the same process.

SECTION 14: pyproject.toml, Makefile, .env.example, README.md
1. pyproject.toml: set [tool.coverage.run] branch = true and [tool.coverage.report] fail_under = 80; register the pytest markers concurrency and e2e if missing.
2. Makefile: add targets test-concurrency (pytest -m concurrency), demo-data (python scripts/seed_demo_data.py), gate-a (bash scripts/verify_gate_a.sh); make test-e2e must run tests/e2e (Playwright chromium installed).
3. .env.example: add the optional comment line "DEMO_PASSWORD=Demo#12345  (only used by scripts/seed_demo_data.py)".
4. README.md: add sections "Demo data and viva script" (link to docs/demo_script_tier1.md), "Gate A" (how to run make gate-a), and fill the Known issues table with these decisions: evaluation has no time restriction; published evaluations are immutable; rubric weightage must total 100 before booking opens; slot creation needs an approved assigned examiner; Admin can add and reject examiners; a full slot reports slot_full; drafts without slots are hidden from students; global BEGIN IMMEDIATE serialises concurrent requests (acceptable locally, revisit if the p95 target fails); soft-delete purge uses updated_at as the deletion time; existing signed session cookies survive a password reset until expiry.
DEBUGGING:
# print("[DEBUG] applied P6 update section N")
OFFLINE DOCKER TEST CASES:
- After sections 1 and 2: pytest -m concurrency passes (20 threads, 5 seats, exactly 5 bookings).
- After all sections: the complete P0-P5 suite still passes with the write lock enabled.
-->
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/maintenance.py
"""
FILE PURPOSE: Housekeeping rules behind the weekly purge job (TDR section 11, "purge-soft-deleted").
DEPENDS ON: app/models, app/services/windows.py, app/services/audit_service.py, app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. purge_soft_deleted(older_than_days=90, now=None) -> int: select examinations with is_deleted True whose updated_at is older than now minus older_than_days (updated_at is the best available deletion time; there is no deleted_at column, record this in the README known issues). Purge an examination ONLY IF it has no booking of ANY status (history must never vanish, risk R-7).
2. For each purgeable examination, in its own transaction: delete its rubric rows, its examination_examiners rows and its slots (none of them can have bookings), then the examination row itself; write ONE audit row (actor NULL, SYSTEM_PURGE, entity examination, details {"name": ..., "course_id": ...}); commit. A failure on one examination is logged with logger.exception, rolled back and does not stop the others.
3. Return the number of examinations purged. Never touch courses, users, bookings, evaluations or audit rows.
4. older_than_days must be a positive integer (ValueError otherwise). The function is idempotent.
DEBUGGING:
# print(f"[DEBUG] purge candidate exam={exam.id} age_days={(now - exam.updated_at).days} bookings={booking_count}")
OFFLINE DOCKER TEST CASES:
- A soft-deleted examination updated 91 days ago with no bookings is purged together with its rubrics, assignments and slots; the audit row exists.
- A soft-deleted examination updated 30 days ago is kept; one with a cancelled booking is kept regardless of age.
- Running purge twice returns 0 the second time.
- A non-deleted examination is never purged.
- older_than_days=0 raises ValueError.
"""
EOF

cat << 'EOF' > app/services/history_service.py
"""
FILE PURPOSE: Builds the per-booking history timeline shown on booking detail pages, with role-based redaction ("complete history", PDR 5.6).
DEPENDS ON: app/models (Booking, AuditLog, Evaluation, ExaminationSlot), app/services/audit_service.py, app/services/windows.py (format only; no clock logic).
PROMPT FOR LLM IMPLEMENTATION:
1. booking_timeline(booking_id, viewer_role, viewer_id) -> list of dicts {"at": datetime, "label": str, "detail": str | None} ordered oldest first, or None when the viewer may not see this booking. Visibility: student only when booking.student_id == viewer_id; examiner only when the booking's CURRENT slot belongs to viewer_id; admin always. Anything else returns None (the route turns it into 404).
2. Sources: the booking row itself (booked_at -> "Booked", cancelled_at -> "Cancelled by student/admin/examiner"), audit_logs for entity_type "booking" and this id (booking.create, booking.cancel, booking.admin_cancel, booking.reschedule) plus slot.cancel rows that list this booking, and the evaluation (submitted_at -> "Evaluation submitted" for admin and examiner only; published_at -> "Result published" for everyone).
3. Labels are plain English with local times left to the template (return raw datetimes). Reschedule rows show "Moved to a different slot" for students and "Moved from slot #A to slot #B" for admin and examiner.
4. Redaction: the admin cancellation REASON and actor ids appear only for admin viewers; students see "Cancelled by the administration" without the reason; examiners see the reason only for slot cancellations of their own slot. Never include audit ip_address, raw JSON or other users' emails for any role.
5. Also provide examination_history_for_student(student_id) returning one summary row per examination the student ever booked (examination, last booking status, evaluation published yes/no, last change time) for the history screen; read-only and scoped to the student.
DEBUGGING:
# print(f"[DEBUG] timeline booking={booking_id} viewer={viewer_role}:{viewer_id} events={len(events)}")
OFFLINE DOCKER TEST CASES:
- A booking that was booked, rescheduled and cancelled by the admin shows three events in order for the admin, and the student sees the same three events without the reason or slot numbers.
- Another student's id returns None; an examiner who does not own the current slot returns None.
- An unpublished evaluation produces no "Result published" event; a submitted one produces "Evaluation submitted" for admin and examiner but not for the student.
- No timeline entry contains the IP address or the text of the reason for a student viewer.
"""
EOF

# ================================ FORMS ==============================

cat << 'EOF' > app/forms/booking_actions.py
"""
FILE PURPOSE: Small forms for Admin booking actions (reschedule, cancel with reason) and slot cancellation with reason.
DEPENDS ON: flask_wtf, wtforms.
PROMPT FOR LLM IMPLEMENTATION:
1. RescheduleForm: new_slot_id SelectField (coerce int) whose choices are injected by the view from eligible slots (same examination, status available, start in the future, not the current slot) labelled "date time - examiner - seats left".
2. ReasonForm: reason (TextAreaField, DataRequired, Length 3-200, strip, label "Reason (kept in the audit history)"). Used for admin cancel and slot cancel.
3. Both inherit FlaskForm (CSRF included). No business rules here.
DEBUGGING:
# print(f"[DEBUG] booking action form {type(form).__name__} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- ReasonForm rejects "ab" and a 201-character string and accepts a normal sentence.
- RescheduleForm with no choices is invalid and shows an explanatory message.
"""
EOF

# ======================== BLUEPRINT ROUTE MODULES ====================

cat << 'EOF' > app/blueprints/admin/booking_actions.py
"""
FILE PURPOSE: ADM-16 reschedule a booking, admin cancel with reason, and admin publish of a submitted evaluation.
DEPENDS ON: admin_bp, admin_required, app/forms/booking_actions.py, app/forms/common.py, app/services/booking_engine.py, app/services/evaluation_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/bookings/<id>/reschedule: show the booking summary and RescheduleForm with eligible target slots (same examination, available, future, not current) loaded by a small query helper in this module or the engine; empty list -> explanatory message and no submit button. POST /admin/bookings/<id>/reschedule (TDR 5.1, field new_slot_id): call booking_engine.reschedule_booking(booking_id, new_slot_id, g.user.id); flash "Booking moved." or the error message; redirect to the booking detail.
2. POST /admin/bookings/<id>/cancel (ReasonForm): call booking_engine.admin_cancel_booking(booking_id, g.user.id, reason); flash "Booking cancelled." or the error message; redirect to the booking detail.
3. POST /admin/evaluations/<id>/publish (ConfirmForm): call evaluation_service.admin_publish; flash "Evaluation published." or the error message; redirect back to the booking detail of that evaluation.
4. Unknown ids return 404. Every POST is CSRF-protected and admin_required. No rule logic in the routes.
DEBUGGING:
# print(f"[DEBUG] admin booking action {request.path} booking={booking_id} result={result}")
OFFLINE DOCKER TEST CASES:
- Reschedule moves the booking, updates both slot counts and statuses, and shows the new slot on the detail page.
- Reschedule to a full slot, a different examination or the same slot flashes the matching message and changes nothing.
- Admin cancel without a reason shows a form error; with a reason frees the seat and the audit tab lists the reason.
- Non-admin POSTs get 403.
"""
EOF

cat << 'EOF' > app/blueprints/admin/evaluations.py
"""
FILE PURPOSE: Admin evaluation tracking list (oversight of pending, draft, submitted and published evaluations).
DEPENDS ON: admin_bp, admin_required, app/services/evaluation_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/evaluations (endpoint evaluations_list) with filters state (not_started, draft, submitted, published), examiner_id, examination_id, q (student name) and pagination, using evaluation_service.list_evaluation_tracking.
2. Above the table a summary strip from evaluation_service.pending_by_examiner ("Examiner X: 4 not yet submitted").
3. Rows link to the booking detail page; submitted rows show a Publish button (POST /admin/evaluations/<id>/publish with CSRF, route in booking_actions.py).
4. Read-only otherwise; Admin never edits scores.
DEBUGGING:
# print(f"[DEBUG] evaluation tracking state={state} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Each state filter returns only matching rows; the summary strip counts match fixtures.
- Non-admin gets 403.
"""
EOF

# ============================= TEMPLATES =============================

cat << 'EOF' > app/templates/admin/reschedule.html
<!--
FILE PURPOSE: ADM-16 reschedule booking.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Reschedule booking #<id>". Summary card: student, examination, current slot (localdt), examiner, status badge. Form (csrf) posting to /admin/bookings/<id>/reschedule with the target-slot select (label "New slot") and a primary "Move booking" button; Cancel link back to the booking detail.
2. Explain: "The student keeps the same booking. Seats are updated on both slots." When no eligible slot exists show a muted message and no form.
DEBUGGING:
<!-- DEBUG: reschedule booking {{ booking.id }} targets {{ form.new_slot_id.choices|length }} -->
OFFLINE DOCKER TEST CASES:
- The select never lists the current slot, full slots or other examinations' slots.
-->
EOF

cat << 'EOF' > app/templates/admin/evaluations_list.html
<!--
FILE PURPOSE: Admin evaluation tracking table.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_admin.html; page_title "Evaluations". Summary strip of pending counts per examiner. Filter bar: state pills (All, Not started, Draft, Submitted, Published), examination select, examiner select, student q.
2. Table: Student, Examination, Slot time, Examiner, Tracking badge (not started grey, draft grey, submitted blue, published green via the evaluation badge macro), Total (when present), View link to the booking, Publish button for submitted rows. Pager and empty state.
DEBUGGING:
<!-- DEBUG: evaluation tracking {{ page.total }} state {{ state }} -->
OFFLINE DOCKER TEST CASES:
- Publish buttons appear only on submitted rows and post to /admin/evaluations/<id>/publish.
-->
EOF

# ============================== SCRIPTS ==============================

cat << 'EOF' > scripts/seed_demo_data.py
"""
FILE PURPOSE: Fill a fresh database with realistic demo data for the viva and for manual testing, using ONLY the service layer (never raw inserts), so the demo data obeys every business rule.
DEPENDS ON: app factory, app/services/* (catalog_service, admin_service, slot_service, booking_engine, evaluation_service, windows), app/cli.py (create_database, seed_admin).
PROMPT FOR LLM IMPLEMENTATION:
1. Run as "python scripts/seed_demo_data.py" (and through "make demo-data"). Build the app with create_app(), push an app context, call create_database() and seed_admin(). Refuse to run when FLASK_ENV is production or when the DATABASE_URL does not point to a local sqlite file. Read the demo password from DEMO_PASSWORD (default "Demo#12345"); never reuse ADMIN_INITIAL_PASSWORD.
2. Idempotent: if the course code DEMO101 already exists print "Demo data already present." and exit 0 without changing anything.
3. TIME TRAVEL: services read the clock only through windows.now_utc(), so write a context manager fake_clock(dt) that temporarily replaces app.services.windows.now_utc and always restores it (finally). Use it to build history in the right order, then leave the system in a state that is useful right now.
4. Data to create (all through services, as the right actor): admin from init-db; 3 approved examiners (examiner1@demo.local ...), 1 PENDING examiner (examiner.pending@demo.local, registered through the same logic as the register route: role examiner, approval pending, with profile) so the approval flow can be demoed; 20 students (student01@demo.local ... student20@demo.local) with roll numbers; 2 courses (DEMO101 active, DEMO102 inactive).
5. Examination A "Viva - Data Structures" (type viva, max marks 100, rubric criteria Concept 40, Implementation 40, Communication 20 with max scores equal to their weightage): windows so that RIGHT NOW booking is OPEN (booking window from 4 days ago to 10 days in the future, slot-creation window ended 5 days ago, cancellation deadline 8 days ahead); 4 future slots across the next week with capacities 3, 3, 2, 1; 9 students booked (one slot FULL, one with a cancelled booking for the history demo, one booking rescheduled by the admin) created under fake_clock at a time inside the booking window.
6. Examination B "Practical - Databases" in the SLOT-CREATION phase right now (creation window open now, booking window starting in 4 days), assigned to two examiners, no slots yet, so the examiner can create a slot live in the demo.
7. Examination C "Project demo - Web" fully COMPLETED in the past: slots in the past (created and booked under fake_clock), 6 bookings, evaluations submitted and PUBLISHED for 4 of them, 1 submitted but unpublished, 1 not evaluated; then run exam_status.sync_all so statuses and booking completion are consistent.
8. At the end print a table of demo accounts (role, email, password) and the three examination names with their current state, plus the exact URL to open (http://127.0.0.1:5000/login). Print counts of what was created.
9. Wrap each phase in try/except that prints which step failed and exits non-zero; no partial silent failures.
DEBUGGING:
# print(f"[DEBUG] demo step={step} clock={windows.now_utc()} created={counts}")
OFFLINE DOCKER TEST CASES:
- On an empty temp DB the script exits 0 and creates 1 admin, 4 examiners, 20 students, 2 courses, 3 examinations; booked_count values equal the number of active bookings for every slot.
- Running it twice prints "Demo data already present." the second time and changes nothing.
- After seeding, Examination A shows booking open and one full slot; Examination B shows slot creation open; Examination C shows completed with 4 published results.
- windows.now_utc is the original function after the script finishes (clock restored), even when a step raised an error.
- With FLASK_ENV=production the script refuses to run.
"""
EOF

cat << 'EOF' > scripts/verify_gate_a.sh
#!/usr/bin/env bash
# FILE PURPOSE: One command that checks every Gate A condition from Master Blueprint 2.3 and, only when everything passes, offers to create the tag tier1-complete.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Bash with "set -uo pipefail" (collect failures instead of stopping at the first). Usage: scripts/verify_gate_a.sh [--tag]. Run from the repo root on branch main with a clean working tree; otherwise print why and exit 2.
# 2. Check 1: tags p0-done to p6-done all exist (git rev-parse -q --verify refs/tags/pN-done) and the commit messages of the six milestone squash commits follow the unique pattern (git log --oneline | grep for Milestone-0 EMP-MAD-1, Milestone-1 ... Milestone-6) with no duplicates.
# 3. Check 2: scripts/check_gate.sh exits 0 (repository-wide audit).
# 4. Check 3: make test-core exits 0 (unit, integration and e2e). Show the last 15 lines of output on failure.
# 5. Check 4: the concurrency suite passes by itself: pytest -m concurrency -q (20 threads on a 5-seat slot yields exactly 5 bookings, duplicate-student threads yield exactly 1).
# 6. Check 5: coverage gate: pytest --cov=app --cov-branch --cov-fail-under=80 -q must pass; additionally run the booking engine tests with --cov=app.services.booking_engine --cov-branch and report the percentage; below 100 prints WARN (TDR target), not FAIL.
# 7. Check 6: database creation from code: in a temporary directory run flask init-db with a temp DATABASE_URL and assert exactly one admin and 12 tables (python -c using sqlite3).
# 8. Check 7: traceability: every line of docs/tier1_traceability.md that starts with "| T1-" must have a non-empty "Verified" column marked "yes"; list any that are not.
# 9. Check 8: .env.example contains no ENABLE_ flags set to true and no RAZORPAY or MAIL variables with values.
# 10. Print a PASS/FAIL/WARN line per check and a final summary "GATE A PASSED" or "GATE A FAILED (n checks)". Exit 0 only when no check failed.
# 11. With --tag and a passing run: create the annotated tag tier1-complete (git tag -a tier1-complete -m "Gate A passed") if it does not exist, and print the push command (git push origin tier1-complete). Never push automatically. Without --tag print the exact tag command as a hint.
# DEBUGGING:
# echo "[DEBUG] check=${NAME} status=${STATUS} detail=${DETAIL}" >&2   (when GATE_DEBUG=1)
# OFFLINE DOCKER TEST CASES:
# - On a repository with all tags and green tests the script exits 0 and prints GATE A PASSED.
# - Removing tag p4-done makes check 1 fail and the script exit 1.
# - A failing test makes check 3 fail; the final summary counts the failed checks.
# - Running it with a dirty working tree exits 2 without running any test.
EOF

# ================================ DOCS ===============================

cat << 'EOF' > docs/demo_script_tier1.md
<!--
FILE PURPOSE: The rehearsed 10-minute viva demo script for Tier 1 (Gate A: "the demo script runs clean for all three roles").
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Tier 1 demo script" with a prerequisites block: fresh clone, venv, requirements, copy .env.example to .env, init-db, "make demo-data", run the server, accounts table (admin from .env, examiner1@demo.local, examiner.pending@demo.local, student01@demo.local, password from DEMO_PASSWORD).
2. Five numbered acts, each with Goal, Steps (click by click), Expected result, and "Say this" talking points that map to course requirements: (1) Admin: first-login password change, dashboard totals, approve the pending examiner, open Examination B slot creation controls, rubric total 100 rule, search by name and by ID, history view. (2) Examiner: pending-approval gate shown with the pending account, login as examiner1, create a slot in Examination B inside the window, show that editing is locked once booking starts, evaluate a student (draft, submit, publish). (3) Student: browse, book the last seat of the FULL-capacity demo slot, see the full/duplicate/closed messages, cancel before the deadline, view history, schedule and published result. (4) Admin again: reschedule a booking, change a slot examiner, cancel with a reason, show the audit and timeline. (5) Robustness: show the concurrency test result (pytest -m concurrency), unauthorised URL gives 403, database created by code on a clean folder.
3. A "If something breaks" table (symptom, quick fix) covering: forgot admin password (re-run init-db on a new DB, demo data again), clock-related closed windows (re-run make demo-data on a fresh DB), port in use.
4. A final "Questions to rehearse" list of 12 viva questions about the code (booking transaction, partial unique index, role decorators, window helper, evaluation rules) with one-line answers pointing to the file names.
5. Keep it under 150 lines of plain Markdown.
DEBUGGING:
(none: documentation file) Verify by following the script on a fresh clone with a stopwatch; it must fit in 10 minutes.
OFFLINE DOCKER TEST CASES:
- Every URL and button named in the script exists in the running application.
- The e2e test tests/e2e/test_tier1_demo_flow.py follows acts 1 to 3.
-->
EOF

cat << 'EOF' > docs/tier1_traceability.md
<!--
FILE PURPOSE: Requirement-to-evidence table that Gate A check 7 reads ("every Tier 1 requirement in PDR section 3.2 is demonstrable").
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Tier 1 traceability" and a Markdown table with columns: ID, Requirement (from PDR 3.2), Phase, Automated test file, Demo script act, Verified (yes/no).
2. One row per bullet of PDR section 3.2 (programmatic SQLite creation; pre-created Admin without Admin registration; examiner and student registration and login; examiner approval gate; Admin dashboard totals; course, examination and rubric CRUD; examiner add, approve and deactivate; timelines; slot-creation open/close; booking open/close; Admin search by name or ID; view all slots; reschedule; change examiner; all history; examiner dashboard; slot create, update, remove with window rules; viewing booked students; rubric evaluation with marks and remarks; student dashboard; search and filter; book; cancel before deadline; status, schedule, history, results, feedback; profile edit; capacity rule; duplicate prevention; auto-close on full; status tracking; deliverables: zip, report, video, AI declaration, unique commit per milestone). IDs T1-01, T1-02, ... in order. Rows start with "| T1-" exactly so the gate script can parse them.
3. Fill the Phase, Test file and Demo act columns from the Master Blueprint milestone map and the test files seeded in P1 to P6; leave Verified as "no" until the team has run the matching test and demo step, then change it to "yes".
4. Keep it plain Markdown, under 80 lines.
DEBUGGING:
(none: documentation file) Verify with: grep -c "^| T1-" docs/tier1_traceability.md
OFFLINE DOCKER TEST CASES:
- scripts/verify_gate_a.sh check 7 lists every row whose Verified column is not "yes".
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_booking_engine_concurrency.py
"""
FILE PURPOSE: THE acceptance test of the flagship feature: the engine never overbooks and never double-books under concurrent requests (Gate A, TDR 10).
DEPENDS ON: app/services/booking_engine.py (with the write lock from the P6 update), tests/conftest.py (run_in_threads, make_open_booking_setup, file-based test DB).
PROMPT FOR LLM IMPLEMENTATION:
1. Mark every test with @pytest.mark.concurrency and run each scenario 3 times (parametrise repetition) because races are probabilistic. All threads start together through a Barrier; each thread works inside its own app context and removes its session in a finally block.
2. test_twenty_students_five_seats: 20 distinct students book the same 5-seat slot concurrently. Assert exactly 5 successes and 15 BookingError with code slot_full (no other error type, in particular no "database is locked" OperationalError), booked_count == 5, slot.status == "full", exactly 5 booking rows with status booked, no student with two rows.
3. test_same_student_many_threads: ONE student sends 10 concurrent book requests for the same slot and for different slots of the same examination: exactly 1 success, the rest duplicate_booking (or slot_full on a full slot), exactly 1 active booking row.
4. test_cancel_and_book_race: slot full with 5 bookings; 5 threads cancel and 10 other students book at the same time; afterwards booked_count equals the number of rows with status booked, never exceeds capacity, status is "full" only when booked_count == capacity, and every cancelled booking row has cancelled_at set.
5. test_booking_close_boundary_race: with freeze_now one second before booking_end all threads succeed up to capacity; with the clock one second after, all fail with booking_closed (no seats consumed).
6. test_write_lock_listener_attached: extensions.write_lock_enabled() is True and PRAGMA busy_timeout is 5000.
7. test_second_writer_waits_instead_of_failing: thread A holds a transaction while thread B starts a booking; B completes after A commits without an OperationalError (busy_timeout works).
8. After every scenario run the invariant checker: for every slot booked_count equals COUNT of bookings with status in (booked, completed) and 0 <= booked_count <= max_capacity.
DEBUGGING:
# print(f"[DEBUG] round={round} successes={ok} slot_full={full} errors={other} booked_count={slot.booked_count}")
OFFLINE DOCKER TEST CASES:
- pytest -m concurrency passes 3 consecutive runs offline.
- Removing the BEGIN IMMEDIATE listener or the guarded UPDATE makes test_twenty_students_five_seats fail.
"""
EOF

cat << 'EOF' > tests/unit/test_booking_engine_admin_ops.py
"""
FILE PURPOSE: Rule tests for reschedule_booking, admin_cancel_booking, cancel_slot and change_examiner.
DEPENDS ON: app/services/booking_engine.py, hooks.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Reschedule: test_reschedule_moves_booking_and_counts, test_reschedule_reopens_old_full_slot, test_reschedule_fills_new_slot_to_full, test_reschedule_same_slot_refused, test_reschedule_other_examination_refused, test_reschedule_to_full_cancelled_completed_or_started_slot_refused, test_reschedule_cancelled_booking_refused, test_reschedule_with_evaluation_refused, test_reschedule_ignores_booking_window_and_deadline, test_reschedule_records_rescheduled_from_slot_id, test_reschedule_requires_admin_actor, test_reschedule_audit_row.
2. Admin cancel: test_admin_cancel_frees_seat_and_sets_cancelled_by, test_admin_cancel_requires_reason, test_admin_cancel_ignores_deadline, test_admin_cancel_refused_with_submitted_or_published_evaluation, test_admin_cancel_allowed_with_draft_evaluation, test_admin_cancel_runs_post_hooks_after_commit.
3. Cancel slot: test_cancel_slot_cancels_all_active_bookings_and_zeroes_count, test_cancel_slot_by_owner_and_by_admin_only, test_cancel_slot_started_refused, test_cancel_slot_with_published_evaluation_refused, test_cancel_slot_reason_required, test_cancel_slot_hook_called_per_booking, test_cancelled_slot_cannot_be_booked_or_reopened.
4. Change examiner: test_change_examiner_rules (not assigned, inactive, same, overlap, cancelled slot), test_change_examiner_keeps_bookings_and_evaluations, test_admin_service_wrapper_delegates.
5. Every failure test asserts the stable code AND that counts and statuses are exactly unchanged (rollback proof); use the invariant checker from the concurrency suite after each test.
DEBUGGING:
# print(f"[DEBUG] admin op case {name}: code={code} counts={[s.booked_count for s in slots]}")
OFFLINE DOCKER TEST CASES:
- 31 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_status_jobs_and_maintenance.py
"""
FILE PURPOSE: Tests for sync_all, purge_soft_deleted and the jobs CLI.
DEPENDS ON: app/services/exam_status.py, app/services/maintenance.py, app/cli.py, tests/conftest.py (freeze_now).
PROMPT FOR LLM IMPLEMENTATION:
1. Sync: test_sync_marks_past_slots_and_bookings_completed, test_sync_ignores_cancelled, test_sync_is_idempotent_no_second_audit_rows, test_sync_updates_exam_status_by_dates, test_sync_exam_completed_after_all_evaluated, test_sync_one_audit_row_per_changed_exam, test_future_slots_untouched, test_completed_booking_still_blocks_duplicate_booking (partial unique index covers completed), test_student_cannot_cancel_completed_booking.
2. Purge: test_purge_old_deleted_exam_without_bookings, test_purge_keeps_recent, test_purge_keeps_exam_with_any_booking, test_purge_idempotent, test_purge_never_touches_active_exam, test_purge_invalid_days.
3. CLI: test_jobs_sync_exam_status_command_output, test_jobs_purge_command_days_option, test_jobs_exit_zero_when_nothing_to_do.
DEBUGGING:
# print(f"[DEBUG] job case {name}: summary={summary}")
OFFLINE DOCKER TEST CASES:
- 18 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_history_service.py
"""
FILE PURPOSE: Tests for booking_timeline and examination_history_for_student, focused on redaction.
DEPENDS ON: app/services/history_service.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_timeline_booked_only, test_timeline_after_reschedule_and_admin_cancel_for_admin, test_student_view_redacts_reason_and_slot_numbers, test_examiner_view_for_current_slot_owner_only, test_foreign_student_gets_none, test_unpublished_evaluation_not_in_student_timeline, test_submitted_event_visible_to_admin_and_examiner_only, test_no_ip_or_raw_json_in_any_view, test_events_sorted_oldest_first, test_examination_history_one_row_per_examination.
2. Build scenarios through the engine functions (not raw inserts) so audit rows are real.
DEBUGGING:
# print(f"[DEBUG] timeline {[(e['at'], e['label']) for e in events]}")
OFFLINE DOCKER TEST CASES:
- 10 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_admin_booking_actions_and_tracking.py
"""
FILE PURPOSE: HTTP tests for reschedule, admin cancel, admin publish, slot cancel by the examiner, and the evaluations tracking page.
DEPENDS ON: tests/conftest.py (admin_client, examiner_client).
PROMPT FOR LLM IMPLEMENTATION:
1. Reschedule: test_reschedule_form_lists_only_eligible_slots, test_reschedule_post_success_flash_and_counts, test_reschedule_post_full_slot_flash, test_reschedule_forged_slot_id_refused.
2. Cancel: test_admin_cancel_requires_reason_form_error, test_admin_cancel_success_and_audit_reason_visible_to_admin_only, test_booking_detail_actions_only_for_booked_status.
3. Publish: test_admin_publish_submitted_evaluation, test_admin_publish_draft_refused_flash, test_published_result_now_visible_to_student.
4. Examiner slot cancel: test_examiner_cancel_slot_cancels_bookings_flash_count, test_examiner_cannot_cancel_other_examiners_slot_404, test_cancel_slot_requires_reason.
5. Tracking: test_evaluations_list_filters_by_state, test_pending_by_examiner_strip_counts, test_sidebar_has_ten_links.
6. Authorisation: every new POST route returns 403 for student and examiner and redirects anonymous users to /login; CSRF enforced when enabled.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 19 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_role_scoped_visibility.py
"""
FILE PURPOSE: Proves role-scoped visibility of data across ALL data-bearing pages (milestone acceptance: students see only their own data).
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Build one dataset with 2 examiners (A, B), 4 students (S1 to S4) with distinctive names and emails, 2 examinations, bookings spread across both examiners' slots, evaluations in every state (draft, submitted, published) and a cancelled booking.
2. Student matrix: for S1 and S2 fetch /student/bookings, /student/history, /student/schedule, /student/results, /student/dashboard, /student/bookings/<own id>, /student/results/<own id> and assert the page contains ONLY that student's data (other students' names, emails, roll numbers never appear) and that unpublished evaluations leak nothing (no totals, no remarks, no status words like "draft" or "submitted").
3. Examiner matrix: A sees only slots, students and evaluations of A's slots (B's student names absent) on /examiner/slots, /examiner/slots/<id>/students, /examiner/evaluations, /examiner/evaluations/submitted, /examiner/dashboard; foreign ids return 404.
4. Admin sees everything: bookings list contains all students; history audit tab lists actions.
5. Secret hygiene: across every page fetched in this test assert the response bodies never contain "scrypt:" or "pbkdf2:" (password hashes), "password_hash", or any session cookie value.
6. Timeline redaction: the admin cancel reason appears on the admin booking page and NOT on the student's booking detail.
DEBUGGING:
# print(f"[DEBUG] visibility check role={role} url={url} leaked={leaked}")
OFFLINE DOCKER TEST CASES:
- The test fetches at least 30 pages and finds no leakage.
- Making any student query unscoped in student_queries.py makes this test fail.
"""
EOF

cat << 'EOF' > tests/integration/test_demo_seed_and_jobs_cli.py
"""
FILE PURPOSE: Tests for scripts/seed_demo_data.py and the flask jobs commands against a temporary database.
DEPENDS ON: scripts/seed_demo_data.py, app/cli.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Load the seed script as a module with importlib (it must expose a main(app=None) function used by __main__) and run it against the temp-DB app.
2. test_seed_creates_expected_counts (1 admin, 4 examiners incl. 1 pending, 20 students, 2 courses, 3 examinations), test_seed_slot_counts_consistent (booked_count equals active bookings for every slot), test_seed_states_after_run (A booking open with one full slot, B slot creation open, C completed with 4 published results), test_seed_idempotent_second_run, test_seed_restores_clock, test_seed_refuses_production, test_seed_passwords_work (log in as student01 and examiner1 through the client).
3. test_flask_jobs_sync_exam_status_runs_clean_after_seed (second run reports zero changes) and test_flask_jobs_purge_reports_zero.
DEBUGGING:
# print(f"[DEBUG] seed counts={counts}")
OFFLINE DOCKER TEST CASES:
- 9 tests pass offline in under 20 seconds.
"""
EOF

cat << 'EOF' > tests/e2e/conftest.py
"""
FILE PURPOSE: Fixtures for browser tests: a real Flask server on a free port in the SAME process, a controllable clock and Playwright (chromium, offline).
DEPENDS ON: playwright.sync_api, werkzeug.serving, app factory, app/cli.py, tests/conftest.py (clock fixture).
PROMPT FOR LLM IMPLEMENTATION:
1. Fixture live_server (session or module scope): create the app with the testing config (APP_TIMEZONE set to UTC to keep datetime-local inputs simple, CSRF ENABLED so the real forms are exercised), a temp file SQLite database, create_database() and seed_admin() with known credentials (must_change_password True), then start werkzeug.serving.make_server on 127.0.0.1 port 0 in a daemon thread; yield the base URL; shut down cleanly.
2. Because the server runs in the same process, the clock fixture from tests/conftest.py (patching windows.now_utc) controls time for the server; document this in a comment.
3. Fixtures browser and page using playwright.sync_api (chromium, headless); one fresh browser context per role so cookies never mix; helper login(page, base_url, email, password).
4. Mark everything with @pytest.mark.e2e; skip with a clear message when playwright or its chromium browser is not installed ("run: playwright install chromium").
5. No network access: assert in a fixture that page.route blocks any non-127.0.0.1 request (fail the test if one is attempted) to prove the app is offline-safe.
DEBUGGING:
# print(f"[DEBUG] live server at {base_url} clock={windows.now_utc()}")
OFFLINE DOCKER TEST CASES:
- The fixture starts and stops without leaving threads or temp files behind.
- A request to an external host from a page fails the test.
"""
EOF

cat << 'EOF' > tests/e2e/test_tier1_demo_flow.py
"""
FILE PURPOSE: Browser walkthrough of the Tier 1 demo (acts 1 to 3 of docs/demo_script_tier1.md) through the real UI.
DEPENDS ON: tests/e2e/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. One test function test_full_tier1_flow driven by the page object helpers, with the clock fixture advanced between phases: (a) Admin logs in, is forced to change the password, then creates a course, an examination with windows around the clock, rubric criteria 60 and 40; (b) an examiner registers in a second context and sees the pending-approval page; Admin approves; the examiner logs in again and reaches the dashboard; Admin assigns the examiner and opens slot creation; (c) the examiner creates a slot with capacity 1; Admin closes slot creation and opens booking after the clock moves into the booking window; (d) student 1 registers, logs in, books the slot and sees "Booking confirmed."; student 2 registers and sees the slot as full and gets "This slot is full."; student 1 sees the duplicate message on a second attempt and can cancel, after which student 2 can book; (e) the examiner opens the student list, evaluates (draft, submit, publish); the student sees the result with feedback; (f) a student opening /admin/dashboard sees the 403 page.
2. Use accessible selectors (labels, roles, button names) rather than CSS ids so the test also verifies accessibility; assert flash texts exactly as the UI shows them.
3. After the flow assert through the database that booked_count equals active bookings and that the audit log contains booking.create and booking.cancel rows.
4. Keep the whole test under 90 seconds; take a screenshot into test-results/ on failure.
DEBUGGING:
# print(f"[DEBUG] e2e step={step} url={page.url} clock={windows.now_utc()}")
OFFLINE DOCKER TEST CASES:
- The test passes with the network disabled (docker compose --profile test run --rm test make test-e2e).
- It fails if any Tier 1 route returns a 500 during the walk.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs scripts -type d -empty -exec touch {}/.gitkeep \;
chmod +x scripts/*.sh

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P6 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P6_update_existing_files.md in ORDER (sections 1 and 2 first: the write lock and the engine functions) with the CURRENT files."
echo "2. Run 'pytest -m concurrency' first, then 'docker compose --profile test run --rm test' (or 'make test-core'), then 'make demo-data' on a fresh database and rehearse docs/demo_script_tier1.md."
echo "3. Run 'git add . && git commit -m \"wip: P6 history tracking and hardening\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p6-booking-history-tracking && git commit -m \"Milestone-6 EMP-Booking-History-Tracking\" && git tag p6-done && git push origin main --tags'."
echo "5. Gate A: run 'bash scripts/verify_gate_a.sh --tag' (checks tags, tests, concurrency, coverage, traceability) and push the tier1-complete tag."
echo "Project scaffolding complete for Tier 1 (P0-P6). Tier 2 scripts (P7-P12) are generated in a later pass and only after tier1-complete exists."
echo "====================================================="
