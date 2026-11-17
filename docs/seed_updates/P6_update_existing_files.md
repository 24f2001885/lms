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
