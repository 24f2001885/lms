# TECHNICAL DESIGN REPORT: Examination Management Portal (EMP), v2

*Input: PDR v2 (`1_PDR_EMP_v2.md`). Tier labels follow the PDR: **T1** = Primary, **T2** = Secondary, **T3** = Tertiary. Nothing marked T3 is built before Gate B (all T1 and T2 complete and tagged).*

---

## 1. Introduction & Conventions

**Runtime:** Python 3.11+ (3.12 recommended), Flask 3.x, Flask-SQLAlchemy 3.x on SQLAlchemy 2.x, SQLite 3.35+ (partial indexes and CHECK constraints are used).
**Mandated stack:** Flask, Jinja2/HTML/CSS/Bootstrap 5, SQLite only. Docker is optional (see section 9) because the course requires a local-machine demo. *Default chosen: virtualenv first, Docker as a convenience.*

**Naming conventions**
- Variables, functions, modules, table and column names: `snake_case`.
- Classes (models, services, forms): `PascalCase`.
- Constants and environment variables: `UPPER_SNAKE_CASE`.
- Endpoints: resource-based nouns, plural collections, correct HTTP verbs. HTML form routes use `/<role>/<resources>`; JSON routes use `/api/v1/<resources>`.
- Enumerated values stored as lowercase `snake_case` strings with a CHECK constraint (for example `'booked'`, `'random_forward_only'`).
- Git commit messages: `Milestone-<phase> EMP-<Name>`, unique per phase (course rule). M0 is fixed as `Milestone-0 EMP-MAD-1`.

**Primary keys:** `INTEGER PRIMARY KEY AUTOINCREMENT` (not UUID). *Default chosen:* SQLite and the course's "search by name or ID" requirement favour short integer IDs.

**Timestamps:** stored as UTC `DATETIME` (naive UTC in SQLite). Displayed in `APP_TIMEZONE` (default `Asia/Kolkata`, configurable). All window checks use one helper, `now_utc()`.

**Linting and formatting:** `ruff` (rules E, F, I, N, B, UP) and `black` (line length 100). Type hints on service functions. Jinja templates use 2-space indentation.

---

## 2. System Architecture

**Client-server model:** server-rendered monolith. Browser requests go to Flask blueprints, which call a service layer, which uses SQLAlchemy models over one SQLite file. Business rules live only in services so HTML views and the JSON API share them.

```
Browser (Bootstrap pages; T3 adds small JS)
   |  HTTPS/HTTP
Flask app (app factory create_app)
   |-- blueprints: auth, admin, examiner, student   (T1)
   |-- blueprint:  api_v1                           (T2)
   |-- blueprints: tests, attempts, proctoring, payments   (T3, behind feature flags)
   |-- services:   booking_engine, evaluation, windows, audit, (T2) mailer, scorecard
   |               (T3) test_engine, proctor_policy, payment_service
   |-- models (SQLAlchemy) --> SQLite file instance/emp.db
   |-- CLI jobs: flask jobs ...
   '-- outbound (T3 only): Razorpay REST API, test mode
```

**Data flow (T1 booking):** student POST `/student/slots/<id>/book` → `role_required('student')` → `booking_engine.book_slot()` → one write transaction → HTML redirect with flash message.

**Tiering in code:** T3 packages (`app/blueprints/tests`, `attempts`, `proctoring`, `payments`, and their services/models) are imported and registered only when the matching flag is true. T1 and T2 code never imports T3 modules. T1 exposes two generic extension points in `app/services/hooks.py`: `pre_booking_hooks` and `post_cancel_hooks` (empty lists in T1), which T3 payments later use. This keeps T3 purely additive.

**Docker (optional):** one `app` container with a bind-mounted `instance/` directory. No other containers are needed because SQLite is file-based.

---

## 3. Flagship Feature: Slot Booking & Capacity Engine

This is the hardest T1 logic. It must stay correct when two students click "Book" on the last seat at once, when windows open or close mid-request, and when Admin reschedules or cancels.

### 3.1 Goals and invariants
1. `0 <= booked_count <= max_capacity` always.
2. A student has at most one active booking (`booked` or `completed`) per examination.
3. Booking is allowed only while the examination's booking window is open.
4. A slot becomes `full` exactly when `booked_count == max_capacity` and returns to `available` when a seat is freed (and the slot is not cancelled/completed).

### 3.2 Why SQLite needs special care
SQLite allows one writer at a time. A read-then-write inside a deferred transaction can still let two requests read the same count. The fix is to start every booking transaction with `BEGIN IMMEDIATE` (taking the write lock up front), so the check and the insert are atomic. The database also enforces the invariants as a second line of defence (CHECK and partial unique index).

Engine setup (SQLAlchemy 2.x recipe):
```python
@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None          # we control BEGIN ourselves
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

@event.listens_for(Engine, "begin")
def begin_immediate(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")
```

### 3.3 Algorithm `book_slot(student_id, slot_id)`
1. Start transaction (`BEGIN IMMEDIATE` via the hook above).
2. Load slot; fail `slot_not_found` if missing; fail `slot_not_available` if status is not `available`.
3. Load examination; run `windows.assert_booking_open(exam, now_utc())` (checks `booking_open` flag AND `booking_start <= now <= booking_end`); fail `booking_closed`.
4. Run `pre_booking_hooks` (empty in T1). A hook may raise `BookingError`.
5. Check duplicate: any booking for (student, examination) with status in (`booked`, `completed`); fail `duplicate_booking`.
6. Check capacity: `slot.booked_count < slot.max_capacity`; fail `slot_full`.
7. Insert booking (`status='booked'`, `booked_at=now`); `slot.booked_count += 1`; if now equal to capacity set `slot.status='full'`.
8. Write an `audit_logs` row; commit. On `IntegrityError` (partial index or CHECK tripped) roll back and map to `duplicate_booking` or `slot_full`.
9. After commit, (T2) enqueue the confirmation email; failure to send never rolls back the booking.

### 3.4 Cancel, reschedule and examiner change
- **Cancel (student):** allowed if `now <= exam.cancellation_deadline` and booking is `booked`. Sets `status='cancelled'`, `cancelled_at`, decrements `booked_count`, flips `full` back to `available`. Runs `post_cancel_hooks`.
- **Cancel (admin):** same without the deadline check; reason recorded in the audit log.
- **Reschedule (admin):** one transaction: lock target slot, verify same examination, verify capacity, move the booking (`slot_id`), decrement old and increment new `booked_count`, adjust both slot statuses, store `rescheduled_from_slot_id`.
- **Change examiner (admin):** updates `examination_slots.examiner_id` (new examiner must be in `examination_examiners` and `approved`), writes an audit row. Existing bookings and evaluations stay attached to the slot; evaluation `examiner_id` records who actually evaluated.

