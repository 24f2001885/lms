#!/usr/bin/env bash
# =====================================================================
# P5.sh - Milestone M5: Student Dashboard & Slot Booking (Tier 1)
# Course commit message : Milestone-5 EMP-Student-Booking
# Branch                : phase/p5-student-booking
# Depends on            : P4 (tag p4-done)
# Screens               : STU-01 to STU-10 (Design Plan 5.4)
# NOT in P5            : Admin reschedule / admin cancel / slot cancel (P6),
#                        BEGIN IMMEDIATE hardening and the concurrency test (P6).
#                        The P5 engine is already written to the final algorithm
#                        (TDR 3.3) so P6 only adds the transaction lock and tests.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P5_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P5"
BRANCH="phase/p5-student-booking"
PREV_TAG="p4-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P4 first."; exit 1; }
[ -f app/services/evaluation_service.py ] || { echo "ERROR: app/services/evaluation_service.py missing (P4 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P5 needs)
# ---------------------------------------------------------------------
mkdir -p app/services app/blueprints/student
mkdir -p app/templates/student app/templates/macros
mkdir -p tests/unit tests/integration docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P5_update_existing_files.md
<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P5 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file.

SECTION 1: app/blueprints/student/__init__.py (stub from P2)
1. Keep student_bp = Blueprint("student", __name__, url_prefix="/student").
2. DELETE the stub dashboard route and its use of auth/role_landing_stub.html.
3. At the bottom import the route modules so they register on student_bp: dashboard, examinations, bookings, results (each with "# noqa: E402,F401"). No logic besides the blueprint and the imports.

SECTION 2: app/services/audit_service.py
1. Add action-name constants: BOOKING_CREATE = "booking.create", BOOKING_CANCEL = "booking.cancel". (P6 adds BOOKING_RESCHEDULE, BOOKING_ADMIN_CANCEL, SLOT_CANCEL, SYSTEM_* constants.)

SECTION 3: app/templates/auth/role_landing_stub.html
1. DELETE this file: all three stub dashboards are now replaced (admin P3, examiner P4, student P5). Also delete any test that still references it.

SECTION 4: tests/conftest.py
1. Add fixture student_client: creates an active student (must_change_password False), logs in via POST /login and returns (client, student).
2. Add factory make_open_booking_setup(student_count=1, capacity=5): builds a ready examination whose BOOKING window contains the frozen now (booking_open True, rubric total 100, approved assigned examiner) with one future available slot, returns (examination, slot, examiner, students).
3. Add factory make_published_evaluation(booking, examiner, total): creates an evaluation with status published and per-criterion scores summing to total.

SECTION 5: app/static/css/app.css
1. Add .slot-row-full (muted text colour), .deadline-note (small muted text), .exam-card (card with hover shadow and a status badge slot in the corner). No other changes.
DEBUGGING:
# print("[DEBUG] applied P5 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P4 suite still passes and GET /student/dashboard returns the real dashboard for a student.
- grep finds no reference to role_landing_stub anywhere in app/ or tests/.
-->
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/hooks.py
"""
FILE PURPOSE: The two extension points that keep Tier 3 purely additive (TDR section 2): pre_booking_hooks and post_cancel_hooks. Both lists stay EMPTY in Tier 1 and Tier 2.
DEPENDS ON: nothing (standard library only). Must not import booking_engine (avoid circular imports).
PROMPT FOR LLM IMPLEMENTATION:
1. Define a frozen dataclass HookContext with fields: student_id (int), slot_id (int), examination_id (int), booking_id (int | None), actor_id (int | None).
2. Module-level lists pre_booking_hooks and post_cancel_hooks (typed as list of callables taking a HookContext). They are empty at import time.
3. register_pre_booking(fn) and register_post_cancel(fn) append a function (ignore duplicates). clear_hooks() empties both lists (tests only).
4. run_pre_booking(ctx): call every pre hook in registration order INSIDE the booking transaction; a hook may raise a BookingError to veto the booking; any other exception propagates (the caller rolls back). Returns None.
5. run_post_cancel(ctx): call every post hook AFTER the cancel transaction has committed; exceptions are caught, logged with logger.exception (never the payload) and never undo the cancellation.
6. Document in the module docstring that Tier 3 payments (P16) register one hook of each kind and that Tier 1/2 code never imports anything from a tier3 package.
DEBUGGING:
# print(f"[DEBUG] hooks pre={len(pre_booking_hooks)} post={len(post_cancel_hooks)} ctx={ctx}")
OFFLINE DOCKER TEST CASES:
- Both lists are empty after import and after clear_hooks().
- A registered pre hook that raises BookingError("payment_required", ...) stops book_slot and no booking row exists.
- A registered post hook that raises RuntimeError does not stop cancel_booking from committing.
- Hooks run in registration order; registering the same function twice runs it once.
"""
EOF

cat << 'EOF' > app/services/booking_engine.py
"""
FILE PURPOSE: The flagship feature: booking and cancelling slots with capacity, duplicate and window rules (TDR section 3). P5 delivers book_slot and cancel_booking in their FINAL algorithmic form; P6 adds the write-lock transaction, reschedule, admin cancel, slot cancel and change examiner to this same module.
DEPENDS ON: app/models (Booking, ExaminationSlot, Examination, User), app/services/windows.py, app/services/hooks.py, app/services/audit_service.py, app/errors.py (BookingError and the code constants), app/extensions.py (db).
PROMPT FOR LLM IMPLEMENTATION:
1. Invariants to protect (TDR 3.1): 0 <= booked_count <= max_capacity; at most one booking with status booked or completed per (student, examination); booking only while the booking window is open; slot status becomes full exactly when booked_count == max_capacity and returns to available when a seat is freed (unless the slot is cancelled or completed).
2. Clock: always windows.now_utc() through the module (or the optional now argument for tests). Never datetime.now().
3. book_slot(student_id, slot_id, now=None) -> Booking. Do everything in ONE transaction and commit once at the end. Check IN THIS ORDER, each failure raises BookingError(code, message) and rolls back: (a) student exists, role student, is_active ("not_a_student"); (b) slot exists, joined to its examination ("slot_not_found"); (c) slot.status: "full" -> SLOT_FULL ("This slot is full. Please choose another slot."), "cancelled" or "completed" -> SLOT_NOT_AVAILABLE ("This slot is no longer available."); (d) slot.start_at must be later than now, otherwise SLOT_NOT_AVAILABLE; (e) the examination is not soft-deleted and its course is active, then windows.assert_booking_open(exam, now) (BOOKING_CLOSED, "Booking is closed."); (f) hooks.run_pre_booking(HookContext(...)); (g) duplicate check: any booking of this student for this EXAMINATION with status booked or completed -> DUPLICATE_BOOKING ("You already have a booking for this examination."); (h) capacity claim with ONE conditional UPDATE: set booked_count = booked_count + 1 where id = slot_id and status = "available" and booked_count < max_capacity; if the affected row count is 0, reload the slot and raise SLOT_FULL or SLOT_NOT_AVAILABLE accordingly (a guarded UPDATE, not read-then-write, so a stale read can never overbook); (i) insert Booking(student_id, slot_id, examination_id copied from the slot, status "booked", booked_at = now); (j) if the claimed count now equals max_capacity run a second conditional UPDATE setting status = "full" where id = slot_id and status = "available" and booked_count = max_capacity; (k) audit_service.log_action(student_id, BOOKING_CREATE, "booking", booking.id, {...}); commit.
4. IntegrityError mapping (second line of defence): on commit/flush rollback and translate: the partial unique index uq_bookings_active_student_exam -> DUPLICATE_BOOKING; the CHECK on booked_count -> SLOT_FULL; anything else is re-raised.
5. cancel_booking(student_id, booking_id, now=None) -> Booking: booking must exist and belong to the student ("booking_not_found"), status must be "booked" ("booking_not_cancellable": completed and already-cancelled bookings cannot be cancelled), windows.assert_can_cancel(exam, now) (CANCEL_DEADLINE_PASSED, "The cancellation deadline has passed."). Then call the internal helper below, audit BOOKING_CANCEL with {"by": "student"}, commit, and AFTER the commit call hooks.run_post_cancel.
6. Internal helper _release_seat(booking, cancelled_by_id, now): set booking.status "cancelled", cancelled_at, cancelled_by; run a guarded UPDATE decrementing the slot (booked_count = booked_count - 1 where id = slot_id and booked_count > 0); then a guarded UPDATE setting the slot status back to "available" where id = slot_id and status = "full" and booked_count < max_capacity (a cancelled or completed slot is never reopened). P6 reuses this helper for admin cancel and slot cancel; keep it free of window checks and commits.
7. All user-visible messages are short, plain English (TDR 12). Error code constants come from app/errors.py; do not invent new codes besides slot_not_found, not_a_student, booking_not_found, booking_not_cancellable (define them as constants next to the others if app/errors.py lacks them).
8. No Flask request/flash/redirect usage in this module; the engine is shared by HTML routes now and the JSON API in P7.
DEBUGGING:
# print(f"[DEBUG] book_slot student={student_id} slot={slot_id} booked_count_before={before} rowcount={result.rowcount} status={slot.status}")
OFFLINE DOCKER TEST CASES:
- Happy path: booking row created with status "booked", slot.booked_count 1, audit row booking.create.
- Booking the last seat flips the slot to "full"; the next student gets slot_full; after one cancellation the slot is "available" again and a booking succeeds.
- Closed window (switch off, before start, after end) -> booking_closed; slot already started -> slot_not_available; cancelled slot -> slot_not_available.
- Same student, same examination, second slot -> duplicate_booking; after cancelling, re-booking works.
- Cancelling after the deadline -> cancel_deadline_passed and booked_count unchanged; cancelling a completed or already cancelled booking -> booking_not_cancellable.
- Cancelling someone else's booking -> booking_not_found.
- A veto from a registered pre-booking hook leaves the database untouched.
- Each failure case leaves booked_count and booking rows exactly as before (rollback proof).
- The guarded UPDATE prevents overbooking even if booked_count was read stale (simulate by calling the UPDATE path directly with booked_count = max_capacity).
"""
EOF

cat << 'EOF' > app/services/student_queries.py
"""
FILE PURPOSE: Read-only queries for the student screens, so routes contain no query logic and every query is scoped to the signed-in student (PDR 5.4, TDR section 6).
DEPENDS ON: app/models, app/services/windows.py, app/services/evaluation_service.py (published_for_student), app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Visibility rule for examinations: show an examination to students only when it is not soft-deleted, its course is active, and (its status is not "draft" OR it has at least one non-cancelled slot). Drafts without slots stay hidden. This also covers the gap between the slot-creation window and the booking window.
2. list_examinations(student_id, q=None, course_id=None, exam_type=None, page=1, per_page=20): paginated visible examinations ordered by booking_start; each item carries booking state from windows.window_state (open/closed/scheduled with the reason text, e.g. "Booking opens on 12 Dec, 10:00"), the student's own active booking for it (or None) and the count of available slots. Filters are whitelisted (exam_type must be in EXAM_TYPES, course_id must be an int).
3. get_examination_for_student(exam_id) returns the examination only if visible (else None -> 404). slots_for_examination(exam_id) returns slots with status available or full whose start_at is in the future (completed/cancelled hidden), ordered by start_at, eager loading the examiner name, each with seats_left.
4. dashboard_data(student_id): available_examinations (booking effectively open now and the student has no active booking for it, max 6), available_slots (next 6 available future slots of those examinations), upcoming (the student's booked bookings whose slot starts in the future, next 5), booked (all the student's bookings with status booked, count and list), published_results (latest 5 from evaluation_service.published_for_student).
5. my_bookings(student_id, status=None, page=1): the student's bookings, newest first, eager loading slot, examination, examiner and evaluation (only the published flag). get_owned_booking(student_id, booking_id) returns None for anyone else's booking. schedule(student_id): booked bookings with future slot start ordered ascending. history(student_id, page): ALL of the student's bookings of every status (booked, cancelled, completed) newest first plus a grouped examination-history summary (examination, final status, result published yes/no).
6. results(student_id, page) and result_detail(student_id, booking_id): ONLY evaluations with status "published" belonging to the student's own bookings; result_detail returns total, maximum marks, per-criterion scores with comments and the remarks; anything else returns None (404). Students never see draft or submitted evaluations or the examiner's internal data beyond name.
7. Every function takes student_id explicitly; no function accepts a user object from the request; no query is written without a student filter where student data is involved.
DEBUGGING:
# print(f"[DEBUG] student_queries {name} student={student_id} rows={len(items)}")
OFFLINE DOCKER TEST CASES:
- A draft examination without slots is invisible; one with a slot is visible with the reason text.
- dashboard_data excludes examinations the student already booked from available_examinations.
- get_owned_booking returns None for another student's booking; result_detail returns None for a draft or submitted evaluation.
- history includes cancelled bookings; schedule excludes past slots and cancelled bookings.
- list_examinations with exam_type="quiz" is ignored (whitelist) and does not error.
"""
EOF

# ========================= BLUEPRINT ROUTE MODULES ===================

cat << 'EOF' > app/blueprints/student/dashboard.py
"""
FILE PURPOSE: STU-01 student dashboard.
DEPENDS ON: student_bp (app/blueprints/student/__init__.py), student_required, app/services/student_queries.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/dashboard (endpoint dashboard) with student_required. Call student_queries.dashboard_data(g.user.id) and render student/dashboard.html. No other logic.
2. Charts are added in P8; leave nothing in the route for them.
DEBUGGING:
# print(f"[DEBUG] student dashboard user={g.user.id} sections={ {k: len(v) for k, v in data.items() if hasattr(v, '__len__')} }")
OFFLINE DOCKER TEST CASES:
- A new student sees five sections with empty states; after booking, Upcoming and Booked show the booking.
- Examiner and Admin get 403.
"""
EOF

cat << 'EOF' > app/blueprints/student/examinations.py
"""
FILE PURPOSE: STU-02 browse/search/filter examinations and STU-03 examination detail with slots and the booking confirmation modal (STU-04).
DEPENDS ON: student_bp, student_required, app/services/student_queries.py, app/services/windows.py, app/forms/common.py (ConfirmForm, parse_page).
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/examinations with query parameters q, course_id, exam_type, page. Render student/examinations.html with the paginated cards from student_queries.list_examinations.
2. GET /student/examinations/<id>: examination via get_examination_for_student (404 when None), its slots via slots_for_examination, the student's own active booking for it, and windows.window_state for the reason line. Provide one ConfirmForm instance per page (CSRF token for the modal forms).
3. A Book button is enabled only when booking is effectively open, the slot is available and the student has no active booking for this examination; otherwise it is disabled with the exact reason text ("Booking opens on ...", "Booking is closed", "This slot is full", "You already booked this examination").
4. No booking logic here; the confirm modal posts to /student/slots/<id>/book (route in bookings.py).
DEBUGGING:
# print(f"[DEBUG] student exam detail exam={exam.id} slots={len(slots)} own_booking={own and own.id}")
OFFLINE DOCKER TEST CASES:
- Draft examination id returns 404; deleted examination returns 404.
- Filters narrow the list and survive paging.
- With booking closed every Book button is disabled with a reason line.
"""
EOF

cat << 'EOF' > app/blueprints/student/bookings.py
"""
FILE PURPOSE: Booking actions and views: book (STU-04), cancel, my bookings (STU-05), booking detail (STU-06), schedule (STU-07), history (STU-08).
DEPENDS ON: student_bp, student_required, app/forms/common.py (ConfirmForm), app/services/booking_engine.py, app/services/student_queries.py, app/errors.py.
PROMPT FOR LLM IMPLEMENTATION:
1. POST /student/slots/<id>/book: validate ConfirmForm; load the slot (404 if it does not exist or its examination is not visible to students); call booking_engine.book_slot(g.user.id, slot_id). Success: flash "Booking confirmed." (category success) and redirect to /student/bookings. BookingError/WindowError: flash the error message (category danger) and redirect back to /student/examinations/<examination_id>. Never render on POST (post/redirect/get), so a refresh cannot double-submit.
2. POST /student/bookings/<id>/cancel: validate ConfirmForm; booking via student_queries.get_owned_booking (404 for other students' ids); call booking_engine.cancel_booking; flash "Booking cancelled. Your seat has been released." or the error message; redirect to /student/bookings.
3. GET /student/bookings (status filter, pagination), GET /student/bookings/<id> (own only; shows status, slot time, examiner, deadline note, Cancel button when allowed), GET /student/schedule, GET /student/history.
4. The Cancel button shows only for status booked; it is enabled until the examination's cancellation deadline and otherwise replaced by the text "Cancellation closed on <local date>".
5. Double-submit protection is server-side only: a second identical POST must end in the duplicate_booking flash.
DEBUGGING:
# print(f"[DEBUG] student booking action {request.path} user={g.user.id} result={result}")
OFFLINE DOCKER TEST CASES:
- Book then cancel through the client: booking_count and slot status change as expected.
- Posting book twice quickly shows "You already have a booking for this examination." the second time and keeps one row.
- Cancel of another student's booking returns 404 and changes nothing.
- A forged book POST to a cancelled slot flashes the unavailable message.
- GET on the book or cancel URLs returns 405.
"""
EOF

cat << 'EOF' > app/blueprints/student/results.py
"""
FILE PURPOSE: STU-09 results list and STU-10 result detail with feedback (scorecard download arrives in P12).
DEPENDS ON: student_bp, student_required, app/services/student_queries.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/results (paginated published results only) and GET /student/results/<booking_id> (404 unless the booking belongs to the student AND its evaluation is published).
2. Detail data comes from student_queries.result_detail: examination, slot date, examiner name, total and maximum, per-criterion table (criterion, score, maximum, comment) and the remarks text under "Feedback".
3. Nothing about draft or submitted evaluations is ever shown, not even their existence.
DEBUGGING:
# print(f"[DEBUG] student result booking={booking_id} found={detail is not None}")
OFFLINE DOCKER TEST CASES:
- A submitted but unpublished evaluation returns 404 for the student and does not appear in the list.
- After the examiner publishes, the result appears with the correct total and feedback.
- Another student's booking id returns 404.
"""
EOF

# ============================= TEMPLATES =============================

cat << 'EOF' > app/templates/student/base_student.html
<!--
FILE PURPOSE: Student layout with a top navbar (Design Plan section 2). Extends base.html by overriding the site_nav block.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html. Override site_nav with a Bootstrap navbar: brand "EMP", links Dashboard, Examinations, My bookings, Results, Profile, and a Logout POST form with csrf. Active link via request.endpoint with aria-current="page". Collapses to a hamburger below lg.
2. Reuse the default layout block (flash messages and content). Provide blocks page_title and page_actions in a header row.
DEBUGGING:
<!-- DEBUG: student nav endpoint={{ request.endpoint }} -->
OFFLINE DOCKER TEST CASES:
- Nav shows exactly Dashboard, Examinations, My bookings, Results, Profile, Logout.
-->
EOF

cat << 'EOF' > app/templates/macros/booking_modal.html
<!--
FILE PURPOSE: STU-04 booking confirmation modal macro.
PROMPT FOR LLM IMPLEMENTATION:
1. Macro book_modal(slot, exam, form): a Bootstrap modal with unique id "book-slot-" ~ slot.id, title "Confirm booking", a summary list (examination name, date and time via localdt, examiner name, seats left), a note showing the cancellation deadline, a POST form to url_for student.book with form.hidden_tag() for CSRF, a primary "Confirm booking" button and a Cancel button.
2. Companion macro book_button(slot, enabled, reason): when enabled a button opening the modal, otherwise a disabled button with aria-disabled="true" followed by a visible reason line (class deadline-note).
DEBUGGING:
<!-- DEBUG: book modal slot {{ slot.id }} enabled {{ enabled }} -->
OFFLINE DOCKER TEST CASES:
- The modal form posts to /student/slots/<id>/book and contains a csrf_token input.
- A disabled button is followed by its reason text.
-->
EOF

cat << 'EOF' > app/templates/student/dashboard.html
<!--
FILE PURPOSE: STU-01 dashboard.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; page_title "Dashboard". Five sections as cards: Available examinations (name, type, booking window, View slots link), Available slots (examination, date/time, examiner, seats left, View link), Upcoming (next booked slots with date and examiner), Booked slots (count and list with status badge and link), Published results (examination, total / maximum, View link). Each has an empty state sentence.
2. Reserve an empty div id="charts-widget" for P8 (comment only).
DEBUGGING:
<!-- DEBUG: dashboard data keys {{ data.keys() }} -->
OFFLINE DOCKER TEST CASES:
- Empty states render for a new student; sections fill after booking and publishing.
-->
EOF

cat << 'EOF' > app/templates/student/examinations.html
<!--
FILE PURPOSE: STU-02 browse and search examinations.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; page_title "Examinations". GET filter bar: search q, course select, type select, Filter button.
2. Card grid (2 columns at md, 1 at xs) of .exam-card: course code, name, type, duration, booking window, state badge, the reason line ("Booking opens on ..."), "N slots available", a "You are booked" badge when applicable, and a View slots button. Pager and empty state "No examinations match your search."
DEBUGGING:
<!-- DEBUG: examinations {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Filters persist in the pager links; the booked badge appears only on examinations the student booked.
-->
EOF

cat << 'EOF' > app/templates/student/examination_detail.html
<!--
FILE PURPOSE: STU-03 examination detail with slots and booking buttons.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; header (name, course, type, duration, maximum marks), a booking-window panel with the open/closed badge and reason line, and the cancellation deadline text.
2. Slots table: Date/time, Examiner, Seats left (with .slot-meter), Status badge, Action (book_button macro; full slots use the .slot-row-full class). Include one book_modal per bookable slot after the table.
3. When the student already has an active booking show an info alert linking to the booking and disable every Book button with "You already booked this examination".
DEBUGGING:
<!-- DEBUG: exam {{ exam.id }} slots {{ slots|length }} own booking {{ own_booking.id if own_booking else None }} -->
OFFLINE DOCKER TEST CASES:
- Full slots show a Full badge and a disabled button; a closed window disables all buttons with the reason.
-->
EOF

cat << 'EOF' > app/templates/student/bookings.html
<!--
FILE PURPOSE: STU-05 my bookings.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; page_title "My bookings"; status filter pills (All, Booked, Completed, Cancelled). Table: Examination, Date/time, Examiner, Status badge, Booked on, Actions (Details link; Cancel button inside the confirm_action modal while allowed, else the "Cancellation closed on ..." text). Pager and empty state with a link to Examinations.
DEBUGGING:
<!-- DEBUG: bookings {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Cancelled rows have no Cancel button; booked rows before the deadline do.
-->
EOF

cat << 'EOF' > app/templates/student/booking_detail.html
<!--
FILE PURPOSE: STU-06 booking detail and cancel.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; summary (examination, course, slot start/end, examiner, status badge, booked on, cancelled on if any), deadline note, Cancel button (confirm modal) when allowed, link back to My bookings; when the result is published a link to the result detail.
DEBUGGING:
<!-- DEBUG: booking {{ booking.id }} status {{ booking.status }} -->
OFFLINE DOCKER TEST CASES:
- Only the owner can open the page (404 for others); the result link appears only when published.
-->
EOF

cat << 'EOF' > app/templates/student/schedule.html
<!--
FILE PURPOSE: STU-07 upcoming schedule.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; page_title "My schedule"; chronological list grouped by date (heading per local date), each entry with time range, examination, examiner and a Details link. Empty state "You have no upcoming examinations."
DEBUGGING:
<!-- DEBUG: schedule entries {{ items|length }} -->
OFFLINE DOCKER TEST CASES:
- Past and cancelled bookings never appear.
-->
EOF

cat << 'EOF' > app/templates/student/history.html
<!--
FILE PURPOSE: STU-08 booking and examination history.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; page_title "History". Section "Booking history": table of every booking with status badge, booked and cancelled dates. Section "Examination history": one row per examination with final status and "Result published" yes/no. Pager and empty states.
DEBUGGING:
<!-- DEBUG: history rows {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Cancelled bookings are listed; the examination summary shows one row per examination.
-->
EOF

cat << 'EOF' > app/templates/student/results.html
<!--
FILE PURPOSE: STU-09 results list.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; page_title "Results"; table: Examination, Date, Total / maximum, Published on, View link. Pager; empty state "No results have been published yet."
DEBUGGING:
<!-- DEBUG: results {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Only published results appear.
-->
EOF

cat << 'EOF' > app/templates/student/result_detail.html
<!--
FILE PURPOSE: STU-10 result detail with feedback (scorecard download link is added in P12).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_student.html; header with examination, date, examiner name; a large "Total: X of N" figure; per-criterion table (Criterion, Score, Maximum, Comment); a "Feedback" section with the remarks (empty text hidden); back link to Results.
2. Reserve a Jinja block named result_actions (empty) where P12 adds the scorecard download button.
DEBUGGING:
<!-- DEBUG: result booking {{ booking.id }} total {{ detail.total }} -->
OFFLINE DOCKER TEST CASES:
- Per-criterion scores sum to the displayed total; remarks are escaped.
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_booking_engine_rules.py
"""
FILE PURPOSE: Rule tests for book_slot and cancel_booking (sequential; the concurrency suite is P6).
DEPENDS ON: app/services/booking_engine.py, hooks.py, tests/conftest.py (freeze_now, make_open_booking_setup).
PROMPT FOR LLM IMPLEMENTATION:
1. Booking: test_book_success_updates_count_and_audit, test_booking_copies_examination_id_from_slot, test_last_seat_flips_to_full, test_full_slot_raises_slot_full, test_cancelled_slot_not_available, test_completed_slot_not_available, test_started_slot_not_available, test_closed_window_variants (switch off, before start, after end, inclusive boundaries), test_deleted_examination_closed, test_inactive_course_closed, test_inactive_student_refused, test_duplicate_other_slot_refused, test_duplicate_after_cancel_allowed, test_duplicate_with_completed_booking_refused, test_two_students_independent.
2. Cancel: test_cancel_frees_seat_and_reopens_full_slot, test_cancel_does_not_reopen_cancelled_or_completed_slot, test_cancel_after_deadline_refused, test_cancel_at_deadline_inclusive_ok, test_cancel_foreign_booking_not_found, test_cancel_completed_or_cancelled_not_cancellable, test_cancel_sets_cancelled_by_and_at, test_post_cancel_hook_runs_after_commit.
3. Safety: test_failure_paths_leave_database_unchanged (snapshot booked_count and booking rows before and after every refusal), test_guarded_update_blocks_overbooking_on_stale_read, test_integrity_error_mapped_to_duplicate_booking (bypass the check by inserting a conflicting row in a nested transaction), test_pre_hook_veto_leaves_no_booking, test_hooks_empty_by_default.
4. Assert stable error codes; use freeze_now for every time-dependent test; call hooks.clear_hooks() in a fixture finaliser.
DEBUGGING:
# print(f"[DEBUG] engine case {name}: code={code} booked_count={slot.booked_count} status={slot.status}")
OFFLINE DOCKER TEST CASES:
- 28 tests pass offline; removing the guarded UPDATE makes test_guarded_update_blocks_overbooking_on_stale_read fail.
"""
EOF

cat << 'EOF' > tests/unit/test_student_queries_and_hooks.py
"""
FILE PURPOSE: Tests for student_queries scoping and the hooks registry.
DEPENDS ON: app/services/student_queries.py, hooks.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Visibility: test_draft_without_slots_hidden, test_draft_with_slot_visible, test_deleted_and_inactive_course_hidden, test_closed_and_completed_visible, test_filters_whitelisted.
2. Dashboard/lists: test_dashboard_excludes_already_booked_examinations, test_available_slots_future_only, test_upcoming_sorted_and_future_only, test_schedule_excludes_cancelled, test_history_includes_all_statuses, test_my_bookings_status_filter.
3. Scoping: test_get_owned_booking_none_for_other_student, test_results_only_published, test_result_detail_none_for_draft_submitted_and_foreign, test_all_queries_scoped (create two students with bookings and assert each function returns only the caller's rows).
4. Hooks: test_register_unique, test_run_order, test_clear_hooks, test_post_hook_exception_swallowed_and_logged.
DEBUGGING:
# print(f"[DEBUG] query {name} -> {[getattr(r, 'id', r) for r in rows]}")
OFFLINE DOCKER TEST CASES:
- 19 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_student_access_ownership.py
"""
FILE PURPOSE: Student routes are role-locked and ownership-scoped (risk R-4).
DEPENDS ON: tests/conftest.py (student_client, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. URL matrix from app.url_map for rules starting /student: anonymous -> 302 /login; admin and examiner -> 403; inactive student -> 302 /account-inactive; student with must_change_password -> 302 /change-password; ready student -> not 403 and not 500. GET on POST-only routes returns 405.
2. Ownership with students A and B: B gets 404 for A's booking detail, cancel and result detail; B's lists never contain A's rows; B cannot book on behalf of A (the route takes no student id; assert there is no such parameter).
3. test_csrf_required_on_book_and_cancel with CSRF enabled.
DEBUGGING:
# print(f"[DEBUG] {method} {url} as {role} -> {response.status_code}")
OFFLINE DOCKER TEST CASES:
- The matrix covers every /student rule at collection time.
"""
EOF

cat << 'EOF' > tests/integration/test_student_browse_book_cancel.py
"""
FILE PURPOSE: HTTP tests for STU-01 to STU-08 (browse, book, cancel, lists).
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Browse: test_examinations_filters_and_paging, test_detail_404_for_draft, test_book_buttons_disabled_with_reasons (closed, full, already booked, not yet open).
2. Booking: test_book_flow_success_flash_and_redirect, test_double_post_gives_duplicate_flash_single_row, test_book_closed_window_flash, test_book_full_slot_flash, test_book_unknown_slot_404, test_get_on_book_url_405.
3. Cancel: test_cancel_before_deadline_frees_seat, test_cancel_after_deadline_flash_and_button_hidden, test_cancel_foreign_booking_404.
4. Lists: test_my_bookings_status_pills, test_schedule_lists_upcoming_only, test_history_includes_cancelled, test_dashboard_sections_fill_after_booking.
5. Assert flash text, redirect Location and database state in each test; freeze the clock with freeze_now.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 16 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_student_results_and_acceptance.py
"""
FILE PURPOSE: Results visibility and the milestone acceptance flow (Design Plan 4.2 and 4.3 end to end).
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Results: test_unpublished_result_hidden_everywhere (list, detail, dashboard), test_published_result_visible_with_feedback, test_result_totals_match_scores, test_remarks_escaped.
2. Acceptance test_student_booking_milestone_acceptance through the HTTP client only: Admin-prepared fixtures with a booking-open examination and a 2-seat slot; student 1 browses, books (flash), sees it under My bookings and Schedule, cancels before the deadline (seat freed), books again; student 2 books the same slot; student 3 gets "This slot is full."; student 1 tries a second slot of the same examination and gets the duplicate message; clock moved past the deadline: cancel refused; clock moved past booking_end: new booking refused with "Booking is closed."; examiner submits and publishes an evaluation; student 1 sees the result.
3. Final assertions on the database: booked_count equals the number of active bookings for the slot, statuses consistent, audit rows exist for every booking.create and booking.cancel.
DEBUGGING:
# print(f"[DEBUG] acceptance step={step} {response.status_code} booked_count={slot.booked_count}")
OFFLINE DOCKER TEST CASES:
- The acceptance test passes offline in under 8 seconds and leaves booked_count equal to active bookings.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P5 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P5_update_existing_files.md section by section (student/__init__.py, audit_service.py, delete role_landing_stub.html, conftest.py, app.css) with the CURRENT files."
echo "2. Run 'docker compose --profile test run --rm test' (or 'make test-core'), then walk the booking flow as Admin, Examiner and Student in the browser."
echo "3. Run 'git add . && git commit -m \"wip: P5 student booking\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p5-student-booking && git commit -m \"Milestone-5 EMP-Student-Booking\" && git tag p5-done && git push origin main --tags'."
echo "5. Decisions to confirm: a full slot reports slot_full (TDR step 2 would say slot_not_available); drafts without slots are hidden from students; post-cancel hooks run after commit."
echo "6. Execute P6.sh"
echo "====================================================="
