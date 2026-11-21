#!/usr/bin/env bash
# =====================================================================
# P4.sh - Milestone M4: Examiner Dashboard & Slot Management (Tier 1)
# Course commit message : Milestone-4 EMP-Examiner-Slots-Evaluation
# Branch                : phase/p4-examiner-slots-evaluation
# Depends on            : P3 (tag p3-done)
# Screens               : EXM-01 to EXM-09 (Design Plan 5.3)
# NOT in P4            : cancelling a slot that already has bookings (needs the
#                        booking engine, P6). In P4 a slot can only be edited or
#                        removed while it has no active bookings.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P4_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P4"
BRANCH="phase/p4-examiner-slots-evaluation"
PREV_TAG="p3-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P3 first."; exit 1; }
[ -f app/services/slot_rules.py ] || { echo "ERROR: app/services/slot_rules.py missing (P3 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P4 needs)
# ---------------------------------------------------------------------
mkdir -p app/services app/forms app/blueprints/examiner
mkdir -p app/templates/examiner
mkdir -p tests/unit tests/integration docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P4_update_existing_files.md
<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P4 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file.

SECTION 1: app/blueprints/examiner/__init__.py (stub from P2)
1. Keep examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner").
2. DELETE the stub dashboard route and its use of auth/role_landing_stub.html.
3. At the bottom import the route modules so they register on examiner_bp: dashboard, examinations, slots, evaluations (each with "# noqa: E402,F401"). No logic besides the blueprint and the imports.

SECTION 2: app/services/audit_service.py
1. Add action-name constants: SLOT_CREATE = "slot.create", SLOT_UPDATE = "slot.update", SLOT_DELETE = "slot.delete", EVALUATION_SAVE = "evaluation.save", EVALUATION_SUBMIT = "evaluation.submit", EVALUATION_PUBLISH = "evaluation.publish". Nothing else changes.

SECTION 3: tests/conftest.py
1. Add factory make_ready_examination(examiner=None, now=None): creates an admin, a course, an examination whose slot-creation window contains now (default the frozen clock) with slot_creation_open True and booking window afterwards, rubric criteria weighted 60 and 40 (max scores 60 and 40, max_marks 100), and an approved assignment of the examiner (created if None). Returns (examination, examiner).
2. Add fixture examiner_client: creates an approved active examiner (must_change_password False), logs in via POST /login and returns (client, examiner).
3. Add helper make_booking_with_slot(examination, examiner, student=None, status="booked") returning (booking, slot) with slot.booked_count incremented to match.

SECTION 4: app/static/css/app.css
1. Add .slot-meter (thin progress bar for seats used) and .score-input (narrow numeric input, right aligned). No other changes.
DEBUGGING:
# print("[DEBUG] applied P4 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P3 suite still passes.
- GET /examiner/dashboard as an approved examiner returns 200 with the real dashboard; pending examiners are still redirected to /pending-approval.
-->
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/slot_service.py
"""
FILE PURPOSE: Examiner-side slot rules: create, update, remove, list, booked students and dashboard counts. All window and ownership rules for slots live here (PDR 5.3, TDR 3.5).
DEPENDS ON: app/models, app/services/windows.py, app/services/slot_rules.py, app/services/audit_service.py, app/errors.py (AppError, WindowError).
PROMPT FOR LLM IMPLEMENTATION:
1. Ownership helpers (read-only, return None when not allowed so views can abort(404), as in TDR section 6): get_owned_slot(examiner_id, slot_id) filters by id AND examiner_id; get_assigned_examination(examiner_id, examination_id) returns the examination only when it is not soft-deleted and a row exists in examination_examiners for that examiner; list_assigned_examinations(examiner_id) returns them with course loaded.
2. create_slot(examiner_id, examination_id, start_at, end_at, max_capacity) validates IN THIS ORDER and raises AppError (or WindowError) with a stable code: examiner is approved and active (defensive, "not_approved"); examination assigned and not deleted ("examination_not_found"); windows.assert_slot_creation_open (WindowError code slot_creation_closed); start_at < end_at ("invalid_time_range"); start_at is not in the past relative to windows.now_utc() ("slot_in_past"); max_capacity is an integer between 1 and 500 ("invalid_capacity"); slot_rules.has_overlap is False ("examiner_overlap", message includes the conflicting local time). Then insert status "available", booked_count 0, audit SLOT_CREATE with {examination_id, start, end, capacity}, commit once, return the slot.
3. update_slot(examiner_id, slot_id, start_at, end_at, max_capacity): the slot must be owned (else AppError "slot_not_found"); windows.assert_slots_editable (WindowError slot_edit_locked: only BEFORE booking_start); the slot has no booking with status booked or completed ("slot_has_bookings"); slot status is available ("slot_not_editable"); same time, capacity and overlap checks as create (exclude the slot itself); audit SLOT_UPDATE with before and after values; commit.
4. delete_slot(examiner_id, slot_id): same ownership, editable-window and no-active-booking guards. If NO booking row of any status references the slot, hard delete it; if only cancelled bookings exist, set status "cancelled" instead (history must survive, risk R-7). Audit SLOT_DELETE with {mode: "deleted"|"cancelled"}. Cancelling a slot that has ACTIVE bookings is not possible in P4 (it arrives in P6 through the booking engine); document this in a comment.
5. list_slots(examiner_id, examination_id=None, status=None, page=1, per_page=20) returns a paginated result ordered by start_at; each row exposes seats_left. booked_students(examiner_id, slot_id) returns the bookings of an owned slot with status booked or completed, eager loading student, student profile and evaluation, ordered by student name; cancelled bookings are excluded from this list (a count of cancelled ones is returned separately).
6. examiner_dashboard_counts(examiner_id) returns {"assigned_examinations": n, "created_slots": n (not cancelled), "students_booked": n (bookings with status booked or completed in own non-cancelled slots), "upcoming_slots": [next 5 slots by start_at >= now]} using COUNT queries.
7. slot_creation_state(examination) returns windows.window_state(examination)["slot_creation"] plus a boolean can_create used by templates to disable the Create button with a reason line.
8. No flashing, no redirects, no request access except through audit_service.
DEBUGGING:
# print(f"[DEBUG] slot_service {name} examiner={examiner_id} exam={examination_id} slot={slot_id}")
OFFLINE DOCKER TEST CASES:
- create_slot fails with slot_creation_closed one second before the window opens and succeeds exactly at slot_creation_start and at slot_creation_end; fails when the switch is off.
- create_slot for an examination the examiner is not assigned to raises examination_not_found and writes nothing.
- Two overlapping slots for the same examiner are refused; back-to-back slots are accepted.
- update_slot at exactly booking_start raises slot_edit_locked; one second earlier succeeds.
- update_slot with an active booking raises slot_has_bookings; delete_slot with only a cancelled booking turns the slot into "cancelled" instead of deleting it.
- get_owned_slot returns None for another examiner's slot.
- examiner_dashboard_counts matches hand-counted fixtures and ignores other examiners' data.
"""
EOF

cat << 'EOF' > app/services/evaluation_service.py
"""
FILE PURPOSE: Rubric-based evaluation rules for examiners: which students may be evaluated, saving drafts, submitting and publishing (PDR 5.5, TDR 4.1 evaluation tables).
DEPENDS ON: app/models (Booking, ExaminationSlot, Evaluation, EvaluationScore, ExaminationRubric), app/services/windows.py, app/services/audit_service.py, app/errors.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Eligibility: a booking can be evaluated by examiner E only when booking.slot.examiner_id == E, booking.status is booked or completed, and the slot status is not cancelled. get_owned_booking(examiner_id, booking_id) returns the booking or None (views abort 404; students of other examiners are invisible). There is NO time restriction (evaluation allowed before the slot time); this is an open decision recorded in the README known-issues list.
2. Queries (paginated, eager loading): pending_bookings(examiner_id, examination_id=None, q=None, page=1) = eligible bookings with NO evaluation or an evaluation in status "draft"; submitted_evaluations(examiner_id, status=None, page=1) = evaluations whose examiner_id equals E with status submitted or published; pending_evaluations_count(examiner_id) = COUNT of pending bookings (used by the dashboard counter).
3. form_context(booking) returns the examination's rubric criteria ordered by position, the existing scores keyed by rubric_id, existing remarks, the evaluation status, and a flag locked (status published).
4. save_evaluation(examiner_id, booking_id, scores, comments, remarks, action) where scores maps rubric_id -> Decimal or None, comments maps rubric_id -> str, action is "save_draft", "submit" or "publish". Validation (stable codes): booking owned ("booking_not_found"); the examination has at least one rubric criterion ("no_rubric"); evaluation is not published ("evaluation_locked"); every rubric_id in scores belongs to the examination ("invalid_rubric"); each given score satisfies 0 <= score <= rubric.max_score, 2 decimals ("score_out_of_range", message names the criterion and its maximum); remarks length <= 2000 ("remarks_too_long"); total = sum of given scores must be <= examination.max_marks ("total_exceeds_max"). For "submit" and "publish" EVERY criterion must have a score ("scores_incomplete"). "save_draft" may be partial.
5. Persistence in ONE transaction: get or create the Evaluation (booking_id unique), set examiner_id to the acting examiner (records who actually evaluated, even after an Admin changed the slot examiner), replace score rows for the submitted criteria (upsert by evaluation_id + rubric_id; None means delete that criterion's row), set total_marks = sum of stored scores, remarks, and status: draft stays "draft"; submit sets "submitted" with submitted_at = windows.now_utc(); publish sets "published" with submitted_at (if empty) and published_at. A submitted evaluation may be edited and re-submitted until it is published. Published evaluations are immutable (Admin unpublish is out of scope; record it in known issues). Audit EVALUATION_SAVE / EVALUATION_SUBMIT / EVALUATION_PUBLISH with {booking_id, total}.
6. Student visibility rule (used in P5): only evaluations with status "published" are visible to students; add a helper published_for_student(student_id) now that returns those, so P5 does not re-implement the rule.
7. Money-like numbers use Decimal with quantize(Decimal("0.01")); never float arithmetic for totals.
DEBUGGING:
# print(f"[DEBUG] evaluation booking={booking_id} action={action} total={total} status={evaluation.status}")
OFFLINE DOCKER TEST CASES:
- Examiner B cannot evaluate a booking in examiner A's slot (get_owned_booking is None).
- save_draft with only one of two criteria stores the partial scores and total; submit with a missing criterion raises scores_incomplete and keeps the draft unchanged.
- score 61 on a criterion with max 60 raises score_out_of_range; total 101 with max_marks 100 raises total_exceeds_max.
- publish sets published_at and submitted_at; a second save raises evaluation_locked.
- Re-submitting a submitted evaluation updates scores and keeps one evaluation row per booking.
- pending_evaluations_count drops by one after submit and does not drop after save_draft.
- After an Admin changes the slot examiner from A to B, B can evaluate and the stored evaluations.examiner_id becomes B.
"""
EOF

# ================================ FORMS ==============================

cat << 'EOF' > app/forms/slot.py
"""
FILE PURPOSE: WTForms for creating and editing a slot (EXM-05).
DEPENDS ON: flask_wtf, wtforms, app/services/windows.py (from_local_input, to_input_value).
PROMPT FOR LLM IMPLEMENTATION:
1. SlotForm fields: examination_id (SelectField, coerce int, choices injected by the view from the examiner's assigned, non-deleted examinations as "Course code - Examination name"), start_at and end_at (StringField rendered as datetime-local, DataRequired), max_capacity (IntegerField, NumberRange 1-500, default 1).
2. to_service_data() returns (examination_id, start_at_utc, end_at_utc, max_capacity) using windows.from_local_input; bad text gives the field error "Enter a valid date and time". populate_from(slot) fills the form for editing.
3. Early cross-field check: end after start with the message "End time must be after start time." (the service stays authoritative).
4. On the edit screen the examination field is read-only (disabled select plus hidden value) because moving a slot between examinations is not allowed.
DEBUGGING:
# print(f"[DEBUG] SlotForm data={form.data} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- end_at equal to start_at gives the end-time message; capacity 0 and 501 are rejected.
- Local "2030-01-10T10:00" in Asia/Kolkata converts to 04:30 UTC.
- Changing the examination on edit is ignored (the stored examination stays).
"""
EOF

cat << 'EOF' > app/forms/evaluation.py
"""
FILE PURPOSE: Dynamic WTForms for the rubric evaluation page (EXM-08): one score and one comment per rubric criterion.
DEPENDS ON: flask_wtf, wtforms, app/models/rubric.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Provide build_evaluation_form(rubrics) that returns a FlaskForm subclass created with type(...) and setattr: for every rubric criterion add score_<rubric_id> (DecimalField, places 2, Optional, NumberRange 0..criterion.max_score, label "<criterion name> (max <max_score>)") and comment_<rubric_id> (StringField, Optional, Length max 300). Add remarks (TextAreaField, Optional, Length max 2000, label "Remarks for the student") and no other fields. The submit buttons are plain buttons named action with values save_draft, submit and publish, read from request.form in the view (they are not WTForms fields).
2. Provide helper extract_scores(form, rubrics) returning (scores, comments) dicts keyed by rubric_id for the service; empty score strings become None.
3. Field names MUST stay score_<id> and comment_<id> (TDR 5.1 contract) so the tests and templates can rely on them.
4. Field-level range errors are repeated in the service; the form is for early feedback only.
DEBUGGING:
# print(f"[DEBUG] evaluation form fields={[f.name for f in form]} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- For two criteria the form has score_1, score_2, comment_1, comment_2 and remarks.
- A score above the criterion maximum fails validation with a message that names the criterion.
- extract_scores turns "" into None and "12.50" into Decimal("12.50").
"""
EOF

# ========================= BLUEPRINT ROUTE MODULES ===================

cat << 'EOF' > app/blueprints/examiner/dashboard.py
"""
FILE PURPOSE: EXM-01 Examiner dashboard (assigned examinations, created slots, students booked, pending evaluations).
DEPENDS ON: examiner_bp (app/blueprints/examiner/__init__.py), approved_examiner_required, app/services/slot_service.py, app/services/evaluation_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /examiner/dashboard (endpoint dashboard) decorated with approved_examiner_required. Build the four counters from slot_service.examiner_dashboard_counts and evaluation_service.pending_evaluations_count for g.user.id.
2. Render examiner/dashboard.html with the four counter cards, the next five upcoming slots, and the first five pending evaluations (links to the evaluation form).
3. No queries or rules in the route beyond calling the services. Charts are added in P8.
DEBUGGING:
# print(f"[DEBUG] examiner dashboard user={g.user.id} counts={counts} pending={pending}")
OFFLINE DOCKER TEST CASES:
- The four counters match fixtures; another examiner's data never changes them.
- Pending examiner is redirected to /pending-approval; student and admin get 403.
"""
EOF

cat << 'EOF' > app/blueprints/examiner/examinations.py
"""
FILE PURPOSE: EXM-02 assigned examinations list and EXM-03 examination detail.
DEPENDS ON: examiner_bp, approved_examiner_required, app/services/slot_service.py, app/services/windows.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /examiner/examinations lists the examiner's assigned, non-deleted examinations with course code, type, status badge, slot-creation state (from slot_service.slot_creation_state) and the number of slots this examiner created for it. Filter by q and status; paginate.
2. GET /examiner/examinations/<id> shows the examination details (type, duration, maximum marks, dates via localdt), the read-only rubric criteria with weightage and max score, the examiner's own slots for it, and a "Create slot" button that is disabled with the reason line when slot creation is closed. An examination not assigned to this examiner returns 404.
3. Read-only: examiners never edit examination settings.
DEBUGGING:
# print(f"[DEBUG] examiner exams user={g.user.id} count={len(exams)}")
OFFLINE DOCKER TEST CASES:
- Only assigned examinations appear; an unassigned id returns 404.
- The Create slot button is disabled with "Slot creation opens on ..." before the window and enabled inside it.
"""
EOF

cat << 'EOF' > app/blueprints/examiner/slots.py
"""
FILE PURPOSE: EXM-04, EXM-05, EXM-06 slot list, create, edit, delete and booked students.
DEPENDS ON: examiner_bp, approved_examiner_required, app/forms/slot.py, app/forms/common.py (ConfirmForm), app/services/slot_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes (TDR 5.1): GET /examiner/slots (filters examination_id, status; pagination), GET /examiner/slots/new, POST /examiner/slots (create), GET /examiner/slots/<id>/edit, POST /examiner/slots/<id>/update, POST /examiner/slots/<id>/delete, GET /examiner/slots/<id>/students.
2. Every route that takes a slot id loads it with slot_service.get_owned_slot and aborts 404 when None (other examiners' slots are invisible). The new-slot form lists only assigned examinations; a forged examination_id yields the examination_not_found message and no row.
3. POST handlers: validate the form, call the service with actor g.user.id, flash success ("Slot created.", "Slot updated.", "Slot removed.") or the AppError/WindowError message (danger) and redirect (post/redirect/get). Form validation errors re-render with status 200.
4. The students page shows booked students (name, email, roll number, booking status, evaluation status badge and an Evaluate button linking to /examiner/bookings/<booking_id>/evaluate) plus the count of cancelled bookings.
5. Edit and Delete buttons are shown only when windows allow them (slots_editable) and the slot has no active bookings; otherwise a muted reason is shown instead.
DEBUGGING:
# print(f"[DEBUG] slots {request.method} {request.path} examiner={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Create inside the window works; outside the window flashes the slot_creation_closed message and creates nothing.
- Another examiner's slot id returns 404 for edit, update, delete and students.
- Editing at or after booking_start flashes slot_edit_locked.
- Overlapping slot flashes the examiner_overlap message with the conflicting time.
"""
EOF

cat << 'EOF' > app/blueprints/examiner/evaluations.py
"""
FILE PURPOSE: EXM-07, EXM-08, EXM-09 pending evaluations, evaluation form, submitted evaluations.
DEPENDS ON: examiner_bp, approved_examiner_required, app/forms/evaluation.py, app/services/evaluation_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /examiner/evaluations (pending list with filters examination_id and q; pagination), GET /examiner/evaluations/submitted (status filter submitted/published), GET and POST /examiner/bookings/<id>/evaluate.
2. The evaluate route loads the booking with evaluation_service.get_owned_booking (404 when None), builds the dynamic form from the examination's rubric (form_context), pre-fills existing scores/comments/remarks, and on POST reads the clicked button from request.form["action"] (save_draft, submit, publish; anything else is a 400). It extracts scores with extract_scores and calls evaluation_service.save_evaluation. Success flashes: "Draft saved.", "Evaluation submitted.", "Evaluation published to the student."; then redirect to the pending list (submit/publish) or back to the form (draft). AppError messages are flashed in danger and the form is re-rendered with the user's input.
3. When the evaluation is published or the examination has no rubric the page is read-only or shows an explanation; the Publish button appears only next to Submit and its helper text says the student can then see the result.
4. Show a live total using server-rendered text only (the total is recalculated on the server; no JavaScript in this milestone). A static line shows "Maximum marks: N".
DEBUGGING:
# print(f"[DEBUG] evaluate booking={booking_id} action={request.form.get('action')} scores={scores}")
OFFLINE DOCKER TEST CASES:
- Save draft, then submit with all criteria, then see it under submitted and gone from pending.
- A booking from another examiner's slot returns 404.
- An out-of-range score re-renders the form with the criterion-specific message and keeps all other inputs.
- Unknown action value returns 400.
- Published evaluation shows read-only values and no buttons.
"""
EOF

# ============================= TEMPLATES =============================

cat << 'EOF' > app/templates/examiner/base_examiner.html
<!--
FILE PURPOSE: Examiner layout with a top navbar (Design Plan section 2). Extends base.html by overriding the site_nav block.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html. Override site_nav with a Bootstrap navbar: brand "EMP", links Dashboard, Examinations, Slots, Evaluations (with a small badge of pending evaluations from a context value pending_count when provided), Profile, and a Logout POST form with csrf. Mark the active link with aria-current="page" from request.endpoint. Collapses to a hamburger below the lg breakpoint.
2. The default layout block from base.html is reused (flash messages and main content). Provide blocks page_title (h1) and page_actions in a small header row above content.
DEBUGGING:
<!-- DEBUG: examiner nav endpoint={{ request.endpoint }} -->
OFFLINE DOCKER TEST CASES:
- The nav shows exactly Dashboard, Examinations, Slots, Evaluations, Profile and Logout; the current link has aria-current.
-->
EOF

cat << 'EOF' > app/templates/examiner/dashboard.html
<!--
FILE PURPOSE: EXM-01 dashboard.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; page_title "Dashboard". Four counter cards (Assigned examinations, Slots created, Students booked, Pending evaluations - the last one highlighted when greater than zero and linking to the pending list).
2. Section "Upcoming slots": table with examination, start (localdt), seats booked/capacity, status badge, link to students. Section "Waiting for your evaluation": up to 5 rows with student, examination, Evaluate button. Empty states for both.
3. Reserve an empty div id="charts-widget" for P8 (comment only).
DEBUGGING:
<!-- DEBUG: counts {{ counts }} pending {{ pending }} -->
OFFLINE DOCKER TEST CASES:
- Counter values match the service output; empty states appear for a brand-new examiner.
-->
EOF

cat << 'EOF' > app/templates/examiner/examinations_list.html
<!--
FILE PURPOSE: EXM-02 assigned examinations.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; page_title "My examinations"; filter bar (q, status). Cards or table with course code, name (link), type, status badge, slot-creation state badge with its reason line, "My slots" count and a Create slot button (disabled with the reason when closed). Pager and empty state "You are not assigned to any examination yet."
DEBUGGING:
<!-- DEBUG: examinations {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- The disabled Create slot button carries aria-disabled and the reason text is visible.
-->
EOF

cat << 'EOF' > app/templates/examiner/examination_detail.html
<!--
FILE PURPOSE: EXM-03 examination detail for an examiner.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; header with name and status badge; summary list (course, type, duration, maximum marks, slot creation window and booking window via localdt); read-only rubric table; "My slots for this examination" table with status badges and links; Create slot button with the reason line when disabled.
DEBUGGING:
<!-- DEBUG: exam {{ exam.id }} my slots {{ slots|length }} -->
OFFLINE DOCKER TEST CASES:
- No edit controls for the examination itself appear anywhere on the page.
-->
EOF

cat << 'EOF' > app/templates/examiner/slots_list.html
<!--
FILE PURPOSE: EXM-04 own slots.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; page_title "My slots"; page_actions "Create slot". Filters: examination, status. Table: Examination, Start, End, Seats with a .slot-meter and text "3 / 5", Status badge (slot domain), Actions: Students link, Edit and Delete only when allowed (else a muted reason such as "Locked: booking has started"). Delete uses the confirm modal macro. Pager and empty state.
DEBUGGING:
<!-- DEBUG: slots {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- A full slot shows the Full badge; a slot with bookings shows no Edit or Delete buttons.
-->
EOF

cat << 'EOF' > app/templates/examiner/slot_form.html
<!--
FILE PURPOSE: EXM-05 create/edit slot.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; page_title "Create slot" or "Edit slot". Form posts to /examiner/slots (create) or /examiner/slots/<id>/update (edit) with csrf; fields: Examination (select; read-only on edit), Start, End (datetime-local with required), Capacity (number input min 1 max 500). Help text shows the examination's slot-creation window and the configured timezone.
2. A top alert shows service errors (overlap, window closed). Save and Cancel buttons.
DEBUGGING:
<!-- DEBUG: slot form errors {{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- Capacity input has min and max attributes; on edit the examination select is disabled.
-->
EOF

cat << 'EOF' > app/templates/examiner/slot_students.html
<!--
FILE PURPOSE: EXM-06 booked students of one slot.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; slot summary (examination, start/end, seats, status); table: Student, Email, Roll number, Booking status badge, Evaluation badge (none / draft / submitted / published), Evaluate button; muted line "N cancelled bookings not shown"; empty state "No students have booked this slot yet."
DEBUGGING:
<!-- DEBUG: slot {{ slot.id }} students {{ bookings|length }} -->
OFFLINE DOCKER TEST CASES:
- Cancelled bookings are not listed but are counted in the muted line.
-->
EOF

cat << 'EOF' > app/templates/examiner/evaluations_pending.html
<!--
FILE PURPOSE: EXM-07 pending evaluations.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; page_title "Pending evaluations"; filter bar (examination, student q); table: Student, Examination, Slot time, Draft saved indicator, Evaluate button. Tabs/links to "Submitted evaluations". Pager and empty state "Nothing waiting for evaluation."
DEBUGGING:
<!-- DEBUG: pending {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- A booking with a draft shows the Draft badge; submitting removes it from this list.
-->
EOF

cat << 'EOF' > app/templates/examiner/evaluation_form.html
<!--
FILE PURPOSE: EXM-08 rubric evaluation form.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; header with student name, examination, slot time and the evaluation status badge.
2. Form with csrf: a table with one row per criterion (Criterion + description, Weightage, Maximum, score_<id> number input with class score-input, step 0.01, min 0, max = criterion max, comment_<id> text input), then Remarks textarea, a read-only line "Total: X of Maximum marks N", then buttons: Save draft (secondary), Submit (primary), Submit and publish (success). Buttons are type submit with name action and the values save_draft, submit, publish. Each button has helper text below the form: draft is private, submit finalises, publish shows it to the student.
3. Read-only mode (published evaluation, or no rubric): values rendered as text, an info alert, no buttons.
4. Field-level errors use render_field/invalid-feedback and an error summary at the top with links to the fields.
DEBUGGING:
<!-- DEBUG: evaluation booking {{ booking.id }} status {{ evaluation.status if evaluation else 'new' }} -->
OFFLINE DOCKER TEST CASES:
- The form has score_ and comment_ inputs for every criterion and three action buttons.
- Published evaluation renders without any input element.
-->
EOF

cat << 'EOF' > app/templates/examiner/evaluations_submitted.html
<!--
FILE PURPOSE: EXM-09 submitted evaluations.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base_examiner.html; page_title "Submitted evaluations"; status filter links (All, Submitted, Published); table: Student, Examination, Total / maximum, Status badge, Submitted (localdt), Published (localdt or dash), View/Edit link (Edit only while status is submitted). Pager and empty state.
DEBUGGING:
<!-- DEBUG: submitted {{ page.total }} -->
OFFLINE DOCKER TEST CASES:
- Published rows have no Edit link; submitted rows do.
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_slot_service.py
"""
FILE PURPOSE: Rule tests for slot_service (windows, ownership, overlap, capacity, counts).
DEPENDS ON: app/services/slot_service.py, tests/conftest.py (freeze_now, make_ready_examination, make_booking_with_slot).
PROMPT FOR LLM IMPLEMENTATION:
1. Window tests: test_create_fails_before_window_opens, test_create_ok_at_window_start_and_end_inclusive, test_create_fails_after_window, test_create_fails_when_switch_off.
2. Rule tests: test_create_requires_assignment, test_create_rejects_past_start, test_create_rejects_bad_time_range, test_create_capacity_bounds (0, 1, 500, 501), test_create_overlap_refused_back_to_back_allowed, test_overlap_checked_across_examinations, test_unapproved_or_inactive_examiner_refused.
3. Update/delete: test_update_locked_at_booking_start, test_update_ok_one_second_before, test_update_refused_with_active_booking, test_update_excludes_self_in_overlap, test_delete_hard_when_no_bookings, test_delete_turns_cancelled_with_cancelled_booking_history, test_delete_refused_with_active_booking.
4. Ownership/lists/counts: test_get_owned_slot_none_for_other_examiner, test_list_slots_filters_and_order, test_booked_students_excludes_cancelled_and_counts_them, test_dashboard_counts_scoped_to_examiner, test_audit_rows_written_for_create_update_delete.
5. Assert stable error codes, never message text. Use freeze_now for every clock-dependent test.
DEBUGGING:
# print(f"[DEBUG] slot rule case {name}: code={code}")
OFFLINE DOCKER TEST CASES:
- 27 tests pass offline; removing assert_slots_editable from update_slot makes test_update_locked_at_booking_start fail.
"""
EOF

cat << 'EOF' > tests/unit/test_evaluation_service.py
"""
FILE PURPOSE: Rule tests for evaluation_service.
DEPENDS ON: app/services/evaluation_service.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Eligibility: test_owned_booking_only, test_cancelled_booking_not_evaluable, test_cancelled_slot_not_evaluable, test_pending_list_excludes_submitted_includes_drafts, test_pending_count_changes_on_submit_not_on_draft.
2. Validation: test_score_range_per_criterion, test_total_cannot_exceed_max_marks, test_submit_requires_all_criteria, test_draft_may_be_partial, test_unknown_rubric_id_rejected, test_no_rubric_examination_refused, test_remarks_length_limit.
3. Lifecycle: test_draft_submit_publish_timestamps, test_resubmit_before_publish_updates_scores_single_row, test_published_is_immutable, test_total_uses_decimal_exactly (0.1 + 0.2 style case yields 0.30), test_examiner_id_follows_acting_examiner_after_slot_reassignment, test_published_for_student_returns_only_published.
4. test_audit_rows_for_save_submit_publish.
DEBUGGING:
# print(f"[DEBUG] evaluation case {name}: status={evaluation.status if evaluation else None} total={total}")
OFFLINE DOCKER TEST CASES:
- 20 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_examiner_access_ownership.py
"""
FILE PURPOSE: Proves examiner routes are role-locked and ownership-scoped (risk R-4, R-5).
DEPENDS ON: tests/conftest.py (examiner_client, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. Build the list of /examiner URLs from app.url_map (like the admin access test) and run a parametrised matrix: anonymous -> 302 /login; student and admin -> 403; pending examiner -> 302 /pending-approval; rejected examiner -> 302 /pending-approval; deactivated examiner -> 302 /account-inactive; approved examiner -> not 403 and not 500.
2. Ownership tests with two approved examiners A and B: B gets 404 for A's slot on edit, update, delete and students; B gets 404 for evaluating a booking in A's slot; B cannot see A's slots in lists; B gets 404 for an examination B is not assigned to.
3. test_flag_flip_takes_effect_next_request (approval to pending, is_active to False) and test_forged_examination_id_on_create_refused.
DEBUGGING:
# print(f"[DEBUG] {method} {url} as {role} -> {response.status_code}")
OFFLINE DOCKER TEST CASES:
- Matrix covers every /examiner rule at collection time; new routes are covered automatically.
"""
EOF

cat << 'EOF' > tests/integration/test_examiner_slots_routes.py
"""
FILE PURPOSE: HTTP tests for EXM-02 to EXM-06.
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_examinations_list_only_assigned, test_create_slot_disabled_button_reason_before_window, test_create_slot_flow_in_window (form post with local times, DB row has UTC), test_create_slot_outside_window_flash, test_overlap_flash_with_time, test_edit_prefills_local_time, test_edit_locked_after_booking_start_flash, test_delete_confirm_flow, test_slot_with_booking_hides_edit_delete, test_students_page_lists_booked_only, test_pagination_keeps_filters.
2. Assert flash text and database state in every test; use freeze_now to place the clock before, inside and after the windows.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} flashes={flashes}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_examiner_evaluation_flow.py
"""
FILE PURPOSE: HTTP tests for EXM-01 and EXM-07 to EXM-09 plus the milestone acceptance flow.
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_dashboard_counters_values, test_pending_list_and_filter, test_evaluation_form_has_inputs_per_criterion, test_save_draft_keeps_in_pending, test_submit_moves_to_submitted_and_decrements_counter, test_publish_makes_read_only, test_out_of_range_score_message_keeps_input, test_unknown_action_400, test_no_rubric_message, test_submitted_list_edit_only_for_submitted.
2. Acceptance test test_examiner_milestone_acceptance: Admin-prepared fixtures; examiner logs in, creates a slot inside the window, cannot edit it at booking_start, a booking made by factory appears under students, evaluates it (draft -> submit -> publish) and the dashboard counters change accordingly; another examiner never sees any of it.
DEBUGGING:
# print(f"[DEBUG] step={step} {response.status_code} {response.headers.get('Location')}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P4 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P4_update_existing_files.md section by section (examiner/__init__.py, audit_service.py, conftest.py, app.css) with the CURRENT files."
echo "2. Run 'docker compose --profile test run --rm test' (or 'make test-core'), then log in as an approved examiner and create a slot inside the window."
echo "3. Run 'git add . && git commit -m \"wip: P4 examiner slots and evaluation\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p4-examiner-slots-evaluation && git commit -m \"Milestone-4 EMP-Examiner-Slots-Evaluation\" && git tag p4-done && git push origin main --tags'."
echo "5. Decisions to confirm (not in the PDR): evaluation has no time restriction; published evaluations are immutable; slots with active bookings cannot be cancelled until P6."
echo "6. Execute P5.sh"
echo "====================================================="