### 3.5 Edge cases
| Case | Behaviour |
|---|---|
| Two students book the last seat | One commits; the other gets `slot_full` |
| Student double-clicks Book | Second request hits the duplicate check or the unique index |
| Booking window closes during the request | Window checked inside the transaction after taking the lock |
| Examiner edits a slot while students book | Edits allowed only before `booking_start`; both paths check the window |
| Slot deleted with bookings | Blocked; examiner must cancel the slot, which cancels bookings through the same service and logs it |
| Examination closed/completed | Slot status moves to `completed`; all bookings become `completed` by the job in section 11 |

### 3.6 T3 deep dive: Test Attempt Engine (deferred to Gate B)
Hardest T3 logic: a per-student attempt that survives refreshes, enforces the deadline and mode rules on the server, and scores once.

**`start_attempt(student_id, test_id)`**
1. Load test (published, inside `available_from..available_until`); load the student's booking for the test's examination with status `booked`; fail `no_valid_booking` (T3 payments hook also requires a paid booking when the fee is above 0).
2. `BEGIN IMMEDIATE`; fail `attempt_exists` if a non-reset attempt exists.
3. Select questions: all, or `random.sample(question_ids, questions_per_attempt)` for random modes; order: author `position` for `standard`, `random.shuffle` for random modes (seeded from `secrets.randbits(64)`, seed not stored; the stored rows are the source of truth).
4. Insert `test_attempts` (`status='in_progress'`, `started_at=now`, `deadline_at=min(now + duration, available_until)`), insert `attempt_questions` with `position` and a shuffled `option_order` JSON for random modes.
5. Commit and redirect to position 0.

**`get_question(attempt, position)`**
- If `now > deadline_at`, call `finalize_attempt(status='auto_submitted_timeout')` and redirect to result.
- `standard` / `random_revisitable`: any position within range is allowed.
- `random_forward_only`: allowed only when `position == attempt.current_index`; any other position returns 409 `revisit_not_allowed` (also blocks edited URLs and the browser back button re-submitting an old page).

**`save_answer(attempt, question_id, option_id)`**
- Re-check deadline; verify the question belongs to the attempt and the option belongs to the question.
- `random_forward_only`: only the question at `current_index` is writable; saving locks it (`is_locked=1`) and advances `current_index`. An already locked question rejects changes with `answer_locked`.
- Other modes: upsert `attempt_answers`; allow `marked_for_review`.

**`finalize_attempt(attempt, status)`** is idempotent: if already final it returns the stored result. It sums marks for correct options, subtracts `negative_marking` for wrong ones (never below 0 total), stores `score`, `max_score`, `submitted_at`, status, and is the single place scoring happens.

**Why this shape:** all rules are decided on the server from stored state, so refresh, back button, two tabs, a slow client timer, or a hand-edited request cannot grant extra time or revisits. The client timer is only a display.

**Seat-hold + payment** (T3) is described in section 8.2.

---

## 4. Database Design

All tables: SQLite, integer PKs. `created_at`/`updated_at` are `DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP` unless noted. Foreign keys are enforced (`PRAGMA foreign_keys=ON`).

### 4.1 Tier 1 tables

- `users`
  - `id` (INTEGER, Primary Key)
  - `email` (TEXT, Unique, Not Null)
  - `password_hash` (TEXT, Not Null)
  - `full_name` (TEXT, Not Null)
  - `role` (TEXT, Not Null, CHECK in `'admin','examiner','student'`)
  - `approval_status` (TEXT, Not Null, CHECK in `'pending','approved','rejected'`, default `'approved'`; examiners register as `'pending'`)
  - `is_active` (BOOLEAN, Not Null, default 1)
  - `last_login_at` (DATETIME, Null)
  - `created_at`, `updated_at`
  - Index: `ix_users_role` (`role`), `ix_users_full_name` (`full_name`)
- `examiner_profiles`
  - `id` (INTEGER, Primary Key)
  - `user_id` (INTEGER, Foreign Key → users.id, Unique, Not Null)
  - `contact_phone` (TEXT, Null)
  - `department` (TEXT, Null)
  - `designation` (TEXT, Null)
  - `status` (TEXT, Not Null, CHECK in `'active','inactive'`, default `'active'`)
  - `created_at`, `updated_at`
- `student_profiles`
  - `id` (INTEGER, Primary Key)
  - `user_id` (INTEGER, Foreign Key → users.id, Unique, Not Null)
  - `roll_number` (TEXT, Unique, Null)
  - `contact_phone` (TEXT, Null)
  - `program` (TEXT, Null)
  - `created_at`, `updated_at`
- `courses`
  - `id` (INTEGER, Primary Key)
  - `code` (TEXT, Unique, Not Null)
  - `name` (TEXT, Not Null)
  - `description` (TEXT, Null)
  - `status` (TEXT, Not Null, CHECK in `'active','inactive'`, default `'active'`)
  - `created_by` (INTEGER, Foreign Key → users.id, Not Null)
  - `created_at`, `updated_at`
- `examinations`
  - `id` (INTEGER, Primary Key)
  - `course_id` (INTEGER, Foreign Key → courses.id, Not Null)
  - `name` (TEXT, Not Null)
  - `description` (TEXT, Null)
  - `exam_type` (TEXT, Not Null, CHECK in `'viva','practical','project_demo','assessment'`)
  - `duration_minutes` (INTEGER, Not Null, CHECK > 0)
  - `max_marks` (INTEGER, Not Null, CHECK > 0)
  - `slot_creation_start` (DATETIME, Not Null)
  - `slot_creation_end` (DATETIME, Not Null)
  - `booking_start` (DATETIME, Not Null)
  - `booking_end` (DATETIME, Not Null)
  - `cancellation_deadline` (DATETIME, Not Null; defaults to `booking_end`)
  - `slot_creation_open` (BOOLEAN, Not Null, default 0; Admin switch)
  - `booking_open` (BOOLEAN, Not Null, default 0; Admin switch)
  - `status` (TEXT, Not Null, CHECK in `'draft','slot_creation','booking_open','closed','completed'`, default `'draft'`)
  - `is_deleted` (BOOLEAN, Not Null, default 0)
  - `created_at`, `updated_at`
  - CHECK: `slot_creation_start < slot_creation_end`, `booking_start < booking_end`, `slot_creation_end <= booking_start`
  - Index: `ix_examinations_course_id`
