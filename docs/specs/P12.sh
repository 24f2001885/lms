#!/usr/bin/env bash
# =====================================================================
# P12.sh - Phase P12: Scorecard & Email Notifications (Tier 2, last phase)
# Course commit message : Milestone-12 EMP-Scorecard-Email
# Branch                : phase/p12-scorecard-email
# Depends on            : P11 (tag p11-done), P7 and P9 (via the sequence), Gate A
# Source of truth       : PDR 2.2/5.7 (scorecard download, email notifications),
#                         PDR 14.2 (notification templates), TDR 4.2 (email_logs),
#                         TDR 8.1 (Flask-Mail, background thread, email_logs),
#                         TDR 11 (retry-failed-emails, retention), Master Blueprint
#                         2.3 (Gate B) and 3.2 (P12 row)
# Acceptance            : emails are recorded in email_logs; the PDF downloads for
#                         published results; an email failure never blocks a booking.
# This phase also seeds the Tier 2 closing tools: verify_gate_b.sh, the submission
# zip builder, the report facts generator and the Tier 2 demo/traceability docs.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P12_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P12"
BRANCH="phase/p12-scorecard-email"
PREV_TAG="p11-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P11 first."; exit 1; }
git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || { echo "GATE A CLOSED: tag tier1-complete is missing."; exit 1; }
[ -f app/security/rate_limit.py ] || { echo "ERROR: app/security/rate_limit.py missing (P11 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
bash scripts/check_gate.sh "$BRANCH" || { echo "ERROR: gate check refused this branch."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P12 needs)
# ---------------------------------------------------------------------
mkdir -p app/models app/services app/blueprints/student
mkdir -p app/templates/emails app/static/vendor/fonts
mkdir -p scripts docs docs/report docs/seed_updates
mkdir -p tests/unit tests/integration tests/e2e

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P12_update_existing_files.md
<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P12 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file. Apply the sections in order.

DESIGN SUMMARY (read first)
- Tier 1 services never import the mailer. They announce what happened by emitting a DOMAIN EVENT after the database commit (new small API in app/services/hooks.py). The mailer registers handlers for those events at start-up. If mail is switched off or fails, the business action has already been committed and is unaffected (acceptance: "an email failure never blocks a booking").
- Emails are plain text, transactional, contain no passwords, no temporary passwords, no marks and no admin cancellation reasons (same redaction rule as the booking timeline for students).
- email_logs keeps what was attempted so failed emails can be retried by a job.

SECTION 1: requirements-tier2.txt and requirements-dev.txt
1. requirements-tier2.txt: add Flask-Mail and ReportLab pinned with == to the latest stable releases for Python 3.11/3.12 (under the "# Tier 2" comment, alphabetical). requirements-dev.txt: add pypdf (pinned, used only by tests to read text from generated PDFs); aiosmtpd is already there.

SECTION 2: app/config.py
1. Add settings from the environment: MAIL_SERVER (localhost), MAIL_PORT (1025), MAIL_USE_TLS (false), MAIL_USERNAME and MAIL_PASSWORD (empty), MAIL_DEFAULT_SENDER (emp@example.edu), MAIL_SUPPRESS_SEND (true in DevConfig and TestConfig, taken from the environment in ProdConfig), MAIL_ASYNC (true; TestConfig false so tests are deterministic), MAIL_MAX_ATTEMPTS (3), EMAIL_LOG_RETENTION_DAYS (90), APP_BASE_URL (http://127.0.0.1:5000, used to build absolute links inside emails because no request exists in a background thread), INSTITUTION_NAME ("Examination Management Portal"), SCORECARD_DETERMINISTIC (false; TestConfig true so PDFs are reproducible).
2. MAIL_PASSWORD is never logged or printed. ProdConfig refuses MAIL_SUPPRESS_SEND false with an empty MAIL_SERVER.

SECTION 3: app/extensions.py
1. Add mail = Mail() (Flask-Mail) and call mail.init_app(app) inside init_extensions(app). Nothing else changes.

SECTION 4: app/models/__init__.py
1. Import EmailLog (new file app/models/email_log.py) after AuditLog and add it to __all__. Add TIER2_TABLE_NAMES = ("email_logs",) next to ALL_TABLE_NAMES (which keeps the 12 Tier 1 names).

SECTION 5: app/cli.py
1. Add EXPECTED_TIER2_TABLES = ("email_logs",). init-db now reports "Tier 1 tables: 12, Tier 2 tables: 1" and warns for missing tables of either tier (a missing Tier 2 table is a warning, not an error).
2. In the jobs group add retry-failed-emails (option --max-attempts, default from config; calls mailer.retry_failed and prints the summary) and purge-email-logs (option --days, default EMAIL_LOG_RETENTION_DAYS; calls mailer.purge_old and prints the number deleted). Both are idempotent and exit 0 when there is nothing to do.

SECTION 6: tests and scripts that assumed exactly 12 tables
1. tests/integration/test_init_db_and_pragmas.py: test_init_db_creates_exactly_12_tables becomes test_init_db_creates_12_tier1_and_1_tier2_tables (13 tables, email_logs present); the "no Tier 3 table" assertion stays (email_logs is Tier 2). tests/unit/test_models_*.py: add nothing.
2. scripts/verify_gate_a.sh, check 6 (clean init-db): assert that the 12 Tier 1 table names EXIST (subset check) instead of requiring exactly 12 tables, and that no Tier 3 table exists; keep the other checks. The MAIL variable check of check 8 applies only before Tier 2: skip it when the tag p7-done exists.

SECTION 7: app/services/hooks.py (domain events)
1. Add, next to the two existing hook lists, a tiny event API: register_event(name, fn) (ignore duplicates), emit(name, **payload) and clear_events(). emit calls every handler registered for that name synchronously, in registration order, passing the payload as keyword arguments; exceptions are caught, logged with logger.exception (never the payload values) and never propagate. Event names as module constants: EVENT_BOOKING_CREATED = "booking.created", EVENT_BOOKING_CANCELLED = "booking.cancelled", EVENT_BOOKING_RESCHEDULED = "booking.rescheduled", EVENT_EXAMINER_APPROVED = "examiner.approved", EVENT_EVALUATION_PUBLISHED = "evaluation.published".
2. Payloads carry ONLY ids and short enums: booking_id, student_id, slot_id, examiner_id, evaluation_id, by ("student", "admin", "slot"). No names, no emails, no reasons.
3. The existing pre_booking_hooks and post_cancel_hooks (Tier 3 uses them) are unchanged.

SECTION 8: services that emit events (AFTER their commit, nothing else changes)
1. app/services/booking_engine.py: book_slot emits EVENT_BOOKING_CREATED(booking_id, student_id); cancel_booking emits EVENT_BOOKING_CANCELLED(booking_id, student_id, by="student"); admin_cancel_booking emits it with by="admin"; cancel_slot emits it once per cancelled booking with by="slot"; reschedule_booking emits EVENT_BOOKING_RESCHEDULED(booking_id, student_id, from_slot_id, to_slot_id).
2. app/services/admin_service.py: approve_examiner emits EVENT_EXAMINER_APPROVED(examiner_id).
3. app/services/evaluation_service.py: save_evaluation with action publish and admin_publish emit EVENT_EVALUATION_PUBLISHED(evaluation_id, booking_id, student_id).
4. A failure inside emit can never change the return value or raise out of these functions (emit swallows errors).

SECTION 9: app/__init__.py
1. After init_extensions call mailer.register_event_handlers() (module app/services/mailer.py) so the handlers exist in every process; keep create_app free of database access and of any network access.

SECTION 10: app/blueprints/student/__init__.py, templates/student/result_detail.html, templates/student/booking_detail.html
1. student/__init__.py: add the import of the new module scorecard (with "# noqa: E402,F401").
2. result_detail.html: fill the Jinja block result_actions (empty since P5) with a button-styled link "Download scorecard (PDF)" to /student/bookings/<id>/scorecard.pdf with the file-type hint "(PDF)" in the link text; booking_detail.html shows the same link only when the result is published.

SECTION 11: app/blueprints/admin/history.py and templates/admin/history.html
1. Add the fifth tab "emails" (read-only): time, recipient, template, status badge (sent green, failed red, queued yellow), attempts, error message (trimmed), with filters status and template and the usual pager. The email body is never shown. Update the tests that expected four tabs to expect five.

SECTION 12: app/services/audit_service.py
1. Add constants SCORECARD_DOWNLOAD = "scorecard.download", SYSTEM_EMAIL_RETRY = "system.email_retry", SYSTEM_EMAIL_PURGE = "system.email_purge".

SECTION 13: scripts/seed_demo_data.py
1. While seeding, force mail into synchronous suppressed mode (restore afterwards) so no thread or SMTP is involved; print how many email_logs rows were created. The demo data keeps at least one published result so the scorecard can be downloaded.

SECTION 14: .env.example, .gitignore, Makefile, pyproject.toml, README.md, docs
1. .env.example: add MAIL_SERVER=localhost, MAIL_PORT=1025, MAIL_USE_TLS=false, MAIL_USERNAME=, MAIL_PASSWORD=, MAIL_DEFAULT_SENDER=emp@example.edu, MAIL_SUPPRESS_SEND=true, MAIL_ASYNC=true, MAIL_MAX_ATTEMPTS=3, EMAIL_LOG_RETENTION_DAYS=90, APP_BASE_URL=http://127.0.0.1:5000 with one comment each (placeholders only). No ENABLE_* flag and no RAZORPAY variable may appear.
2. .gitignore: add submission_core.zip and docs/report/generated_facts.md is NOT ignored (it is a deliverable).
3. Makefile: targets mail-sink (python -m aiosmtpd -n -l localhost:1025), test-mail (pytest -m mail), test-scorecard (pytest -m scorecard), report-facts (python scripts/report_facts.py), submission (bash scripts/build_submission.sh), gate-b (bash scripts/verify_gate_b.sh).
4. pyproject.toml: register markers mail and scorecard. README.md: sections "Email notifications" (templates, log, retry job, local sink), "Scorecard PDF", "Gate B and submission" (make gate-b, make submission). docs/ai_llm_declaration.md: add rows for P7 to P12.
5. app/static/vendor/README.md: add the optional font entry: app/static/vendor/fonts/DejaVuSans.ttf and DejaVuSans-Bold.ttf (free licence, download once while online, keep the licence text next to the files); without them the scorecard falls back to Helvetica and replaces unsupported characters.

SECTION 15: tests/conftest.py
1. Add fixture mail_outbox (Flask-Mail record_messages) and sync_mail (sets MAIL_ASYNC false and MAIL_SUPPRESS_SEND false inside the test so messages are recorded); fixture smtp_failure(exception) that makes mail.send raise; helper read_pdf_text(bytes) using pypdf; helper make_published_result(student) that creates a published evaluation with scores.
DEBUGGING:
# print("[DEBUG] applied P12 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the complete P0-P11 suite passes (only the three table-count/tab-count tests change).
- Booking a slot with mail switched on creates one email_logs row with status sent (or failed when SMTP is broken) and the booking exists either way.
- GET /student/bookings/<id>/scorecard.pdf for a published result returns a PDF.
-->
EOF

# =============================== MODELS ==============================

cat << 'EOF' > app/models/email_log.py
"""
FILE PURPOSE: Table "email_logs" (Tier 2): one row per email that the system tried to send, so failures are visible and can be retried (TDR 4.2).
DEPENDS ON: app/extensions.py (db).
PROMPT FOR LLM IMPLEMENTATION:
1. Class EmailLog(db.Model), __tablename__ = "email_logs", sqlite_autoincrement. Columns from TDR 4.2: id PK; to_email TEXT not null; template TEXT not null (for example "booking_confirmed"); status TEXT not null with CheckConstraint status_valid in ("queued","sent","failed") (constant EMAIL_STATUSES); error_message TEXT null (at most 300 characters, never a stack trace, never a password); related_entity_type TEXT null; related_entity_id INTEGER null; created_at DATETIME not null server_default current_timestamp; sent_at DATETIME null.
2. v2.1 ADDITIONS to the TDR table (note them in a comment "TDR 4.2 update"), needed so a failed email can be retried and shown: subject TEXT not null; body_text TEXT not null; attempts INTEGER not null default 0 with CheckConstraint attempts_non_negative; last_attempt_at DATETIME null.
3. Indexes: ix_email_logs_status_created_at on (status, created_at); ix_email_logs_related on (related_entity_type, related_entity_id).
4. No relationships and no foreign keys (a log row must survive deletion of anything it refers to). No business logic; a read-only property is_terminal_failure(max_attempts) is allowed.
5. Declare that the recipient address is personal data: retention is 90 days (purge job) and the Admin history tab never shows the body.
DEBUGGING:
# print(f"[DEBUG] EmailLog {self.id} {self.template} -> {self.status} attempts={self.attempts}")
OFFLINE DOCKER TEST CASES:
- status "pending" raises IntegrityError; attempts -1 raises IntegrityError.
- A row with only the required columns stores status "queued" only when the service sets it (no default hidden in the model).
- The table exists after init-db and is the only Tier 2 table; no Tier 3 table exists.
"""
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/mailer.py
"""
FILE PURPOSE: Builds, logs, sends and retries the transactional emails (TDR 8.1). Sending happens AFTER the business commit, in a background thread, and can never break or roll back the action that caused it.
DEPENDS ON: flask_mail (Message), app/extensions.py (mail, db), app/models/email_log.py, app/services/hooks.py (register_event and the event constants), app/services/windows.py (now_utc, to_local), app/services/audit_service.py, app/templates/emails/*.txt, app config (MAIL_*, APP_BASE_URL, INSTITUTION_NAME).
PROMPT FOR LLM IMPLEMENTATION:
1. Template registry EMAIL_TEMPLATES: name -> {"subject": str with placeholders, "file": "emails/<name>.txt"} for exactly five templates (TDR 8.1): booking_confirmed, booking_cancelled, booking_rescheduled, examiner_approved, result_published.
2. build_message(template, context) -> (subject, body): render the text template with Flask's template engine (the .txt files are not auto-escaped, so the code must never put HTML or user-controlled text into the subject unsanitised); strip carriage returns and line feeds from the subject, collapse whitespace, limit it to 150 characters; the body ends with the shared footer. Unknown template names raise KeyError.
3. queue_email(template, to_email, context, related=(entity_type, entity_id)) -> int | None: validate the recipient with a simple address check (reject anything containing CR, LF, comma or more than one @; return None and log a WARNING without the address), create the EmailLog row (status "queued", attempts 0, subject, body_text), commit it in its OWN short transaction, then call dispatch(log_id) and return the id. This function is only ever called after the business transaction has committed.
4. dispatch(log_id): when MAIL_ASYNC is true start a daemon thread (threading.Thread) that runs _send_with_context(app_object, log_id) where app_object = current_app._get_current_object() (a request or app context must exist); when false call it directly. _send_with_context pushes an app context, calls attempt_send and ALWAYS calls db.session.remove() in a finally block.
5. attempt_send(log_id) -> str (the final status): load the row; if it is already "sent" return "sent" (idempotent); increment attempts, set last_attempt_at, build a flask_mail.Message from the row (subject, recipients, body, sender from MAIL_DEFAULT_SENDER) and call mail.send. When MAIL_SUPPRESS_SEND is true Flask-Mail skips the SMTP call: record status "sent", sent_at now and error_message "suppressed (MAIL_SUPPRESS_SEND)". On success status "sent" and sent_at. On ANY exception set status "failed" and error_message to the exception class name plus a trimmed message of at most 300 characters with credentials removed; log a WARNING containing the template and attempt number but never the recipient or the body; commit each state change separately; never re-raise.
6. retry_failed(max_attempts=None, limit=100, now=None) -> dict {"considered": n, "sent": n, "still_failed": n}: select rows with status "failed" and attempts below max_attempts (config MAIL_MAX_ATTEMPTS, default 3), plus rows still "queued" older than 15 minutes (a thread that died with the process), oldest first, call attempt_send synchronously for each; a row that reaches the maximum stays "failed" (terminal). Write one audit row SYSTEM_EMAIL_RETRY (actor null) with the summary when anything was considered.
7. purge_old(days=None, now=None) -> int: delete rows older than the retention (EMAIL_LOG_RETENTION_DAYS) whose status is "sent" or which are terminal failures; never delete "queued" or retryable rows; audit SYSTEM_EMAIL_PURGE with the count; days must be a positive integer (ValueError otherwise).
8. register_event_handlers(): register one handler per domain event with hooks.register_event (idempotent): on_booking_created, on_booking_cancelled, on_booking_rescheduled, on_examiner_approved, on_evaluation_published. Each handler receives only ids, loads what it needs in a fresh query, skips silently when the recipient is inactive or has no email, builds the context and calls queue_email. Context rules: dates and times via windows.to_local with the timezone abbreviation; absolute links as APP_BASE_URL + path (/student/bookings, /student/results/<booking_id>, /login); booking_confirmed: student name, examination name and course code, slot start and end, examiner name, booking id, cancellation deadline; booking_cancelled: the three variants selected by "by" (own cancellation, "cancelled by the administration", "the slot was cancelled") and NEVER the admin reason; booking_rescheduled: old and new slot times and the new examiner; examiner_approved: name and the login link; result_published: examination name and date and the link, NEVER marks or remarks.
9. Privacy and safety rules: no password, temporary password, token or CSRF value ever appears in a subject, body or log row; the module never imports anything from a blueprint; no network access except through Flask-Mail.
DEBUGGING:
# print(f"[DEBUG] mailer {action} log_id={log_id} template={template} status={status} attempts={attempts}")
OFFLINE DOCKER TEST CASES:
- queue_email creates a "queued" row and, with MAIL_ASYNC false and Flask-Mail recording, one outbox message whose subject and body equal the stored subject and body_text; the row becomes "sent".
- With mail.send raising an exception the row ends "failed" with attempts 1 and a trimmed error_message, the caller sees no exception, and retry_failed later sends it (attempts 2, status "sent").
- A row that failed MAIL_MAX_ATTEMPTS times stays failed and is not retried again; a "queued" row older than 15 minutes is retried; a younger one is not.
- A recipient with a newline or a comma is rejected and no row is created; a subject containing a newline is sanitised.
- Booking cancelled by the admin produces text without the reason; result_published contains no digits from the marks.
- purge_old deletes only old sent or terminal rows and returns the count; days=0 raises ValueError.
- The 5 templates render with a realistic context and contain the footer and no unreplaced placeholders.
- 20 emails queued from 20 threads each create exactly one row and one send attempt.
"""
EOF

cat << 'EOF' > app/services/scorecard.py
"""
FILE PURPOSE: Builds the examination scorecard PDF for ONE published result (PDR 5.7, TDR 5.2 route /student/bookings/<id>/scorecard.pdf). Pure function: no request, no response objects.
DEPENDS ON: reportlab (platypus, pdfbase.ttfonts), app/models, app/services/student_queries.py (result_detail: only published evaluations), app/services/windows.py (to_local, format_local), app config (INSTITUTION_NAME, SCORECARD_DETERMINISTIC), vendored fonts in app/static/vendor/fonts/.
PROMPT FOR LLM IMPLEMENTATION:
1. build_scorecard(student_id, booking_id) -> tuple[bytes, str] | None: returns None (the route turns it into 404) unless the booking belongs to the student AND its evaluation has status "published" (reuse student_queries.result_detail so the visibility rule exists once). Otherwise returns (pdf_bytes, filename) with filename "scorecard-<ascii slug of the examination name, max 40 chars>-<booking_id>.pdf".
2. Layout (A4 portrait, ReportLab platypus, one page for up to about 12 criteria, repeatRows header and automatic continuation beyond that): title "Examination Scorecard" and the institution name; a two-column details block (student name, roll number if any, programme, course code and name, examination name and type, slot date and time in local time with the timezone abbreviation, examiner name, booking id); a criteria table (Criterion, Weightage %, Maximum, Score, Comment) with the comment column wrapping; a totals row "Total X of Y" and "Percentage Z %" (1 decimal, exact Decimal arithmetic); a "Feedback" paragraph with the remarks (omitted when empty); a footer line "Generated on <local date time> - Reference EMP-<booking id>-<examination id>" and "Page n of N".
3. Fonts: when DejaVuSans.ttf and DejaVuSans-Bold.ttf exist in app/static/vendor/fonts register and use them (covers accented Latin names); otherwise fall back to the built-in Helvetica and replace characters the font cannot encode with "?" so generation NEVER fails because of a name. Devanagari and other non-Latin scripts are a documented limitation (record it in the README known issues).
4. Metadata: title "Scorecard - <examination name>", author = institution name, subject "Examination result"; no JavaScript, no embedded files, no form fields, no external links. When SCORECARD_DETERMINISTIC is true use ReportLab's invariant mode and fixed creation date so tests can compare bytes; otherwise normal output.
5. All text comes from the database through escaped paragraphs (escape &, <, > before passing to Paragraph so user text can never inject markup); numbers are formatted by one helper (no float rounding surprises); never include the password hash, email address or any evaluator internals.
6. Return quickly: for the maximum realistic size (30 criteria, 1000-character remarks) generation stays under 500 ms.
DEBUGGING:
# print(f"[DEBUG] scorecard booking={booking_id} rows={len(rows)} bytes={len(pdf_bytes)} font={font_name}")
OFFLINE DOCKER TEST CASES:
- The bytes start with %PDF- and end with %%EOF; pypdf reads one page and the extracted text contains the student name, the examination name, every criterion, the total line and the reference.
- A draft, a submitted-but-unpublished evaluation, another student's booking and an unknown id all return None.
- A name with accents and an examination name containing <b>&</b> render without error and without markup being interpreted; a missing font file falls back to Helvetica without raising.
- 30 criteria and a 1000-character remark produce a valid multi-page-safe PDF under 500 ms.
- Two runs with SCORECARD_DETERMINISTIC true give identical bytes.
- Percentage is 62.5 for 25 of 40 and has exactly one decimal.
"""
EOF

# ======================= BLUEPRINT ROUTE MODULE ======================

cat << 'EOF' > app/blueprints/student/scorecard.py
"""
FILE PURPOSE: The scorecard download route for students (the TDR 5.2 "T2 extra").
DEPENDS ON: student_bp, student_required, app/services/scorecard.py, app/services/audit_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/bookings/<id>/scorecard.pdf (endpoint scorecard) with student_required. Call scorecard.build_scorecard(g.user.id, id); None means abort(404) (identical for a foreign booking, an unknown id and an unpublished result so nothing is leaked).
2. Return the bytes with Content-Type application/pdf, Content-Disposition attachment with both filename and filename* (UTF-8 encoded) parameters, Cache-Control private, no-store and Content-Length. Write the audit row SCORECARD_DOWNLOAD (actor the student, entity booking) and commit before returning; a failure to write the audit row must not prevent the download but is logged.
3. Only GET is allowed; there is no admin or examiner variant in Tier 2 (recorded in the decisions).
DEBUGGING:
# print(f"[DEBUG] scorecard download user={g.user.id} booking={id} found={result is not None}")
OFFLINE DOCKER TEST CASES:
- Student downloads a published result: 200, application/pdf, attachment header, body starts with %PDF-.
- Another student, an unpublished result, an unknown id: 404; examiner and admin: 403; anonymous: 302 to /login.
- An audit row scorecard.download exists after the download.
"""
EOF

# ============================= EMAIL TEMPLATES =======================

cat << 'EOF' > app/templates/emails/_footer.txt
{#
FILE PURPOSE: Shared footer included at the end of every email body.
PROMPT FOR LLM IMPLEMENTATION:
1. Plain text, three lines: a blank line, "This is an automated message from {{ institution }}. Please do not reply to it." and "If you did not expect this email, contact your administrator." No links, no tracking, no HTML.
DEBUGGING:
DEBUG (add as a Jinja comment while debugging): footer institution={{ institution }}
OFFLINE DOCKER TEST CASES:
- Every rendered email ends with this footer.
#}
EOF

cat << 'EOF' > app/templates/emails/booking_confirmed.txt
{#
FILE PURPOSE: Email to a student after a booking is confirmed (PDR 14.2 "Booking Confirmed").
PROMPT FOR LLM IMPLEMENTATION:
1. Plain text body. Greeting "Hello {{ student_name }},". One sentence "Your booking is confirmed." Then labelled lines: Examination ({{ examination_name }}, {{ course_code }}), Date and time ({{ slot_start }} to {{ slot_end }} {{ tz }}), Examiner ({{ examiner_name }}), Booking number ({{ booking_id }}), Cancel until ({{ cancel_deadline }} {{ tz }}). A line "View your bookings: {{ link }}". Then include _footer.txt.
2. Context keys exactly as produced by mailer.on_booking_created; no other data, no emails or ids of other people.
DEBUGGING:
DEBUG (add as a Jinja comment while debugging): booking_confirmed booking={{ booking_id }}
OFFLINE DOCKER TEST CASES:
- Renders with all placeholders replaced, under 25 lines, ASCII-safe line endings.
#}
EOF

cat << 'EOF' > app/templates/emails/booking_cancelled.txt
{#
FILE PURPOSE: Email to a student when a booking is cancelled (PDR 14.2 "Booking Cancelled").
PROMPT FOR LLM IMPLEMENTATION:
1. Plain text body with three variants chosen by the variable by: "student" ("You cancelled your booking. Your seat has been released."), "admin" ("Your booking was cancelled by the administration."), "slot" ("The slot you booked was cancelled."). NEVER include a reason or the name of the person who cancelled.
2. Then labelled lines: Examination, Original date and time, Booking number, and for the admin and slot variants a sentence "You can book another slot while booking is open: {{ link }}". Then include _footer.txt.
DEBUGGING:
DEBUG (add as a Jinja comment while debugging): booking_cancelled by={{ by }}
OFFLINE DOCKER TEST CASES:
- Each variant renders; none contains the word "reason".
#}
EOF

cat << 'EOF' > app/templates/emails/booking_rescheduled.txt
{#
FILE PURPOSE: Email to a student when the administration moves their booking (PDR 14.2 "Rescheduled").
PROMPT FOR LLM IMPLEMENTATION:
1. Plain text body: "Your booking was moved to a different slot by the administration." Then lines: Examination, Previous time ({{ old_start }} {{ tz }}), New time ({{ new_start }} to {{ new_end }} {{ tz }}), New examiner ({{ examiner_name }}), Booking number. A link to the bookings page. Then include _footer.txt. No reason, no admin identity.
DEBUGGING:
DEBUG (add as a Jinja comment while debugging): booking_rescheduled booking={{ booking_id }}
OFFLINE DOCKER TEST CASES:
- Old and new times differ in the rendered text; the footer is present.
#}
EOF

cat << 'EOF' > app/templates/emails/examiner_approved.txt
{#
FILE PURPOSE: Email to an examiner when the Admin approves the account (PDR 14.2 "Examiner Approved").
PROMPT FOR LLM IMPLEMENTATION:
1. Plain text body: "Hello {{ examiner_name }}," then "Your examiner account has been approved. You can now sign in and manage your slots and evaluations." and "Sign in: {{ link }}". Then include _footer.txt. Never include a password or temporary password.
DEBUGGING:
DEBUG (add as a Jinja comment while debugging): examiner_approved examiner={{ examiner_id }}
OFFLINE DOCKER TEST CASES:
- Renders with the login link and contains no word "password".
#}
EOF

cat << 'EOF' > app/templates/emails/result_published.txt
{#
FILE PURPOSE: Email to a student when a result is published (PDR 14.2 "Results Published").
PROMPT FOR LLM IMPLEMENTATION:
1. Plain text body: "Hello {{ student_name }}," then "Your result for {{ examination_name }} ({{ exam_date }}) has been published. Sign in to see your marks, feedback and scorecard:" and the link. Then include _footer.txt. NEVER include marks, percentages, remarks or the examiner's name (the student must sign in to see them).
DEBUGGING:
DEBUG (add as a Jinja comment while debugging): result_published booking={{ booking_id }}
OFFLINE DOCKER TEST CASES:
- The rendered text contains no digits other than those of the date, and no word "marks" followed by a number.
#}
EOF

# ================================ SCRIPTS ============================

cat << 'EOF' > scripts/report_facts.py
"""
FILE PURPOSE: Generates the factual parts of the final report from the real project (so the report can never disagree with the code): libraries and versions, API endpoint list and the ER diagram. Output goes to docs/report/generated_facts.md and docs/er_diagram.mmd. Offline, no third-party dependency.
DEPENDS ON: the app factory (url_map, db.metadata), requirements*.txt, importlib.metadata.
PROMPT FOR LLM IMPLEMENTATION:
1. Provide pure functions (importable by tests): libraries_table(requirement_files) -> list of rows {package, version, tier, purpose, licence}: parse every requirements*.txt (skip comments and -r lines; version after ==), tier from the file name (requirements.txt = 1, requirements-tier2.txt = 2, requirements-dev.txt = dev), purpose from a small built-in dictionary (Flask, Flask-SQLAlchemy, Flask-WTF, Flask-Login, Flask-Mail, ReportLab, pytest, playwright and so on, unknown packages get "see documentation"), licence read from importlib.metadata when the package is installed (empty otherwise).
2. endpoints_table(app) -> rows {method, path, endpoint, blueprint, summary}: from app.url_map, excluding static, one row per method except HEAD and OPTIONS, sorted by path then method, summary = first line of the view function docstring when present; separate lists for HTML routes and /api/v1 routes.
3. er_mermaid(metadata) -> str: a Mermaid erDiagram: every table with its columns (type, PK, FK, UK markers) and a relationship line for every foreign key using the cardinality "||--o{" (parent to child), alphabetical order, deterministic output.
4. main(): build the app with the testing config on a temporary database, write docs/er_diagram.mmd, write docs/report/generated_facts.md with three sections (Libraries, Tier 1 HTML endpoints and Tier 2 API endpoints, ER diagram as a mermaid code block plus the table count) and a generated-on line; print the paths. Exit 0; exit 2 on usage errors. It never touches a real database and never needs a network.
5. Output is deterministic (sorted) except the generated-on line, which can be disabled with --no-date for tests.
DEBUGGING:
# print(f"[DEBUG] report_facts libraries={len(libs)} endpoints={len(eps)} tables={len(tables)}")
OFFLINE DOCKER TEST CASES:
- On the finished project the ER diagram lists 13 tables (12 Tier 1 and email_logs) and every foreign key appears as a relationship line.
- The endpoint table contains /student/slots/<id>/book, /api/v1/bookings and /student/bookings/<id>/scorecard.pdf.
- The libraries table lists Flask-Login and ReportLab with pinned versions from requirements-tier2.txt.
- Two runs with --no-date produce identical files.
"""
EOF

cat << 'EOF' > scripts/build_submission.sh
#!/usr/bin/env bash
# FILE PURPOSE: Builds submission_core.zip (Tier 1 + Tier 2, Tier 3 flags off) in a reproducible, clean way (Master Blueprint Gate B: "submission package ready"; course rule: one zip of the code).
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Bash with "set -euo pipefail". Usage: scripts/build_submission.sh [REF]. REF defaults to HEAD (use tier2-complete after tagging). Refuse to run with a dirty working tree unless --allow-dirty is given; refuse when REF does not exist.
# 2. Build from Git, not from the working folder: git archive --format=zip --prefix=emp/ -o submission_core.zip REF, so only tracked files are included and .env, instance/, logs/, wheels/, caches, test artefacts and previous zips are automatically left out.
# 3. Post-build checks on the zip (unzip -l): the top-level folder is emp/; required entries exist (README.md, requirements.txt, requirements-tier2.txt, Dockerfile, docker-compose.yml, Makefile, .env.example, app/__init__.py, app/models/user.py, app/services/booking_engine.py, app/blueprints/api_v1/__init__.py, app/services/scorecard.py, tests/, docs/ai_llm_declaration.md, docs/er_diagram.mmd, docs/report/report_draft.md); forbidden entries do not exist (.env, instance/*.db, logs/*, any path containing "tier3", __pycache__, .git/, *.pyc, wheels/*.whl, node_modules, submission_core.zip itself); no file inside matches a secret pattern (rzp_live_, private key headers, MAIL_PASSWORD= or SECRET_KEY= with a non-placeholder value) - extract to a temp directory and grep.
# 4. Print: the zip size in MB (warn above 20 MB), the number of files, the SHA-256 and the exact commit hash used. Fail with exit 1 and a clear list when any check fails; exit 0 and "SUBMISSION ZIP OK" otherwise.
# 5. The script never modifies the repository (no commits, no tags) and never needs a network.
# DEBUGGING:
# echo "[DEBUG] ref=${REF} files=${COUNT} size=${SIZE}" >&2   (when SUB_DEBUG=1)
# OFFLINE DOCKER TEST CASES:
# - On a clean checkout the script creates submission_core.zip and prints SUBMISSION ZIP OK.
# - Adding .env to the index (git add -f) makes the forbidden-entry check fail.
# - Creating app/blueprints/tier3 makes the check fail.
# - Running twice on the same commit gives the same SHA-256 (reproducible: fixed file order and timestamps from the commit).
EOF

cat << 'EOF' > scripts/verify_gate_b.sh
#!/usr/bin/env bash
# FILE PURPOSE: One command that checks every Gate B condition from Master Blueprint 2.3 and, only when all pass, offers to create the tag tier2-complete. Tier 3 may only start after this tag exists.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Bash with "set -uo pipefail" (collect failures). Usage: scripts/verify_gate_b.sh [--tag] [--allow-pending-video]. Run from the repo root on branch main with a clean working tree; otherwise print why and exit 2.
# 2. Check 1: Gate A still holds: tag tier1-complete exists and bash scripts/verify_gate_a.sh (without --tag) passes.
# 3. Check 2: tags p7-done to p12-done all exist and the six Tier 2 squash commits carry the unique messages Milestone-7 EMP-API-Integration, Milestone-8 EMP-Charts-Visualization, Milestone-9 EMP-Validation, Milestone-10 EMP-Responsive-UI, Milestone-11 EMP-Flask-Login-Security, Milestone-12 EMP-Scorecard-Email, each exactly once.
# 4. Check 3: scripts/check_gate.sh passes (no Tier 3 artefact, no secret, no true ENABLE_ flag).
# 5. Check 4: make test-core passes (unit, integration, e2e including all Tier 2 suites).
# 6. Check 5: markers pass individually: pytest -m api, -m charts, -m validation, -m responsive, -m a11y, -m security, -m mail, -m scorecard, -m concurrency (a marker with no tests is a FAIL, proving the suite exists).
# 7. Check 6: coverage: pytest --cov=app --cov-branch --cov-fail-under=80.
# 8. Check 7: make security and make a11y both pass.
# 9. Check 8: the API reference page lists every /api/v1 rule (the drift-guard test) and docs/tier2_traceability.md has every row starting "| T2-" marked Verified "yes" (list the others).
# 10. Check 9: submission package: bash scripts/build_submission.sh succeeds for HEAD; docs/report/report_draft.md exists and contains the required headings (Student details, Project details and approach, AI/LLM declaration, Frameworks and libraries, ER diagram, API endpoints, Video link); docs/ai_llm_declaration.md has no empty "Team member" cell for P0 to P12; docs/report/video_link.txt contains an https URL (with --allow-pending-video a missing link is a WARN instead of FAIL).
# 11. Check 10: .env.example contains no ENABLE_ flag set to true and no RAZORPAY variable; requirements-tier3.txt does not exist.
# 12. Print one PASS/FAIL/WARN line per check and a final "GATE B PASSED" or "GATE B FAILED (n checks)". Exit 0 only when no check failed.
# 13. With --tag and a passing run: create the annotated tag tier2-complete ("Gate B passed") if it does not exist and print the push command; never push. Without --tag print the exact tag command as a hint and the reminder that Tier 3 branches may only be created from this tag (make tier3-branch).
# DEBUGGING:
# echo "[DEBUG] check=${NAME} status=${STATUS} detail=${DETAIL}" >&2   (when GATE_DEBUG=1)
# OFFLINE DOCKER TEST CASES:
# - With everything green the script exits 0 and prints GATE B PASSED.
# - Removing tag p9-done makes check 2 fail; an empty tests/e2e folder makes check 4 fail.
# - Without video_link.txt the run fails, and with --allow-pending-video it only warns.
# - A dirty working tree exits 2 without running any test.
EOF

# ================================ DOCS ===============================

cat << 'EOF' > docs/tier2_traceability.md
<!--
FILE PURPOSE: Requirement-to-evidence table that Gate B check 8 reads ("every Tier 2 requirement is demonstrable").
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Tier 2 traceability" and a Markdown table with columns: ID, Requirement (from PDR 3.3 and 5.7), Phase, Automated test file, Demo act, Verified (yes/no). Rows start with "| T2-" exactly so the gate script can parse them.
2. One row per requirement: JSON API with at least four HTTP methods (GET, POST, PUT, DELETE) for examinations, examiners, students, slots and bookings; API errors and pagination contract; API reference page; role scoping identical to HTML; admin charts (booking trend, completion, workload); examiner charts (students evaluated, participants); student charts (history, trend, results); chart data-table fallback and offline Chart.js; HTML5 validation attributes; JavaScript validation mirroring the server; server validation for dates, timelines, capacity, rubric and marks; duplicate booking protection (server and submit-once); responsive layouts at 375, 768 and 1280 px; table cards and off-canvas Admin menu; WCAG 2.1 AA checks (contrast, keyboard, static audit); Flask-Login based sessions with unchanged RBAC; session fixation protection; idle and absolute timeout; password change invalidating other sessions; login lockout (5 failures per 15 minutes); security headers and strict CSP; scorecard PDF download for published results only; booking confirmation email; cancellation, reschedule and examiner-approval emails; result publication email without marks; email log with failure recording; email failure never blocking a booking; retry-failed-emails job; email log retention. IDs T2-01, T2-02, ... in order.
3. Fill Phase, Test file and Demo act from the Master Blueprint and the test files seeded in P7 to P12; leave Verified as "no" until the team has run the test and the demo step.
4. Under 70 lines of plain Markdown.
DEBUGGING:
(none: documentation file) Verify with: grep -c "^| T2-" docs/tier2_traceability.md
OFFLINE DOCKER TEST CASES:
- scripts/verify_gate_b.sh check 8 lists every row whose Verified column is not "yes".
-->
EOF

cat << 'EOF' > docs/demo_script_tier2.md
<!--
FILE PURPOSE: The rehearsed Tier 2 demo (about 8 minutes) to follow the Tier 1 script of docs/demo_script_tier1.md.
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Tier 2 demo script" with prerequisites: make demo-data on a fresh database, make mail-sink in a second terminal (so emails really travel over SMTP to the local sink) and MAIL_SUPPRESS_SEND=false for the demo, accounts from the Tier 1 script.
2. Six acts, each with Goal, Steps, Expected result and "Say this" talking points: (1) API: open /api/v1/docs, run GET, POST, PUT and DELETE with the browser console or curl using docs/api_examples.md, show a 409 and a 422; (2) Charts: dashboard widgets and the three chart pages per role, toggle the data table, show the empty state with a new student; (3) Validation: submit bad data with JavaScript on (inline messages, error summary, focus), turn JavaScript off or remove an attribute in dev tools and show the same message from the server, double-click a booking button; (4) Responsive and accessibility: resize to 375, 768 and 1280 px, open the Admin drawer with the keyboard, show the skip link and focus rings, run make a11y; (5) Security: five wrong passwords then the lockout message, change the password in one browser and show the other browser signed out, show the response headers in dev tools; (6) Email and scorecard: book a slot and show the message arriving in the mail sink and the email_logs tab in Admin history, break the SMTP port to show a failed log row and that the booking still succeeded, run the retry job, publish a result and download the scorecard PDF.
3. "If something breaks" table (symptom, fix) for: mail sink not running, port in use, lockout during rehearsal (restart the server clears it), missing Chart.js or font files (vendor README).
4. Twelve viva questions about Tier 2 (why Flask-Login, how the session fingerprint works, why a limiter in memory, what CSP blocks, why charts have a data table, why validation exists on both sides, how emails avoid blocking bookings, what the domain events are) with one-line answers pointing to files.
5. Under 130 lines of plain Markdown.
DEBUGGING:
(none: documentation file) Verify by following it on a fresh clone with a stopwatch.
OFFLINE DOCKER TEST CASES:
- Every URL, button and command named in the script exists; tests/e2e/test_tier2_demo_flow.py follows acts 1, 2, 5 and 6.
-->
EOF

cat << 'EOF' > docs/submission_checklist.md
<!--
FILE PURPOSE: Checklist for the course Final Submission of Tier 1 + Tier 2 (the "Final-A" step of Master Blueprint 3.4) with the evidence column for the viva.
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Final submission checklist". Table with columns Item, How to produce or verify it, Done (checkbox), Evidence.
2. Rows: tier1-complete and tier2-complete tags exist and are pushed; make gate-a and make gate-b pass; repository is private and the collaborator account MADI-cs2003 has access; every milestone has one unique commit message (list them); submission_core.zip built with make submission from the tier2-complete tag and unzipped on a clean machine to run make init-db and the demo; .env is not inside the zip; report of at most 5 pages with student details, project details and approach, AI/LLM declaration, frameworks and libraries, ER diagram, API endpoints and the video link (use docs/report/generated_facts.md from make report-facts); demo video of 5 to 10 minutes uploaded to Drive with the access set to anyone with the link and the link stored in docs/report/video_link.txt; AI/LLM declaration complete for P0 to P12; viva portal upload done; final commit message "Milestone-EMP Final-Submission" created after the zip is built; Tier 3 flags are off and no tier3 folder is in the zip; known issues list in the README is up to date.
3. A last section "Freeze rules": Tier 3 only starts after the tag tier2-complete and only if the freeze date allows it; otherwise it ships disabled or not at all.
4. Under 60 lines of plain Markdown.
DEBUGGING:
(none: documentation file)
OFFLINE DOCKER TEST CASES:
- Each row can be ticked from evidence produced by a script or a command listed in the row.
-->
EOF

cat << 'EOF' > docs/report/report_draft.md
<!--
FILE PURPOSE: Skeleton of the final report (course rule: up to 5 pages) with a page budget, built so that the factual sections are pasted from docs/report/generated_facts.md. Gate B check 9 looks for the required headings.
PROMPT FOR LLM IMPLEMENTATION:
1. Create the file with exactly these H2 headings in this order and a word budget in brackets after each heading: Student details (60 words), Project details and approach (450 words: problem, the three roles, the tier model, architecture, the booking engine idea, security approach, testing approach), AI/LLM declaration (copy the summary table from docs/ai_llm_declaration.md, 250 words), Frameworks and libraries (table from generated_facts.md), ER diagram (the rendered image of docs/er_diagram.mmd plus 3 sentences), API endpoints (the compact table from generated_facts.md, grouped by area), Video link (one line read from docs/report/video_link.txt).
2. Under each heading put a short "TODO" paragraph telling the writer what to paste or write, and the exact command that produces the facts (make report-facts). No invented content: every number must come from the generated facts or the traceability tables.
3. Add a closing "Page budget check" line reminding that the final PDF must be at most 5 pages with 11 pt text and 2 cm margins.
4. Keep it under 90 lines of plain Markdown.
DEBUGGING:
(none: documentation file) Verify with: grep -c "^## " docs/report/report_draft.md  (expect 7)
OFFLINE DOCKER TEST CASES:
- The seven required headings exist; the video link section is read by scripts/verify_gate_b.sh.
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_email_log_and_events.py
"""
FILE PURPOSE: Model constraints for email_logs and behaviour of the domain-event API in hooks.py.
DEPENDS ON: app/models/email_log.py, app/services/hooks.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Model: test_status_check_rejects_unknown, test_attempts_non_negative, test_required_columns_not_null (to_email, template, subject, body_text), test_indexes_exist (sqlite_master), test_no_foreign_keys, test_table_count_is_13_after_init (12 plus email_logs).
2. Events: test_register_unique_and_order, test_emit_passes_only_keywords, test_emit_swallows_handler_exception_and_logs_without_payload, test_emit_with_no_handlers_is_noop, test_clear_events, test_existing_pre_and_post_hooks_unchanged, test_event_names_are_stable_constants.
3. Emit sites (with a recording handler registered): test_book_slot_emits_after_commit_only (a vetoed or failed booking emits nothing; the handler sees a committed row), test_cancel_variants_emit_by_student_admin_slot, test_reschedule_emits_both_slot_ids, test_approve_examiner_emits, test_publish_and_admin_publish_emit, test_emit_failure_does_not_change_return_value.
DEBUGGING:
# print(f"[DEBUG] event case {name}: calls={recorded}")
OFFLINE DOCKER TEST CASES:
- 19 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_mailer.py
"""
FILE PURPOSE: Unit tests for mailer.py (templates, log lifecycle, retries, privacy, threads).
DEPENDS ON: app/services/mailer.py, tests/conftest.py (mail_outbox, sync_mail, smtp_failure, freeze_now).
PROMPT FOR LLM IMPLEMENTATION:
1. Templates: test_all_five_templates_render_with_footer_and_no_placeholders, test_subject_sanitised_single_line_max_150, test_unknown_template_keyerror, test_cancel_variants_never_contain_reason, test_result_email_has_no_marks, test_examiner_email_has_no_password_word, test_links_use_app_base_url, test_times_are_local_with_tz_abbreviation.
2. Lifecycle: test_queue_creates_row_then_sent, test_suppress_send_marks_sent_with_note, test_failure_marks_failed_attempts_one_and_trims_error, test_caller_never_sees_exception, test_error_message_has_no_credentials (SMTP error text containing the password is scrubbed), test_idempotent_attempt_on_sent_row, test_recipient_validation (newline, comma, two @), test_inactive_or_missing_email_skipped.
3. Retry and purge: test_retry_sends_failed_and_increments_attempts, test_terminal_failure_not_retried_after_max_attempts, test_stale_queued_row_retried_fresh_not, test_retry_writes_one_audit_row, test_purge_old_only_sent_or_terminal, test_purge_days_validation, test_retry_summary_counts.
4. Threads: test_async_mode_sends_in_background_thread_and_removes_session (wait with a join on the recorded thread, no sleeps), test_twenty_threads_twenty_rows_one_attempt_each, test_sync_mode_in_tests.
5. Safety: test_logs_never_contain_recipient_or_body (caplog), test_mailer_imports_no_blueprint_module.
DEBUGGING:
# print(f"[DEBUG] mailer case {name}: row={row.status}/{row.attempts} outbox={len(outbox)}")
OFFLINE DOCKER TEST CASES:
- 29 tests pass offline; removing the try/except in attempt_send makes test_caller_never_sees_exception fail.
"""
EOF

cat << 'EOF' > tests/unit/test_scorecard.py
"""
FILE PURPOSE: Unit tests for scorecard.build_scorecard.
DEPENDS ON: app/services/scorecard.py, tests/conftest.py (make_published_result, read_pdf_text).
PROMPT FOR LLM IMPLEMENTATION:
1. Access: test_published_own_returns_pdf, test_draft_submitted_foreign_unknown_return_none.
2. Content: test_pdf_header_and_footer_bytes, test_text_contains_student_exam_criteria_total_and_reference, test_percentage_one_decimal (25 of 40 gives 62.5), test_feedback_section_only_when_remarks, test_local_time_with_timezone_abbreviation, test_never_contains_email_or_hash (extracted text and raw bytes).
3. Robustness: test_accented_names_with_and_without_font_files, test_markup_in_names_is_escaped, test_thirty_criteria_multi_page_safe_and_fast (under 500 ms with a generous CI margin), test_long_comment_wraps_without_error, test_non_latin_name_falls_back_without_exception.
4. Metadata: test_metadata_title_author, test_no_javascript_or_embedded_files_in_pdf (search the raw bytes for /JS and /EmbeddedFile).
5. Determinism: test_deterministic_mode_identical_bytes.
6. Filename: test_filename_slug_ascii_and_length.
7. Mark with @pytest.mark.scorecard.
DEBUGGING:
# print(f"[DEBUG] scorecard case {name}: bytes={len(pdf)} pages={pages}")
OFFLINE DOCKER TEST CASES:
- 17 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_email_triggers.py
"""
FILE PURPOSE: End-to-end proof that real actions produce the right emails and that failures never block them (acceptance of P12).
DEPENDS ON: tests/conftest.py (api and HTTP clients, sync_mail, mail_outbox, smtp_failure, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. test_booking_creates_confirmation_email_and_log (HTML route and API route), test_student_cancel_email, test_admin_cancel_email_has_no_reason, test_slot_cancel_emails_every_student_once, test_reschedule_email_new_slot, test_examiner_approval_email, test_publish_by_examiner_email_no_marks, test_publish_by_admin_email.
2. Failure isolation: test_smtp_failure_booking_still_succeeds_and_log_failed, test_smtp_failure_cancel_and_publish_still_succeed, test_mail_suppressed_mode_logs_sent_with_note, test_mail_disabled_by_clearing_handlers_changes_nothing (hooks.clear_events then book: no log rows, booking fine).
3. Counts: test_exactly_one_email_per_event (no duplicates on double POST: the second POST is a duplicate booking and sends nothing), test_inactive_student_gets_no_email.
4. Atomicity: test_email_row_not_created_when_business_action_fails (full slot, closed window).
5. Mark with @pytest.mark.mail.
DEBUGGING:
# print(f"[DEBUG] trigger case {name}: logs={[(l.template, l.status) for l in logs]}")
OFFLINE DOCKER TEST CASES:
- 17 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_scorecard_route_history_tab_jobs.py
"""
FILE PURPOSE: HTTP tests for the scorecard route, the Admin email history tab and the two jobs.
DEPENDS ON: tests/conftest.py, app/cli.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Scorecard route: test_download_published_headers_and_body, test_content_disposition_filename_and_filename_star, test_cache_control_private_no_store, test_foreign_unpublished_unknown_404_identical, test_examiner_admin_403_anonymous_redirect, test_audit_row_written, test_link_visible_only_when_published (result detail and booking detail pages), test_get_only_405.
2. History tab: test_emails_tab_lists_rows_with_badges, test_filters_status_and_template, test_body_never_shown, test_five_tabs_present, test_non_admin_403.
3. Jobs CLI: test_jobs_retry_failed_emails_output_and_exit_code, test_jobs_retry_respects_max_attempts_option, test_jobs_purge_email_logs_days_option, test_jobs_exit_zero_when_nothing_to_do, test_init_db_reports_tier_counts_12_and_1.
4. Mark scorecard tests with @pytest.mark.scorecard and mail tests with @pytest.mark.mail.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Content-Type')} len={len(response.data)}")
OFFLINE DOCKER TEST CASES:
- 19 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_report_and_submission_scripts.py
"""
FILE PURPOSE: Tests for the closing tools: report_facts.py and build_submission.sh (run on a tiny temporary Git repository, never on the real one).
DEPENDS ON: scripts/report_facts.py, scripts/build_submission.sh, subprocess, tmp_path.
PROMPT FOR LLM IMPLEMENTATION:
1. report_facts: test_libraries_table_parses_pins_and_tiers, test_endpoints_table_contains_known_routes, test_er_mermaid_lists_all_tables_and_foreign_keys (13 tables), test_output_deterministic_with_no_date, test_main_writes_both_files_to_tmp_dir.
2. build_submission.sh in a temporary Git repo with a handful of tracked files: test_zip_has_emp_prefix_and_only_tracked_files, test_forbidden_entries_fail_the_script (tracked .env, a tier3 folder, a pyc), test_secret_pattern_fails, test_dirty_tree_refused_without_flag, test_same_commit_same_sha256, test_missing_required_entry_reported.
3. Skip the shell tests with a clear message when git or zip tools are unavailable.
DEBUGGING:
# print(f"[DEBUG] script run rc={proc.returncode} stdout_tail={proc.stdout[-200:]!r}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass offline.
"""
EOF

cat << 'EOF' > tests/e2e/test_tier2_demo_flow.py
"""
FILE PURPOSE: Browser walkthrough of Tier 2 acts 1, 2, 5 and 6 of docs/demo_script_tier2.md, including the real PDF download.
DEPENDS ON: tests/e2e/conftest.py (live_server, browser fixtures, clock), demo or chart dataset, a local aiosmtpd sink started by a fixture.
PROMPT FOR LLM IMPLEMENTATION:
1. Mark @pytest.mark.e2e. A module fixture starts an aiosmtpd controller on a free port and sets the app mail config to it (MAIL_SUPPRESS_SEND false, MAIL_ASYNC true) so messages really travel over SMTP to the in-process sink.
2. test_api_docs_and_calls: open /api/v1/docs, then through page.request with the CSRF token from /api/v1/session run GET list, POST booking, PUT slot (as examiner context) and DELETE booking and assert statuses 200, 201, 200, 200 plus one 409 and one 422.
3. test_charts_and_data_tables_for_each_role (short: every canvas reaches the ready state and the data table has rows).
4. test_lockout_and_password_change_sessions (compact version of the security e2e): lockout message after five failures; password change in one context signs out the other.
5. test_booking_email_arrives_and_logged: a student books; the sink receives one message to the student's address containing the examination name and no password; Admin history emails tab shows a "sent" row for booking_confirmed.
6. test_smtp_down_booking_still_succeeds: stop the sink, book as another student, assert the booking exists, the log row is "failed", restart the sink and run the retry job through the CLI helper; the row becomes "sent" and the sink receives the message.
7. test_scorecard_download: a student with a published result clicks "Download scorecard (PDF)" with page.expect_download; the file name matches the pattern, the first bytes are %PDF-, and pypdf finds the student name and the total in the text.
8. Assert no console errors, no CSP violations and no non-local requests in every test; take screenshots into test-results/ on failure.
DEBUGGING:
# print(f"[DEBUG] tier2 e2e step={step} url={page.url} smtp_inbox={len(inbox)}")
OFFLINE DOCKER TEST CASES:
- All tests pass with the network disabled (the SMTP sink is local).
- Stopping the sink makes the failure test see a "failed" row and a successful booking.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs scripts -type d -empty -exec touch {}/.gitkeep \;
chmod +x scripts/*.sh 2>/dev/null || true

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P12 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Optional while online: download DejaVuSans.ttf and DejaVuSans-Bold.ttf into app/static/vendor/fonts/ (see app/static/vendor/README.md)."
echo "2. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P12_update_existing_files.md in ORDER (requirements, config, extensions, models, hooks, then the emitting services) with the CURRENT files."
echo "3. Run 'make test-core', 'make test-mail' and 'make test-scorecard'; start 'make mail-sink' and walk docs/demo_script_tier2.md."
echo "4. Run 'git add . && git commit -m \"wip: P12 scorecard and email\"'  (wip: commits are free-form)."
echo "5. When green: 'git checkout main && git merge --squash phase/p12-scorecard-email && git commit -m \"Milestone-12 EMP-Scorecard-Email\" && git tag p12-done && git push origin main --tags'."
echo "6. Gate B: fill docs/tier2_traceability.md, docs/report/report_draft.md and docs/report/video_link.txt, run 'make report-facts', 'make submission', then 'bash scripts/verify_gate_b.sh --tag' and push the tier2-complete tag."
echo "7. Decisions to confirm: domain events in hooks.py (post-commit, never undo); plain-text emails without marks or reasons; email_logs gets subject, body_text and attempts columns (TDR 4.2 update); ReportLab with optional DejaVu fonts (no Devanagari); scorecard for students only; Admin email tab shows no bodies."
echo "Project scaffolding complete for Tier 1 and Tier 2 (P0-P12). Tier 3 (P13-P17) scripts are generated only after the tag tier2-complete exists."
echo "====================================================="
