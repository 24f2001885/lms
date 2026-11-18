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