- `examination_rubrics`
  - `id` (INTEGER, Primary Key)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null)
  - `criterion_name` (TEXT, Not Null)
  - `description` (TEXT, Null)
  - `weightage` (NUMERIC(5,2), Not Null, CHECK between 0 and 100)
  - `max_score` (NUMERIC(6,2), Not Null, CHECK > 0)
  - `position` (INTEGER, Not Null, default 0)
  - Unique: (`examination_id`, `criterion_name`)
- `examination_examiners`
  - `id` (INTEGER, Primary Key)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null)
  - `examiner_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `assigned_by` (INTEGER, Foreign Key → users.id, Not Null)
  - `assigned_at` (DATETIME, Not Null)
  - Unique: (`examination_id`, `examiner_id`)
- `examination_slots`
  - `id` (INTEGER, Primary Key)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null)
  - `examiner_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `start_at` (DATETIME, Not Null)
  - `end_at` (DATETIME, Not Null, CHECK `end_at > start_at`)
  - `max_capacity` (INTEGER, Not Null, CHECK > 0)
  - `booked_count` (INTEGER, Not Null, default 0, CHECK `booked_count >= 0 AND booked_count <= max_capacity`)
  - `status` (TEXT, Not Null, CHECK in `'available','full','cancelled','completed'`, default `'available'`)
  - `created_at`, `updated_at`
  - Index: `ix_slots_examination_id`, `ix_slots_examiner_id`
  - Rule in service: no two slots of the same examiner overlap in time.
- `bookings`
  - `id` (INTEGER, Primary Key)
  - `student_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `slot_id` (INTEGER, Foreign Key → examination_slots.id, Not Null)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null; denormalised so the unique index below works)
  - `status` (TEXT, Not Null, CHECK in `'booked','cancelled','completed'`, default `'booked'`)
  - `booked_at` (DATETIME, Not Null)
  - `cancelled_at` (DATETIME, Null)
  - `cancelled_by` (INTEGER, Foreign Key → users.id, Null)
  - `rescheduled_from_slot_id` (INTEGER, Foreign Key → examination_slots.id, Null)
  - `created_at`, `updated_at`
  - Partial unique index: `uq_bookings_active_student_exam` on (`student_id`, `examination_id`) `WHERE status IN ('booked','completed')`
  - Index: `ix_bookings_slot_id`, `ix_bookings_student_id`
- `evaluations`
  - `id` (INTEGER, Primary Key)
  - `booking_id` (INTEGER, Foreign Key → bookings.id, Unique, Not Null)
  - `examiner_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `total_marks` (NUMERIC(6,2), Not Null, default 0, CHECK >= 0)
  - `remarks` (TEXT, Null)
  - `status` (TEXT, Not Null, CHECK in `'draft','submitted','published'`, default `'draft'`)
  - `submitted_at` (DATETIME, Null)
  - `published_at` (DATETIME, Null)
  - `created_at`, `updated_at`
- `evaluation_scores`
  - `id` (INTEGER, Primary Key)
  - `evaluation_id` (INTEGER, Foreign Key → evaluations.id, Not Null)
  - `rubric_id` (INTEGER, Foreign Key → examination_rubrics.id, Not Null)
  - `score` (NUMERIC(6,2), Not Null, CHECK >= 0)
  - `comment` (TEXT, Null)
  - Unique: (`evaluation_id`, `rubric_id`)
  - Service rule: `score <= rubric.max_score` and `total_marks <= examination.max_marks`.
- `audit_logs`
  - `id` (INTEGER, Primary Key)
  - `actor_id` (INTEGER, Foreign Key → users.id, Null; null for system jobs)
  - `action` (TEXT, Not Null; e.g. `booking.create`)
  - `entity_type` (TEXT, Not Null)
  - `entity_id` (INTEGER, Null)
  - `details` (TEXT, Null; JSON string)
  - `ip_address` (TEXT, Null)
  - `created_at`
  - Index: `ix_audit_logs_entity` (`entity_type`, `entity_id`)

### 4.2 Tier 2 tables
- `email_logs`
  - `id` (INTEGER, Primary Key)
  - `to_email` (TEXT, Not Null)
  - `template` (TEXT, Not Null; e.g. `booking_confirmed`)
  - `status` (TEXT, Not Null, CHECK in `'queued','sent','failed'`)
  - `error_message` (TEXT, Null)
  - `related_entity_type` (TEXT, Null), `related_entity_id` (INTEGER, Null)
  - `created_at`, `sent_at` (DATETIME, Null)

### 4.3 Tier 3 tables (created only after Gate B; **no T1 or T2 table is altered**)
This refines PDR section 8: the fee and the seat hold live in their own tables so `bookings` and `examinations` stay untouched.

- `examination_fees`
  - `id` (INTEGER, Primary Key)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Unique, Not Null)
  - `amount_paise` (INTEGER, Not Null, CHECK >= 0)
  - `currency` (TEXT, Not Null, default `'INR'`)
  - `created_at`, `updated_at`
- `tests`
  - `id` (INTEGER, Primary Key)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null)
  - `title` (TEXT, Not Null)
  - `instructions` (TEXT, Null)
  - `delivery_mode` (TEXT, Not Null, CHECK in `'standard','random_forward_only','random_revisitable'`)
  - `duration_minutes` (INTEGER, Not Null, CHECK > 0)
  - `questions_per_attempt` (INTEGER, Null; null means all questions)
  - `marks_per_question` (NUMERIC(5,2), Not Null, default 1)
  - `negative_marks` (NUMERIC(5,2), Not Null, default 0)
  - `pass_marks` (NUMERIC(6,2), Null)
  - `available_from` (DATETIME, Not Null), `available_until` (DATETIME, Not Null)
  - `max_violations` (INTEGER, Not Null, default 1, CHECK >= 1)
  - `blur_grace_ms` (INTEGER, Not Null, default 1000, CHECK >= 0)
  - `require_fullscreen` (BOOLEAN, Not Null, default 0)
  - `result_publish_mode` (TEXT, Not Null, CHECK in `'immediate','manual'`, default `'immediate'`)
  - `is_published` (BOOLEAN, Not Null, default 0)
  - `created_by` (INTEGER, Foreign Key → users.id, Not Null)
  - `created_at`, `updated_at`
  - Unique: (`examination_id`, `title`)
- `test_questions`
  - `id` (INTEGER, Primary Key)
  - `test_id` (INTEGER, Foreign Key → tests.id, Not Null)
  - `question_text` (TEXT, Not Null)
  - `explanation` (TEXT, Null)
  - `marks` (NUMERIC(5,2), Null; null uses `tests.marks_per_question`)
  - `position` (INTEGER, Not Null)
  - `created_at`, `updated_at`
  - Unique: (`test_id`, `position`)
- `test_options`
  - `id` (INTEGER, Primary Key)
  - `question_id` (INTEGER, Foreign Key → test_questions.id, Not Null)
  - `option_text` (TEXT, Not Null)
  - `is_correct` (BOOLEAN, Not Null, default 0)
  - `position` (INTEGER, Not Null)
  - Partial unique index: one correct option per question, `uq_options_one_correct` on (`question_id`) `WHERE is_correct = 1`
- `test_attempts`
  - `id` (INTEGER, Primary Key)
  - `test_id` (INTEGER, Foreign Key → tests.id, Not Null)
  - `booking_id` (INTEGER, Foreign Key → bookings.id, Not Null)
  - `student_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `status` (TEXT, Not Null, CHECK in `'in_progress','submitted','auto_submitted_timeout','auto_submitted_violation','reset'`)
  - `rules_accepted_at` (DATETIME, Not Null)
  - `started_at` (DATETIME, Not Null), `deadline_at` (DATETIME, Not Null)
  - `submitted_at` (DATETIME, Null)
  - `current_index` (INTEGER, Not Null, default 0)
  - `violation_count` (INTEGER, Not Null, default 0)
  - `score` (NUMERIC(6,2), Null), `max_score` (NUMERIC(6,2), Null)
  - `created_at`, `updated_at`
  - Partial unique index: `uq_attempts_one_live` on (`test_id`, `student_id`) `WHERE status != 'reset'`
- `attempt_questions`
  - `id` (INTEGER, Primary Key)
  - `attempt_id` (INTEGER, Foreign Key → test_attempts.id, Not Null)
  - `question_id` (INTEGER, Foreign Key → test_questions.id, Not Null)
  - `position` (INTEGER, Not Null)
  - `option_order` (TEXT, Not Null; JSON list of option IDs)
  - `is_locked` (BOOLEAN, Not Null, default 0)
  - Unique: (`attempt_id`, `position`), (`attempt_id`, `question_id`)
- `attempt_answers`
  - `id` (INTEGER, Primary Key)
  - `attempt_id` (INTEGER, Foreign Key → test_attempts.id, Not Null)
  - `question_id` (INTEGER, Foreign Key → test_questions.id, Not Null)
  - `selected_option_id` (INTEGER, Foreign Key → test_options.id, Null)
  - `marked_for_review` (BOOLEAN, Not Null, default 0)
  - `answered_at` (DATETIME, Null), `updated_at`
  - Unique: (`attempt_id`, `question_id`)
- `proctoring_events`
  - `id` (INTEGER, Primary Key)
  - `attempt_id` (INTEGER, Foreign Key → test_attempts.id, Not Null)
  - `event_type` (TEXT, Not Null, CHECK in `'visibility_hidden','window_blur','fullscreen_exit','copy_attempt','cut_attempt','paste_attempt','context_menu','heartbeat_lost'`)
  - `client_occurred_at` (DATETIME, Null), `received_at` (DATETIME, Not Null)
  - `duration_ms` (INTEGER, Null)
  - `question_position` (INTEGER, Null)
  - `counted_as_violation` (BOOLEAN, Not Null, default 0)
  - `user_agent` (TEXT, Null), `ip_address` (TEXT, Null)
  - Index: `ix_proctoring_events_attempt_id`
- `payments`
  - `id` (INTEGER, Primary Key)
  - `student_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null)
  - `slot_id` (INTEGER, Foreign Key → examination_slots.id, Not Null)
  - `booking_id` (INTEGER, Foreign Key → bookings.id, Null; set after confirmation)
  - `razorpay_order_id` (TEXT, Unique, Not Null)
  - `razorpay_payment_id` (TEXT, Unique, Null)
  - `razorpay_signature` (TEXT, Null)
  - `amount_paise` (INTEGER, Not Null, CHECK > 0), `currency` (TEXT, Not Null)
  - `status` (TEXT, Not Null, CHECK in `'created','paid','failed','refunded','expired'`)
  - `failure_reason` (TEXT, Null)
  - `paid_at` (DATETIME, Null)
  - `created_at`, `updated_at`
- `seat_holds`
  - `id` (INTEGER, Primary Key)
  - `payment_id` (INTEGER, Foreign Key → payments.id, Unique, Not Null)
  - `slot_id` (INTEGER, Foreign Key → examination_slots.id, Not Null)
  - `student_id` (INTEGER, Foreign Key → users.id, Not Null)
  - `examination_id` (INTEGER, Foreign Key → examinations.id, Not Null)
  - `status` (TEXT, Not Null, CHECK in `'active','converted','expired','released'`)
  - `expires_at` (DATETIME, Not Null)
  - `created_at`
  - Partial unique index: `uq_holds_active_student_exam` on (`student_id`, `examination_id`) `WHERE status = 'active'`
- `refunds`
  - `id` (INTEGER, Primary Key)
  - `payment_id` (INTEGER, Foreign Key → payments.id, Not Null)
  - `razorpay_refund_id` (TEXT, Unique, Null)
  - `amount_paise` (INTEGER, Not Null, CHECK > 0)
  - `status` (TEXT, Not Null, CHECK in `'initiated','processed','failed'`)
  - `reason` (TEXT, Null)
  - `created_at`, `processed_at` (DATETIME, Null)

**Programmatic creation:** `create_db.py` calls `db.create_all()` and seeds the Admin idempotently from env values (never hard-coded in the repo). T3 tables are defined in separate model modules imported only when a T3 flag is on, so `create_all()` adds them at that point with no migration of T1/T2 tables.

---

## 5. REST API Design

**Conventions:** JSON bodies; errors use `{"error": {"code": "slot_full", "message": "This slot is full."}}`; list responses use `{"items": [...], "page": 1, "per_page": 20, "total": 57}`; timestamps are ISO 8601 UTC strings. All state-changing browser requests need the CSRF token (form field `csrf_token` or header `X-CSRFToken`).

### 5.1 T1: Server-rendered form routes (HTML in, redirect + flash out)
| Method | Path | Request (form fields) | Result | Roles |
|---|---|---|---|---|
| GET/POST | `/register` | `role` (student or examiner), `full_name`, `email`, `password`, `confirm_password` | 302 to `/login` | public |
| GET/POST | `/login` | `email`, `password` | 302 to role dashboard | public |
| POST | `/logout` | none | 302 to `/login` | any |
| GET | `/admin/dashboard` | none | HTML with six totals | admin |
| GET/POST | `/admin/courses` | `code`, `name`, `description`, `status` | list / create | admin |
| POST | `/admin/courses/<id>/update`, `/delete` | same fields / none | 302 | admin |
| GET/POST | `/admin/examinations` | all `examinations` columns above | list / create | admin |
| POST | `/admin/examinations/<id>/update`, `/delete` | fields / none | 302 | admin |
| POST | `/admin/examinations/<id>/slot-creation/toggle`, `/booking/toggle` | none | flips switch, audit row | admin |
| GET/POST | `/admin/examinations/<id>/rubrics` | `criterion_name`, `description`, `weightage`, `max_score` | list / add; sum of weightage must be 100 | admin |
| POST | `/admin/examinations/<id>/examiners` | `examiner_id` | assign examiner | admin |
| GET | `/admin/examiners` | query `status`, `q` | list | admin |
| POST | `/admin/examiners/<id>/approve`, `/deactivate` | none | 302 | admin |
| GET | `/admin/search` | query `q`, `type` (student, examiner, examination, booking) | results page | admin |
| GET | `/admin/slots`, `/admin/bookings`, `/admin/history` | filters | lists | admin |
| POST | `/admin/bookings/<id>/reschedule` | `new_slot_id` | 302 | admin |
| POST | `/admin/slots/<id>/examiner` | `examiner_id` | 302 | admin |
| GET | `/examiner/dashboard` | none | assigned exams, slots, booked counts, pending evaluations | examiner (approved) |
| GET/POST | `/examiner/slots` | `examination_id`, `start_at`, `end_at`, `max_capacity` | list / create | examiner |
| POST | `/examiner/slots/<id>/update`, `/delete` | same / none | 302 | examiner (own) |
| GET | `/examiner/slots/<id>/students` | none | booked students | examiner (own) |
| GET/POST | `/examiner/bookings/<id>/evaluate` | `score_<rubric_id>` per rubric, `remarks`, `publish` | saves evaluation | examiner (own slot) |
| GET | `/student/dashboard` | none | available exams, slots, upcoming, booked, results | student |
| GET | `/student/examinations` | query `q`, `course_id`, `exam_type` | search/filter | student |
| POST | `/student/slots/<id>/book` | none | 302 + flash | student |
| POST | `/student/bookings/<id>/cancel` | none | 302 + flash | student (own) |
| GET | `/student/bookings`, `/student/history`, `/student/results` | none | lists | student |
| GET/POST | `/profile` | profile fields | update own profile | any |

### 5.2 T2: JSON API `/api/v1`
Authentication: the logged-in session cookie (same RBAC as the HTML routes). Page size default 20, max 100.

| Method | Path | Request | Response | Roles |
|---|---|---|---|---|
| GET | `/api/v1/examinations` | query `course_id`, `status`, `q`, `page`, `per_page` | 200 list | any (scoped) |
| GET | `/api/v1/examinations/<id>` | none | 200 object | any (scoped) |
| POST | `/api/v1/examinations` | `{course_id, name, exam_type, duration_minutes, max_marks, slot_creation_start, slot_creation_end, booking_start, booking_end, cancellation_deadline}` | 201 object | admin |
| PUT | `/api/v1/examinations/<id>` | same fields (partial allowed) | 200 object | admin |
| DELETE | `/api/v1/examinations/<id>` | none | 204 | admin |
| GET | `/api/v1/examiners` | query `status`, `q` | 200 list | admin |
| GET | `/api/v1/students` | query `q` | 200 list | admin |
| GET | `/api/v1/slots` | query `examination_id`, `status` | 200 list | any (scoped) |
| POST | `/api/v1/slots` | `{examination_id, start_at, end_at, max_capacity}` | 201 object | examiner |
| PUT | `/api/v1/slots/<id>` | partial fields | 200 object | examiner (own) |
| DELETE | `/api/v1/slots/<id>` | none | 204 | examiner (own) |
| GET | `/api/v1/bookings` | query `status`, `examination_id` | 200 list (own for students, own slots for examiners, all for admin) | any |
| POST | `/api/v1/bookings` | `{slot_id}` | 201 `{id, slot_id, examination_id, status, booked_at}` or 409 `slot_full` / `duplicate_booking` / `booking_closed` | student |
| DELETE | `/api/v1/bookings/<id>` | none | 200 `{id, status: "cancelled"}` | student (own) / admin |
| GET | `/api/v1/stats/summary` | none | `{courses, examinations, examiners, students, slots, bookings}` | admin |

Chart data endpoints (T2, same session auth): `GET /api/v1/charts/bookings-by-day`, `/charts/examiner-workload`, `/charts/examination-completion` return `{"labels": [...], "series": [{"name": "...", "data": [...]}]}`.

T2 extras: `GET /student/bookings/<id>/scorecard.pdf` (PDF), emails sent from services.

### 5.3 T3: Tests, attempts, proctoring (after Gate B)
| Method | Path | Request | Response | Roles |
|---|---|---|---|---|
| GET/POST | `/admin/tests`, `/examiner/tests` | form: `examination_id`, `title`, `instructions`, `delivery_mode`, `duration_minutes`, `questions_per_attempt`, `marks_per_question`, `negative_marks`, `pass_marks`, `available_from`, `available_until`, `max_violations`, `blur_grace_ms`, `require_fullscreen`, `result_publish_mode` | list / create | admin, examiner (own exams) |
| GET/POST | `/<role>/tests/<id>/questions` | `question_text`, `options[]` (2 to 6), `correct_index`, `marks` | list / add | admin, examiner |
| POST | `/<role>/tests/<id>/publish` | none | publish (needs at least 1 question, valid mode) | admin, examiner |
| GET | `/student/tests` | none | tests for booked examinations | student |
| POST | `/student/tests/<test_id>/attempts` | form: `accept_rules=on` | 302 to `/student/attempts/<id>/questions/0`; 409 `no_valid_booking`, `attempt_exists`, `test_not_open` | student |
| GET | `/student/attempts/<attempt_id>/questions/<position>` | none | HTML question page with remaining time; 409 `revisit_not_allowed` | student (own) |
| POST | `/student/attempts/<attempt_id>/answers` | JSON `{question_id, selected_option_id, marked_for_review}` | 200 `{"saved": true, "next_position": 3, "remaining_seconds": 1180}`; 409 `answer_locked`; 410 `attempt_closed` | student (own) |
| POST | `/student/attempts/<attempt_id>/submit` | none | 200 `{"status": "submitted", "redirect": "/student/attempts/12/result"}` (idempotent) | student (own) |
| GET | `/student/attempts/<attempt_id>/result` | none | score and per-question review (if allowed) | student (own) |
| POST | `/student/attempts/<attempt_id>/events` | JSON `{event_type, client_occurred_at, duration_ms, question_position}` | 200 `{"violation_count": 1, "max_violations": 1, "auto_submitted": true, "redirect": "/student/attempts/12/result"}` | student (own, in progress) |
| GET | `/admin/proctoring/reports` | query `test_id`, `student_id`, `from`, `to`, `min_violations` | HTML list of attempts | admin |
| GET | `/admin/proctoring/attempts/<attempt_id>` | none | event timeline | admin |
| GET | `/admin/proctoring/reports.csv` | same filters | CSV download | admin |
| POST | `/admin/attempts/<attempt_id>/reset` | `reason` | old attempt becomes `reset`; audit row | admin |
| POST | `/<role>/tests/<id>/results/publish` | none | publishes scores (manual mode) | admin, examiner |

### 5.4 T3: Payments
| Method | Path | Request | Response | Roles |
|---|---|---|---|---|
| POST | `/student/payments/orders` | JSON `{slot_id}` | 201 `{"payment_id": 5, "order_id": "order_abc", "amount": 50000, "currency": "INR", "key_id": "rzp_test_xxx", "hold_expires_at": "2026-12-01T10:10:00Z"}`; 409 `slot_full`, `duplicate_booking`, `booking_closed` | student |
| POST | `/student/payments/verify` | JSON `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` | 200 `{"status": "paid", "booking_id": 42}`; 400 `invalid_signature`; 409 `hold_expired` (payment is auto-refunded) | student |
| POST | `/student/payments/<id>/cancel` | none | 200 `{"status": "expired"}` releases the hold | student (own) |
| GET | `/student/payments` | none | own payments list | student |
| GET | `/admin/payments` | query `status`, `examination_id`, `from`, `to` | list and reconciliation flags | admin |
| POST | `/admin/examinations/<id>/fee` | form `amount_paise` | set fee (0 removes) | admin |

---

## 6. Security Design

- **Passwords:** Werkzeug `generate_password_hash` (scrypt default in Werkzeug 3) and `check_password_hash`; minimum 8 characters; never logged. Admin seed password comes from `ADMIN_INITIAL_PASSWORD` and the Admin is asked to change it on first login.
- **Sessions:** Flask signed cookie session (T1), replaced by Flask-Login in P11 (T2) with the same user loader. `session.clear()` before login to avoid fixation. Cookie flags: `HttpOnly`, `SameSite=Lax`, `Secure` when served over HTTPS. Idle timeout 30 minutes (`PERMANENT_SESSION_LIFETIME`); during an active test attempt the page heartbeat keeps the session alive.
- **CSRF:** Flask-WTF `CSRFProtect` globally. Forms include `{{ form.csrf_token }}` or `<input type="hidden" name="csrf_token">`; fetch calls send the `X-CSRFToken` header read from a `<meta name="csrf-token">` tag.
- **RBAC:** decorators `login_required`, `role_required('admin')`, and `approved_examiner_required` (checks `approval_status='approved'` and `is_active` on every request, not just login). Ownership is enforced in queries, for example `ExaminationSlot.query.filter_by(id=slot_id, examiner_id=current_user_id)` returns 404 for other examiners' slots. Students can only query bookings with `student_id == current_user_id`.
- **Input handling:** WTForms validators plus service-level checks; SQLAlchemy ORM parameters only (no string-built SQL); Jinja autoescape on; `rel="noopener"` on external links.
- **Admin protections:** no UI path creates an Admin; admin routes check `role == 'admin'` server-side; destructive actions are audit-logged.
- **Rate limiting (T2):** simple in-process limiter on `/login` (5 failures per 15 minutes per email+IP) via a small decorator (no extra dependency).
- **Secrets:** `.env` is git-ignored; `.env.example` has placeholders only.
- **T3 proctoring endpoint:** accepts events only for the caller's own `in_progress` attempt; server assigns `received_at`; client timestamps are informational; payload size limited to 1 KB; at most 30 events per minute per attempt. Whether a blur counts as a violation is decided server-side from `blur_grace_ms`, never by the client.
- **T3 payments:** server computes the amount from `examination_fees` (never from the client); signature check is HMAC-SHA256 of `order_id|payment_id` with `RAZORPAY_KEY_SECRET` using the SDK's `verify_payment_signature` (constant-time comparison); `razorpay_payment_id` is unique so a payment cannot confirm two bookings; the key secret is never sent to the browser (only `key_id`).

---

## 7. Frontend Technical Design

- **Framework:** none. Server-rendered **Jinja2** with **Bootstrap 5** (the only CSS framework allowed). Bootstrap files are vendored under `static/vendor/` so the demo works offline.
- **Templates:** `base.html` (head, flash messages, footer) extended by role bases: `admin/base_admin.html` (sidebar layout), `examiner/base_examiner.html` and `student/base_student.html` (top nav). Reusable macros: `macros/forms.html`, `macros/status_badge.html`, `macros/pagination.html`.
- **State management:** state lives on the server (database + session). Pages are stateless HTML. T1 uses no JavaScript for core requirements.
- **T2 JS:** Chart.js (vendored) for charts; small validation scripts (`static/js/validation.js`) that mirror server rules but never replace them.
- **T3 JS (vanilla, no framework):** `proctor.js` (Page Visibility, `blur`, `fullscreenchange`, `copy`/`cut`/`paste`/`contextmenu` listeners; posts to the events endpoint with the CSRF header; on `auto_submitted: true` redirects), `attempt_timer.js` (countdown from the server's `remaining_seconds`; display only), `razorpay_checkout.js` (opens Checkout with the order data and posts the three result values to `/verify`).
- **Forward-only UI:** the question page renders one question with a single "Save and next" button and no previous/jump controls; the server rejects anything else anyway.

---

## 8. Third-Party Integration Design

### 8.1 Email / OTP (T2)
- **Library:** Flask-Mail over SMTP. Dev: local debug SMTP (`python -m aiosmtpd -n -l localhost:1025`) or `MAIL_SUPPRESS_SEND=true`. Optional Gmail SMTP with an app password in env.
- **Templates:** `booking_confirmed`, `booking_cancelled`, `booking_rescheduled`, `examiner_approved`, `result_published` (T3 adds `test_auto_submitted`, `payment_received`, `refund_initiated`).
- **Behaviour:** sending happens after the DB commit, in a background thread started with `threading.Thread`; every attempt is recorded in `email_logs`; failures never roll back business actions.
- **OTP:** the PDR requires no OTP. Not included.

### 8.2 Payment Gateway (Sandbox): Razorpay (T3, after Gate B)
- **Mode:** test mode keys only (`rzp_test_...`). `RAZORPAY_MODE` is `test` or `mock`; `mock` uses a built-in fake gateway so the viva demo works with no internet.
- **Flow:**
  1. Student chooses a slot and POSTs `/student/payments/orders`.
  2. In one `BEGIN IMMEDIATE` transaction: window check, duplicate check, capacity check using `booked_count + active seat_holds < max_capacity`, create `payments(status='created')` and `seat_holds(status='active', expires_at=now+10 min)`.
  3. The server creates the Razorpay order (`amount` in paise, `currency='INR'`, `receipt='emp_<payment_id>'`) and returns checkout data.
  4. The browser opens Razorpay Checkout; on success it posts `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature` to `/verify`.
  5. The server verifies the signature; if valid and the hold is still active, it calls `booking_engine.book_slot()` (so every Tier 1 rule re-runs), then sets `payments.status='paid'`, `payments.booking_id`, hold `converted`.
  6. If the hold has expired or the booking engine fails after payment (for example a free-exam booking took the seat), the server issues an automatic refund and returns `hold_expired` or the specific error.
- **Policy hooks:** a `pre_booking_hooks` entry rejects direct bookings (`/student/slots/<id>/book`, `POST /api/v1/bookings`) for examinations with `amount_paise > 0` with `payment_required`. A `post_cancel_hooks` entry creates a refund for the booking's paid payment.
- **Refund:** `client.payment.refund(payment_id, {"amount": amount_paise})`; stored in `refunds`; payment becomes `refunded`.
- **Webhooks:** not used (a public URL is not available on a local machine). Correctness relies on the synchronous `/verify` call plus the expiry job. Noted as an open issue.
- **Failure handling:** gateway timeouts return a retryable error; the hold remains until expiry; the Admin payments page flags `created` payments older than 15 minutes for review.

---

## 9. Infrastructure & DevOps

- **Local dev (primary):** `python -m venv .venv`, `pip install -r requirements.txt`, `flask --app app init-db`, `flask --app app run --debug`.
- **Docker (optional):** `Dockerfile` (`python:3.12-slim`, non-root user, `gunicorn` not required for the demo) and `docker-compose.yml` with one service `app` plus a volume for `instance/`. A second compose profile `test` runs pytest offline.
- **Configuration:** `config.py` classes `DevConfig`, `TestConfig`, `ProdConfig`; all secrets from environment.
- **CI/CD (optional, GitHub Actions):** on push, run `ruff`, `black --check`, `pytest` (T1 and T2 always; T3 suites only when `tests/tier3` exists). No deployment step is needed for the course.
- **Git:** protected `main`; feature branches per phase; tags `tier1-complete` and `tier2-complete` mark the gates (details in the Master Blueprint).

---

## 10. Testing Strategy

All tests run offline, in isolated temp SQLite files, locally or inside the `test` Docker profile.

- **Unit (pytest):** `windows` helper, scoring, status transitions, forward-only pointer rules, signature verification (with known test vectors), proctor policy (grace period, strike counting).
- **Integration (pytest + Flask test client):** every route with each role (positive and 403/404 cases); booking engine under concurrency (20 threads on a 5-seat slot must end with exactly 5 bookings); reschedule and examiner change; evaluation limits; Admin seed idempotence.
- **E2E:** Playwright (Python) in a container, headless: register, approval, slot creation, booking, evaluation, results. T3 E2E: forward-only back navigation is rejected; switching tabs (emulated visibility change) auto-submits; timer expiry auto-submits; mock-gateway payment confirms a booking.
- **Contract tests (T2):** JSON schema checks of each API response; error shape checks.
- **Regression gate:** the full T1 and T2 suites must pass before every T3 merge (`make test-core`), then `make test-tier3`.
- **Coverage target:** 80% of services and routes; 100% of the booking engine and attempt engine branches.
- **Manual viva checklist:** one scripted demo path per role, rehearsed with flags on and off.

---

## 11. Business Logic Algorithms

Jobs are Flask CLI commands (`flask --app app jobs <name>`) that can run from cron or a loop. Correctness never depends on them: each rule is also enforced lazily when the data is read.

| Job | Schedule | Logic |
|---|---|---|
| `sync-exam-status` (T1) | every 5 min | For each non-deleted examination move `status` by dates and switches: `slot_creation` when the creation window is open, `booking_open` when booking is open, `closed` after `booking_end`, `completed` when all slots are past and evaluations are submitted. Also mark past slots `completed` and their `booked` bookings `completed`. |
| `purge-soft-deleted` (T1) | weekly | Hard-delete soft-deleted records older than 90 days only if they have no dependent bookings. |
| `retry-failed-emails` (T2) | every 10 min | Retry `email_logs.status='failed'` up to 3 times. |
| `expire-seat-holds` (T3) | every minute | `seat_holds` with `status='active'` and `expires_at < now` become `expired`; linked `payments` still `created` become `expired`. |
| `finalize-expired-attempts` (T3) | every minute | `test_attempts` in progress with `deadline_at < now` run `finalize_attempt(status='auto_submitted_timeout')`. |
| `purge-proctoring-events` (T3) | weekly | Delete `proctoring_events` older than `PROCTORING_RETENTION_DAYS` (default 180) for attempts that are final. |
| `reconcile-payments` (T3) | daily or on demand | Flag payments in `created` older than 15 minutes, or `paid` without a booking, in the Admin payments view. |

**Retention:** `audit_logs` are kept for the project's life; `email_logs` 90 days; proctoring events 180 days.

---

## 12. Error Handling & Logging

- **Log format:** `%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s user_id=%(user_id)s %(message)s`, written to console and `logs/emp.log` (rotating, 5 files of 1 MB).
- **Levels:** `INFO` business events (login, booking, evaluation submitted, test started/submitted, payment verified); `WARNING` rule rejections and violations (`slot_full`, `revisit_not_allowed`, proctoring violation, invalid signature); `ERROR` unexpected exceptions and gateway failures (with stack trace); `DEBUG` only in development. Never log passwords, tokens, signatures or Razorpay secrets.
- **Domain errors:** `BookingError`, `WindowError`, `PermissionDenied`, `AttemptError`, `PaymentError`, each carrying a stable `code`.
- **Error codes (user-facing):** `booking_closed`, `slot_full`, `duplicate_booking`, `slot_not_available`, `cancel_deadline_passed`, `not_approved`, `revisit_not_allowed`, `answer_locked`, `attempt_closed`, `attempt_exists`, `no_valid_booking`, `payment_required`, `invalid_signature`, `hold_expired`.
- **Message standards:** short, plain, actionable, no internals ("This slot is full. Please choose another slot."). HTML routes use flash messages (`danger`, `warning`, `success`, `info`); JSON routes use the error shape in section 5. Custom 403, 404 and 500 pages; 500 shows a reference `request_id` only.

---

## 13. Operational Runbook

```bash
# 1. Setup
git clone <your-private-repo> && cd emp
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # edit SECRET_KEY, ADMIN_* values

# 2. Create database and seed Admin (programmatic, idempotent)
flask --app app init-db

# 3. Run
flask --app app run --debug                             # http://127.0.0.1:5000

# 4. Tests
pytest tests/unit tests/integration -q                  # Tier 1 and Tier 2
pytest tests/e2e -q                                     # needs Playwright browsers installed
make test-core                                          # unit + integration + e2e for T1/T2
make test-tier3                                         # only after Gate B

# 5. Jobs (manual)
flask --app app jobs sync-exam-status
flask --app app jobs expire-seat-holds                  # T3
flask --app app jobs finalize-expired-attempts          # T3

# 6. Optional: local mail sink (T2)
python -m aiosmtpd -n -l localhost:1025

# 7. Optional: Docker
docker compose up --build
docker compose --profile test run --rm test

# 8. Lint
ruff check . && black --check .

# 9. Tier 3 enable (only after Gate B)
# set ENABLE_ONLINE_TESTS=true / ENABLE_PROCTORING=true / ENABLE_PAYMENTS=true in .env, then:
flask --app app init-db                                 # creates the new T3 tables only
```
Migrations: if any T1/T2 column changes later, use Flask-Migrate with `render_as_batch=True` (SQLite). The T3 design avoids this by adding tables only.

---

## 14. Technical Dependencies & Licenses

*Licenses are from general knowledge; confirm each package's current license file before submission.*

| Package / library | Purpose | Tier | License |
|---|---|---|---|
| Flask, Werkzeug, Jinja2 | Web framework, hashing, templates | 1 | BSD-3-Clause |
| Flask-SQLAlchemy, SQLAlchemy | ORM | 1 | BSD-3-Clause, MIT |
| Flask-WTF, WTForms | Forms and CSRF | 1 | BSD-3-Clause |
| python-dotenv | `.env` loading | 1 | BSD-3-Clause |
| pytest, pytest-cov | Testing | 1 | MIT |
| ruff, black | Lint and format | 1 | MIT |
| Bootstrap 5 | UI | 1 | MIT |
| Flask-Login (or Flask-Security-Too) | Sessions and RBAC | 2 | MIT / MIT |
| Flask-RESTful | API (optional) | 2 | BSD-3-Clause |
| Flask-Mail, aiosmtpd | Email, dev SMTP sink | 2 | BSD-3-Clause, Apache-2.0 |
| Flask-Migrate (Alembic) | Migrations if needed | 2 | MIT |
| ReportLab | Scorecard PDF | 2 | BSD-3-Clause |
| Chart.js | Charts | 2 | MIT |
| Playwright (Python) | E2E tests | 2/3 | Apache-2.0 |
| `razorpay` Python SDK | Payments | 3 | MIT |
| Razorpay Checkout JS (hosted script) | Payment popup | 3 | Razorpay service terms (not open source) |

---

## 15. Open Issues & Decisions Pending

1. **Test types:** the request described two kinds; this design uses three delivery modes (`standard`, `random_forward_only`, `random_revisitable`). Confirm. A different split only changes the `delivery_mode` enum and `get_question` rules.
2. **Cancellation deadline:** the statement says "booking deadline" without a separate field; `cancellation_deadline` defaults to `booking_end` but is stored separately. Confirm.
3. **Multiple examiners per examination:** modelled with `examination_examiners` (many-to-many). Confirm the course intent.
4. **Timezone:** UTC storage with `Asia/Kolkata` display is a default; confirm for the viva machine.
5. **Anti-cheat limits:** a browser cannot report which application the student opened. The Admin report will show when and for how long the student left. Confirm this meets the intended requirement.
6. **Razorpay offline demo:** the viva machine may have no internet; `mock` mode covers this, but evaluators may expect real test-mode checkout.
7. **Webhooks:** skipped for the local setup; real deployments would need them for payment reliability.
8. **Examiner authoring tests:** assumed allowed for their own examinations. Confirm.
9. **Email provider:** Gmail SMTP vs local sink for the demo is undecided.

---

## 16. Appendix: Environment Variable Reference

```dotenv
# --- Core (T1) ---
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=change-me-to-a-long-random-string
DATABASE_URL=sqlite:///instance/emp.db
APP_TIMEZONE=Asia/Kolkata
ADMIN_EMAIL=admin@example.edu
ADMIN_FULL_NAME=System Admin
ADMIN_INITIAL_PASSWORD=change-me-on-first-login
SESSION_COOKIE_SECURE=false
PERMANENT_SESSION_LIFETIME_MINUTES=30
LOG_LEVEL=INFO
LOG_FILE=logs/emp.log

# --- Tier 2 ---
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=emp@example.edu
MAIL_SUPPRESS_SEND=true
LOGIN_RATE_LIMIT_FAILURES=5
LOGIN_RATE_LIMIT_WINDOW_MINUTES=15

# --- Tier 3 feature flags (all false until Gate B) ---
ENABLE_ONLINE_TESTS=false
ENABLE_PROCTORING=false
ENABLE_PAYMENTS=false
PROCTORING_RETENTION_DAYS=180
PROCTORING_DEFAULT_MAX_VIOLATIONS=1
PROCTORING_DEFAULT_BLUR_GRACE_MS=1000

# --- Tier 3 Razorpay (test mode only) ---
RAZORPAY_MODE=mock            # mock | test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
SEAT_HOLD_MINUTES=10
```
