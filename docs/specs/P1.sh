#!/usr/bin/env bash
# =====================================================================
# P1.sh - Milestone M1: Database Models & Schema (Tier 1, Primary)
# Course commit message : Milestone-1 EMP-Database-Models
# Branch                : phase/p1-database-models
# Depends on            : P0 (tag p0-done)
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files for the LLM implementation step.
# Existing P0 files are NEVER overwritten; changes to them are described
# in docs/seed_updates/P1_update_app_init.md.
# =====================================================================
set -euo pipefail

PHASE="P1"
BRANCH="phase/p1-database-models"
PREV_TAG="p0-done"

# ---------------------------------------------------------------------
# Pre-flight checks (infrastructure only)
# ---------------------------------------------------------------------
[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P0 first."; exit 1; }
[ -f app/__init__.py ] || { echo "ERROR: app/__init__.py missing (P0 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P1 needs)
# ---------------------------------------------------------------------
mkdir -p app/models tests/unit tests/integration docs/seed_updates instance logs

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# =============================== CORE ================================

cat << 'EOF' > app/config.py
"""
FILE PURPOSE: Configuration classes (Dev, Test, Prod) built only from environment variables.
DEPENDS ON: .env / .env.example from P0.
PROMPT FOR LLM IMPLEMENTATION:
1. Define BaseConfig plus DevConfig, TestConfig, ProdConfig and a function get_config(name: str | None) -> type. When name is None, choose from FLASK_ENV: "development" -> DevConfig, "testing" -> TestConfig, "production" -> ProdConfig, default DevConfig.
2. Read these variables with os.environ.get (python-dotenv is loaded by Flask automatically): SECRET_KEY, DATABASE_URL (default sqlite:///instance/emp.db), APP_TIMEZONE (default Asia/Kolkata), ADMIN_EMAIL, ADMIN_FULL_NAME (default "System Admin"), ADMIN_INITIAL_PASSWORD, SESSION_COOKIE_SECURE (string "true"/"false" -> bool, default false), PERMANENT_SESSION_LIFETIME_MINUTES (int, default 30), LOG_LEVEL (default INFO), LOG_FILE (default logs/emp.log).
3. SQLITE PATH TRAP (important): Flask-SQLAlchemy 3 resolves a RELATIVE sqlite path against app.instance_path, so sqlite:///instance/emp.db would end up at instance/instance/emp.db. Write a helper that converts any relative sqlite:/// path into an ABSOLUTE path anchored at the PROJECT ROOT (the parent folder of the app package), so sqlite:///instance/emp.db always means <root>/instance/emp.db. Absolute URLs (sqlite:////tmp/x.db) pass through unchanged. Set SQLALCHEMY_DATABASE_URI from the result and SQLALCHEMY_TRACK_MODIFICATIONS = False.
4. Session settings on BaseConfig: SESSION_COOKIE_HTTPONLY = True, SESSION_COOKIE_SAMESITE = "Lax", SESSION_COOKIE_SECURE from env, PERMANENT_SESSION_LIFETIME = timedelta(minutes=PERMANENT_SESSION_LIFETIME_MINUTES).
5. DevConfig: DEBUG = True; if SECRET_KEY is missing use the fixed string "dev-only-change-me" and log a warning at app start (never in Prod).
6. TestConfig: TESTING = True, WTF_CSRF_ENABLED = False (one dedicated test in P2 turns it back on), SECRET_KEY = "test-secret", SERVER_NAME unset, ADMIN_* default to admin@test.local / "Test Admin" / "Admin#Test123". The test DB URI is injected by the pytest fixture, not hard-coded.
7. ProdConfig: DEBUG = False; raise RuntimeError at import/creation time if SECRET_KEY is missing or equals the dev placeholder.
8. Expose constants (not secrets) used elsewhere: DEFAULT_PAGE_SIZE = 20, MAX_PAGE_SIZE = 100, MIN_PASSWORD_LENGTH = 8.
9. Do NOT read any MAIL_*, ENABLE_*, RAZORPAY_* or PROCTORING_* variables (Tier 2 / Tier 3).
DEBUGGING:
# print(f"[DEBUG] config={cls.__name__} db_uri={uri} (password values must never be printed)")
OFFLINE DOCKER TEST CASES:
- get_config("testing") returns TestConfig; get_config(None) with FLASK_ENV unset returns DevConfig.
- DATABASE_URL=sqlite:///instance/emp.db resolves to <project_root>/instance/emp.db (absolute) and the instance/instance folder is never created.
- ProdConfig without SECRET_KEY raises RuntimeError.
- PERMANENT_SESSION_LIFETIME_MINUTES=45 yields timedelta(minutes=45).
"""
EOF

cat << 'EOF' > app/extensions.py
"""
FILE PURPOSE: Single place for shared Flask extension objects, the SQLite pragma hook and the timestamp mixin.
DEPENDS ON: Flask-SQLAlchemy, Flask-WTF.
PROMPT FOR LLM IMPLEMENTATION:
1. Create db = SQLAlchemy(metadata=MetaData(naming_convention=...)) with the standard convention: ix_%(column_0_label)s, uq_%(table_name)s_%(column_0_name)s, ck_%(table_name)s_%(constraint_name)s, fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s, pk_%(table_name)s. This keeps constraint names stable for tests and for Flask-Migrate batch mode later.
2. Create csrf = CSRFProtect() but do NOT call init_app in this phase (P2 does it). Only the object is defined here so P2 never needs to edit this file.
3. Define TimestampMixin with two columns: created_at (DateTime, not null, server_default current_timestamp) and updated_at (DateTime, not null, server_default current_timestamp, onupdate current_timestamp). SQLite CURRENT_TIMESTAMP is UTC, matching the TDR rule "store naive UTC".
4. Define a function register_sqlite_pragmas() that attaches ONE "connect" event listener to sqlalchemy.engine.Engine. The listener must first check isinstance(dbapi_connection, sqlite3.Connection) and then execute: PRAGMA foreign_keys=ON, PRAGMA journal_mode=WAL, PRAGMA busy_timeout=5000. Make the function idempotent (calling it twice must not attach two listeners).
5. IMPORTANT: do NOT set dbapi_connection.isolation_level = None and do NOT add the "begin" BEGIN IMMEDIATE listener here. TDR section 3.2 requires them TOGETHER; they are added in P6. Setting only the first half would silently disable transactions.
6. Expose init_extensions(app) that calls register_sqlite_pragmas() and db.init_app(app) (and nothing else in P1).
DEBUGGING:
# print(f"[DEBUG] pragma listener attached; foreign_keys={cursor.execute('PRAGMA foreign_keys').fetchone()}")
OFFLINE DOCKER TEST CASES:
- After create_app(), "PRAGMA foreign_keys" returns 1 and "PRAGMA journal_mode" returns "wal" on a file database.
- "PRAGMA busy_timeout" returns 5000.
- Calling register_sqlite_pragmas() twice leaves exactly one listener (assert via sqlalchemy.event.contains).
- Constraint names in the generated DDL follow the naming convention (e.g. ck_users_role_valid).
"""
EOF

cat << 'EOF' > app/logging_config.py
"""
FILE PURPOSE: Structured logging with a per-request id and the current user id (TDR section 12).
DEPENDS ON: app/config.py values LOG_LEVEL, LOG_FILE.
PROMPT FOR LLM IMPLEMENTATION:
1. Define setup_logging(app) that configures the root "emp" logger: console handler plus RotatingFileHandler on LOG_FILE (maxBytes 1_000_000, backupCount 5, create the logs/ folder if missing). Format exactly: %(asctime)s %(levelname)s %(name)s request_id=%(request_id)s user_id=%(user_id)s %(message)s
2. Add a logging.Filter that injects request_id and user_id into every record: values come from flask.g when inside a request context, otherwise "-". user_id is read defensively with getattr(g, "user", None) because authentication arrives in P2.
3. Idempotency: calling setup_logging twice (tests create many apps) must not add duplicate handlers; clear or check existing handlers first.
4. Define register_request_logging(app): a before_request that sets g.request_id = uuid4().hex[:12], and an after_request that adds the header X-Request-ID and logs one INFO line "METHOD path -> status" . Never log request bodies, passwords, tokens or headers.
5. In TestConfig skip the file handler (console only, level WARNING) to keep tests quiet.
6. Log level comes from LOG_LEVEL; invalid values fall back to INFO.
DEBUGGING:
# print(f"[DEBUG] handlers={[type(h).__name__ for h in logging.getLogger('emp').handlers]}")
OFFLINE DOCKER TEST CASES:
- After create_app() twice, logging.getLogger("emp").handlers has the same length as after once.
- A request to "/" returns an X-Request-ID header of 12 hex characters.
- A log record emitted outside a request renders request_id=- user_id=- without raising.
- No log line contains the string of the ADMIN_INITIAL_PASSWORD after running init-db.
"""
EOF

cat << 'EOF' > app/cli.py
"""
FILE PURPOSE: Flask CLI commands. P1 delivers "init-db": programmatic database creation plus the idempotent Admin seed (course rule: DB must be created by code, Admin pre-exists).
DEPENDS ON: app/extensions.py, app/models, app/config.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Provide two plain, individually testable functions (not hidden inside the click command): create_database() runs db.create_all() inside the current app context and returns the sorted list of table names; seed_admin() creates the Admin and returns one of the strings "created", "exists".
2. seed_admin() rules: read ADMIN_EMAIL, ADMIN_FULL_NAME, ADMIN_INITIAL_PASSWORD from app.config. If ADMIN_EMAIL or ADMIN_INITIAL_PASSWORD is empty, raise a clear click.ClickException ("Set ADMIN_EMAIL and ADMIN_INITIAL_PASSWORD in .env") - never invent a default password. Normalise the email with strip().lower(). If a user with that email already exists AND role is admin, return "exists" WITHOUT touching the password or any field (idempotent). If that email exists with another role, raise ClickException. Otherwise create User(role="admin", approval_status="approved", is_active=True, must_change_password=True) using set_password(). Commit once.
3. Register the command with @click.command("init-db") and a register_cli(app) function that calls app.cli.add_command. init-db flow: ensure app.instance_path exists, create_database(), seed_admin(), then print: the DB file path, the number of tables (12 expected in Tier 1), and "Admin created: <email>" or "Admin already exists: <email>". NEVER print the password.
4. The command must be safe to run any number of times and must not drop or alter existing tables or data.
5. Do not add the "jobs" command group yet (the sync-exam-status job arrives in P6).
6. Expose EXPECTED_TIER1_TABLES (a tuple of the 12 table names) for the tests and for a final sanity check in init-db that warns if a table is missing.
DEBUGGING:
# print(f"[DEBUG] init-db: tables={tables} admin_status={status}")
OFFLINE DOCKER TEST CASES:
- On an empty temp DB, init-db creates 12 tables and exactly 1 user with role "admin".
- Running init-db a second time prints "Admin already exists" and the user count stays 1; password_hash is unchanged.
- With ADMIN_INITIAL_PASSWORD unset, init-db exits non-zero with the helpful message and creates no user.
- Output of init-db never contains the plain-text password.
"""
EOF

cat << 'EOF' > docs/seed_updates/P1_update_app_init.md
<!--
FILE PURPOSE: Update prompt for app/__init__.py (already implemented in P0 as a placeholder app). Do not regenerate it from scratch.
HOW TO USE: give your LLM this prompt plus the CURRENT app/__init__.py and ask for the full updated file.
PROMPT FOR LLM IMPLEMENTATION:
1. Change create_app(config_name=None) so it loads config with get_config(config_name) from app/config.py (app.config.from_object). Keep instance_relative_config=True and keep creating the instance folder.
2. Call setup_logging(app) and register_request_logging(app) from app/logging_config.py, then init_extensions(app) from app/extensions.py (db and the SQLite pragma hook only; do NOT call csrf.init_app yet).
3. Import the app.models package inside the factory (import app.models) purely so every table is registered on db.metadata; do not import any model name into the module namespace.
4. Call register_cli(app) from app/cli.py so "flask --app app init-db" works.
5. Keep the P0 placeholder route "/" and its text exactly as is (P2 replaces it). Do not register any blueprint.
6. The P0 tests in tests/unit/test_smoke_app.py must still pass unchanged.
7. create_app must never touch the database at import time or on startup (tables are created only by init-db).
DEBUGGING:
# print(f"[DEBUG] create_app: config={app.config['ENV'] if 'ENV' in app.config else type(cfg).__name__} db={app.config['SQLALCHEMY_DATABASE_URI']}")
OFFLINE DOCKER TEST CASES:
- pytest tests/unit/test_smoke_app.py still passes (3 tests).
- flask --app app init-db works after this change on a clean checkout.
- create_app("testing") and create_app("development") use different config classes.
-->
EOF

# =============================== MODELS ==============================

cat << 'EOF' > app/models/__init__.py
"""
FILE PURPOSE: Import every Tier 1 model so db.metadata knows all 12 tables, and document the conventions shared by all models.
DEPENDS ON: every module in app/models/.
PROMPT FOR LLM IMPLEMENTATION:
1. Import and re-export (via __all__) these classes: User, ExaminerProfile, StudentProfile, Course, Examination, ExaminationRubric, ExaminationExaminer, ExaminationSlot, Booking, Evaluation, EvaluationScore, AuditLog. Import order must follow foreign-key dependency (users first).
2. Do NOT import anything from a tier3 package or email_log (Tier 2 adds EmailLog in P12).
3. In the module docstring list the shared conventions every model file follows: (a) snake_case names; (b) integer primary key with __table_args__ containing {"sqlite_autoincrement": True} so DDL says AUTOINCREMENT as in TDR section 1; (c) timestamps are naive UTC via TimestampMixin; (d) enumerations are stored as lowercase snake_case strings with a named CheckConstraint built from a module-level tuple constant (for example ROLES) so forms and services can reuse the tuple; (e) booleans are Boolean columns with explicit server_default "0"/"1"; (f) every foreign key declares ondelete="RESTRICT" (history must never vanish, risk R-7); (g) no cascade="all, delete-orphan" anywhere except Evaluation.scores; (h) models contain NO business logic beyond tiny helpers (properties, set_password); rules live in services (P3 to P6).
4. Provide a tuple ALL_TABLE_NAMES with the 12 table names for tests.
DEBUGGING:
# print(f"[DEBUG] metadata tables: {sorted(db.metadata.tables)}")
OFFLINE DOCKER TEST CASES:
- sorted(db.metadata.tables) equals the 12 Tier 1 names exactly (no email_logs, no Tier 3 tables).
- Importing app.models twice has no side effects.
"""
EOF

cat << 'EOF' > app/models/user.py
"""
FILE PURPOSE: Table "users": one row per Admin, Examiner or Student account.
DEPENDS ON: app/extensions.py (db, TimestampMixin), Werkzeug.
PROMPT FOR LLM IMPLEMENTATION:
1. Class User(db.Model, TimestampMixin), __tablename__ = "users". Columns (TDR 4.1): id INTEGER PK; email TEXT unique not null; password_hash TEXT not null; full_name TEXT not null; role TEXT not null; approval_status TEXT not null default "approved"; is_active BOOLEAN not null default 1; last_login_at DATETIME null; plus created_at/updated_at from the mixin.
2. ADDITION TO THE TDR (needed by Design Plan screen PUB-05 and the Admin temporary-password flow): must_change_password BOOLEAN not null default 0. Add a comment in the file "TDR 4.1 update: users.must_change_password" so the TDR can be patched later.
3. Constants: ROLES = ("admin","examiner","student"); APPROVAL_STATUSES = ("pending","approved","rejected"). CheckConstraints named role_valid and approval_status_valid built from these tuples.
4. Indexes: ix_users_role on role, ix_users_full_name on full_name. email is stored lowercase; add a CHECK that email = lower(email) named email_lowercase so case-variant duplicates are impossible at the database level.
5. Helpers only: set_password(raw) using werkzeug.security.generate_password_hash (default scrypt), check_password(raw) using check_password_hash, properties is_admin / is_examiner / is_student, and __repr__ showing id, email, role only (never the hash).
6. Meaning of the flags (document in comments, enforced in P2/P3): examiners register with approval_status "pending"; students and the seeded admin are "approved"; deactivation sets is_active False.
7. Relationships: one-to-one examiner_profile and student_profile (uselist=False, back_populates), no cascades.
DEBUGGING:
# print(f"[DEBUG] User created id={user.id} role={user.role} approval={user.approval_status}")
OFFLINE DOCKER TEST CASES:
- Inserting role "superuser" raises IntegrityError; inserting approval_status "maybe" raises IntegrityError.
- Two users with the same email (even differing only by case) cannot both be stored (unique or lowercase CHECK trips).
- set_password then check_password returns True for the right password and False for a wrong one; password_hash never equals the raw password.
- A user created with only required fields has is_active True, approval_status "approved", must_change_password False.
"""
EOF

cat << 'EOF' > app/models/examiner_profile.py
"""
FILE PURPOSE: Table "examiner_profiles": extra details for users whose role is examiner.
DEPENDS ON: app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class ExaminerProfile(db.Model, TimestampMixin), __tablename__ = "examiner_profiles". Columns: id PK; user_id INTEGER FK users.id unique not null (ondelete RESTRICT); contact_phone TEXT null; department TEXT null; designation TEXT null; status TEXT not null default "active" with CheckConstraint status_valid in ("active","inactive").
2. Constant PROFILE_STATUSES = ("active","inactive"). Relationship user (back_populates examiner_profile).
3. Comment: "deactivate" in P3 will set BOTH users.is_active = False and this status = "inactive"; request-time checks (P2) read users.is_active.
4. Do not enforce that the linked user's role is examiner at DB level (cross-table); P2 registration creates the row only for role examiner, and a test covers it.
DEBUGGING:
# print(f"[DEBUG] ExaminerProfile user_id={self.user_id} status={self.status}")
OFFLINE DOCKER TEST CASES:
- Two profiles for the same user_id raise IntegrityError.
- status "retired" raises IntegrityError.
- user.examiner_profile returns the profile; deleting a user that has a profile raises IntegrityError (RESTRICT).
"""
EOF

cat << 'EOF' > app/models/student_profile.py
"""
FILE PURPOSE: Table "student_profiles": extra details for users whose role is student.
DEPENDS ON: app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class StudentProfile(db.Model, TimestampMixin), __tablename__ = "student_profiles". Columns: id PK; user_id INTEGER FK users.id unique not null (ondelete RESTRICT); roll_number TEXT unique null; contact_phone TEXT null; program TEXT null.
2. roll_number is nullable and unique: SQLite allows many NULLs, so students without a roll number do not clash. Add a comment saying so.
3. Relationship user (back_populates student_profile).
DEBUGGING:
# print(f"[DEBUG] StudentProfile user_id={self.user_id} roll={self.roll_number}")
OFFLINE DOCKER TEST CASES:
- Two students with roll_number NULL can both be stored.
- Two students with the same non-null roll_number raise IntegrityError.
- Two profiles for the same user_id raise IntegrityError.
"""
EOF

cat << 'EOF' > app/models/course.py
"""
FILE PURPOSE: Table "courses": the academic course an examination belongs to.
DEPENDS ON: app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class Course(db.Model, TimestampMixin), __tablename__ = "courses". Columns: id PK; code TEXT unique not null; name TEXT not null; description TEXT null; status TEXT not null default "active" with CheckConstraint status_valid in ("active","inactive"); created_by INTEGER FK users.id not null (RESTRICT).
2. Constant COURSE_STATUSES. Relationships: examinations (one-to-many, no cascade, lazy "select") and creator (many-to-one to User).
3. code is compared case-insensitively in forms (P3); here only enforce unique. Add index ix_courses_status.
4. Deleting a course that has examinations must fail at DB level (RESTRICT); P3 uses status "inactive" instead of delete.
DEBUGGING:
# print(f"[DEBUG] Course {self.code} status={self.status}")
OFFLINE DOCKER TEST CASES:
- Duplicate code raises IntegrityError; missing name raises IntegrityError.
- Status "archived" raises IntegrityError.
- Deleting a course with an examination raises IntegrityError.
"""
EOF

cat << 'EOF' > app/models/examination.py
"""
FILE PURPOSE: Table "examinations": an exam (viva, practical, project demo, assessment) with its two time windows and two Admin switches.
DEPENDS ON: app/models/course.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class Examination(db.Model, TimestampMixin), __tablename__ = "examinations". Columns: id PK; course_id FK courses.id not null; name TEXT not null; description TEXT null; exam_type TEXT not null; duration_minutes INTEGER not null; max_marks INTEGER not null; slot_creation_start, slot_creation_end, booking_start, booking_end, cancellation_deadline all DATETIME not null; slot_creation_open BOOLEAN not null default 0; booking_open BOOLEAN not null default 0; status TEXT not null default "draft"; is_deleted BOOLEAN not null default 0.
2. Constants: EXAM_TYPES = ("viva","practical","project_demo","assessment"); EXAM_STATUSES = ("draft","slot_creation","booking_open","closed","completed").
3. CheckConstraints (named): exam_type_valid, status_valid, duration_positive (duration_minutes > 0), max_marks_positive (max_marks > 0), creation_window_order (slot_creation_start < slot_creation_end), booking_window_order (booking_start < booking_end), windows_do_not_overlap (slot_creation_end <= booking_start).
4. cancellation_deadline is NOT NULL but defaults to booking_end: implement this with a before_insert mapper event (or a @validates hook) that copies booking_end when cancellation_deadline is None. Document why a plain column default cannot do this.
5. Index ix_examinations_course_id. Relationships: course, rubrics, slots, examiner_links (to ExaminationExaminer); none with delete cascades. Soft delete only (is_deleted); no hard-delete helper.
6. Helper properties (read-only, no DB access): is_deleted_flag not needed; do not add window logic here. Window checks belong to app/services/windows.py in P3.
DEBUGGING:
# print(f"[DEBUG] Examination {self.id} type={self.exam_type} booking={self.booking_start}->{self.booking_end} open={self.booking_open}")
OFFLINE DOCKER TEST CASES:
- booking_start >= booking_end raises IntegrityError; slot_creation_end later than booking_start raises IntegrityError.
- duration_minutes 0 or max_marks -5 raises IntegrityError.
- exam_type "quiz" and status "paused" raise IntegrityError.
- Creating an examination without cancellation_deadline stores booking_end in that column.
- A new examination has status "draft", both switches 0, is_deleted 0.
"""
EOF

cat << 'EOF' > app/models/rubric.py
"""
FILE PURPOSE: Table "examination_rubrics": scoring criteria used by examiners during evaluation.
DEPENDS ON: app/models/examination.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class ExaminationRubric(db.Model), __tablename__ = "examination_rubrics" (no timestamp mixin per TDR). Columns: id PK; examination_id FK examinations.id not null; criterion_name TEXT not null; description TEXT null; weightage NUMERIC(5,2) not null; max_score NUMERIC(6,2) not null; position INTEGER not null default 0.
2. CheckConstraints: weightage_range (weightage >= 0 AND weightage <= 100), max_score_positive (max_score > 0). UniqueConstraint (examination_id, criterion_name).
3. Index on examination_id. Relationship examination (back_populates rubrics, order_by position).
4. Comment: SQLite stores NUMERIC as float; services compare with a tolerance. The rule "weightages of one examination must total 100" is a P3 service rule, not a DB constraint.
DEBUGGING:
# print(f"[DEBUG] Rubric exam={self.examination_id} {self.criterion_name} w={self.weightage} max={self.max_score}")
OFFLINE DOCKER TEST CASES:
- Duplicate criterion_name inside one examination raises IntegrityError; the same name in a different examination is allowed.
- weightage 101 or -1 raises IntegrityError; max_score 0 raises IntegrityError.
"""
EOF

cat << 'EOF' > app/models/examination_examiner.py
"""
FILE PURPOSE: Junction table "examination_examiners": which examiners are assigned to which examination (many-to-many).
DEPENDS ON: app/models/examination.py, app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class ExaminationExaminer(db.Model), __tablename__ = "examination_examiners". Columns: id PK; examination_id FK examinations.id not null; examiner_id FK users.id not null; assigned_by FK users.id not null; assigned_at DATETIME not null with server_default current_timestamp.
2. UniqueConstraint (examination_id, examiner_id). Indexes on both foreign keys.
3. Relationships: examination (back_populates examiner_links), examiner (User), assigner (User, foreign_keys explicit because two FKs point to users - set foreign_keys on each relationship to avoid SQLAlchemy ambiguity errors).
4. Comment: P3 only assigns users whose role is examiner and approval_status is approved; that check is in the service, not here.
DEBUGGING:
# print(f"[DEBUG] assignment exam={self.examination_id} examiner={self.examiner_id} by={self.assigned_by}")
OFFLINE DOCKER TEST CASES:
- Assigning the same examiner twice to one examination raises IntegrityError.
- Mapper configuration succeeds (no AmbiguousForeignKeysError) - assert via sqlalchemy.orm.configure_mappers().
- Assigning an examiner id that does not exist raises IntegrityError (foreign keys are ON).
"""
EOF

cat << 'EOF' > app/models/slot.py
"""
FILE PURPOSE: Table "examination_slots": a bookable time slot created by an examiner, with capacity.
DEPENDS ON: app/models/examination.py, app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class ExaminationSlot(db.Model, TimestampMixin), __tablename__ = "examination_slots". Columns: id PK; examination_id FK examinations.id not null; examiner_id FK users.id not null; start_at DATETIME not null; end_at DATETIME not null; max_capacity INTEGER not null; booked_count INTEGER not null default 0; status TEXT not null default "available".
2. Constant SLOT_STATUSES = ("available","full","cancelled","completed"). CheckConstraints: status_valid; time_order (end_at > start_at); capacity_positive (max_capacity > 0); booked_count_in_range (booked_count >= 0 AND booked_count <= max_capacity). This last constraint is the DATABASE-LEVEL guard against overbooking (invariant 1 in TDR 3.1).
3. Indexes ix_slots_examination_id and ix_slots_examiner_id. Relationships: examination, examiner (User), bookings (one-to-many, no cascade).
4. Read-only property seats_left = max_capacity - booked_count (never negative). No other logic; booking/cancel logic belongs to booking_engine in P5/P6.
5. Comment: "no two slots of the same examiner may overlap" is a P4 service rule.
DEBUGGING:
# print(f"[DEBUG] Slot {self.id} {self.start_at}->{self.end_at} {self.booked_count}/{self.max_capacity} {self.status}")
OFFLINE DOCKER TEST CASES:
- booked_count 6 with max_capacity 5 raises IntegrityError; booked_count -1 raises IntegrityError.
- end_at equal to start_at raises IntegrityError; max_capacity 0 raises IntegrityError.
- status "open" raises IntegrityError.
- seats_left is 3 for capacity 5 and booked_count 2.
"""
EOF

cat << 'EOF' > app/models/booking.py
"""
FILE PURPOSE: Table "bookings": a student's seat in a slot; the heart of the capacity engine data model.
DEPENDS ON: app/models/slot.py, app/models/examination.py, app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class Booking(db.Model, TimestampMixin), __tablename__ = "bookings". Columns: id PK; student_id FK users.id not null; slot_id FK examination_slots.id not null; examination_id FK examinations.id not null (DENORMALISED on purpose so the partial unique index can span student and examination); status TEXT not null default "booked"; booked_at DATETIME not null; cancelled_at DATETIME null; cancelled_by FK users.id null; rescheduled_from_slot_id FK examination_slots.id null.
2. Constant BOOKING_STATUSES = ("booked","cancelled","completed"); CheckConstraint status_valid.
3. PARTIAL UNIQUE INDEX (core business rule R-2): name uq_bookings_active_student_exam on (student_id, examination_id) with sqlite_where condition status IN ('booked','completed'). Cancelled rows are exempt so a student may re-book after cancelling.
4. Indexes ix_bookings_slot_id and ix_bookings_student_id.
5. Relationships: student, slot (foreign_keys explicit), examination, canceller, rescheduled_from, evaluation (one-to-one, uselist=False). With several FKs to users and slots, set foreign_keys on every relationship.
6. Invariant to document in a comment and test in P5: examination_id must equal slot.examination_id. Booking creation in booking_engine always copies it from the slot; do not add a cross-table CHECK.
7. booked_at has no default here: the service sets it from now_utc() so tests control time.
DEBUGGING:
# print(f"[DEBUG] Booking {self.id} student={self.student_id} slot={self.slot_id} exam={self.examination_id} status={self.status}")
OFFLINE DOCKER TEST CASES:
- Two bookings (booked) for the same student and examination raise IntegrityError, even in different slots.
- Booked + cancelled for the same pair is allowed; cancelled + cancelled is allowed; booked + completed is rejected.
- status "pending" raises IntegrityError; a missing booked_at raises IntegrityError.
- Mapper configuration succeeds with no ambiguous foreign key errors.
"""
EOF

cat << 'EOF' > app/models/evaluation.py
"""
FILE PURPOSE: Tables "evaluations" and "evaluation_scores": an examiner's marks and remarks for one booking, scored per rubric criterion.
DEPENDS ON: app/models/booking.py, app/models/rubric.py, app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class Evaluation(db.Model, TimestampMixin), __tablename__ = "evaluations". Columns: id PK; booking_id FK bookings.id unique not null (one evaluation per booking); examiner_id FK users.id not null (the examiner who ACTUALLY evaluated; may differ from the slot's current examiner after an Admin change); total_marks NUMERIC(6,2) not null default 0 with CheckConstraint total_marks_non_negative; remarks TEXT null; status TEXT not null default "draft"; submitted_at DATETIME null; published_at DATETIME null.
2. Constant EVALUATION_STATUSES = ("draft","submitted","published"); CheckConstraint status_valid.
3. Class EvaluationScore(db.Model), __tablename__ = "evaluation_scores". Columns: id PK; evaluation_id FK evaluations.id not null; rubric_id FK examination_rubrics.id not null; score NUMERIC(6,2) not null with CheckConstraint score_non_negative; comment TEXT null. UniqueConstraint (evaluation_id, rubric_id).
4. Relationship Evaluation.scores to EvaluationScore with cascade="all, delete-orphan" (the ONLY cascade in the project) and EvaluationScore.evaluation back_populates; Evaluation.booking and Evaluation.examiner many-to-one.
5. Comment the service rules enforced in P4: score <= rubric.max_score and total_marks <= examination.max_marks; students can read only status "published" evaluations.
DEBUGGING:
# print(f"[DEBUG] Evaluation booking={self.booking_id} status={self.status} total={self.total_marks}")
OFFLINE DOCKER TEST CASES:
- A second evaluation for the same booking raises IntegrityError.
- Two scores for the same (evaluation, rubric) raise IntegrityError.
- Negative total_marks or score raises IntegrityError; status "final" raises IntegrityError.
- Deleting an evaluation also deletes its scores (the single cascade); deleting a booking that has an evaluation raises IntegrityError.
"""
EOF

cat << 'EOF' > app/models/audit_log.py
"""
FILE PURPOSE: Table "audit_logs": append-only record of important actions (booking, cancel, reschedule, approvals, switches).
DEPENDS ON: app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class AuditLog(db.Model), __tablename__ = "audit_logs" (only created_at, no updated_at - rows are never edited). Columns: id PK; actor_id FK users.id null (null for system jobs); action TEXT not null (dotted names such as booking.create, booking.cancel, exam.booking_toggle); entity_type TEXT not null; entity_id INTEGER null; details TEXT null (JSON string); ip_address TEXT null; created_at DATETIME not null server_default current_timestamp.
2. Index ix_audit_logs_entity on (entity_type, entity_id).
3. Optional read-only helper details_dict() that json-loads details and returns {} on empty or invalid JSON (never raises).
4. No delete or update helpers; add a comment that the service layer (audit_service in P3) is the only writer.
DEBUGGING:
# print(f"[DEBUG] audit {self.action} {self.entity_type}#{self.entity_id} by={self.actor_id}")
OFFLINE DOCKER TEST CASES:
- A row with actor_id NULL is accepted (system job).
- A row without action or entity_type raises IntegrityError.
- details_dict() returns {} for None, for "not json", and the parsed dict for '{"reason": "x"}'.
"""
EOF

# =============================== TESTS ===============================

cat << 'EOF' > tests/conftest.py
"""
FILE PURPOSE: Shared pytest fixtures and tiny test-data factories for all later phases.
DEPENDS ON: app/__init__.py (create_app), app/models, app/extensions.
PROMPT FOR LLM IMPLEMENTATION:
1. Fixture app (function scope): build create_app("testing"), override SQLALCHEMY_DATABASE_URI to a file in pytest's tmp_path (sqlite:///<tmp>/test.db; NOT :memory:, because WAL and multiple connections need a file), push an app context, run db.create_all(), yield the app, then db.session.remove() and db.drop_all().
2. Fixtures client (app.test_client()) and runner (app.test_cli_runner()). Fixture session returns db.session.
3. Factory fixtures (plain functions returned by fixtures, each commits and returns the object, each accepting keyword overrides):
   - make_user(role="student", email=None, password="Passw0rd!", approval_status=None, is_active=True, full_name=None, must_change_password=False): auto-generates unique emails like student1@test.local; default approval_status is "approved" except role "examiner" which defaults to "pending"; creates the matching profile row.
   - make_admin(**kw) (forwards must_change_password and other overrides), make_examiner(approved=True), make_student(): thin wrappers.
   - make_course(code=None, created_by=None): creates an admin if none given.
   - make_examination(course=None, **overrides): valid windows built from a fixed BASE datetime (2030-01-01 00:00): slot_creation 01-01..01-10, booking 01-10..01-20, cancellation_deadline = booking_end, duration 30, max_marks 100.
   - make_rubric(examination, name, weightage, max_score), make_slot(examination, examiner, capacity=5, **overrides), make_booking(student, slot, status="booked") which sets booked_at and examination_id from the slot but does NOT touch booked_count (tests of the engine in P5/P6 use the service instead).
4. Provide login helper fixture login(client, email, password) that POSTs to /login (works from P2 onward; skip with pytest.skip if the route returns 404).
5. Keep fixtures free of app logic: no business rules, only object creation.
DEBUGGING:
# print(f"[DEBUG] test db at {tmp_path / 'test.db'}; tables={sorted(db.metadata.tables)}")
OFFLINE DOCKER TEST CASES:
- A test using the app fixture sees 12 empty tables.
- make_user called twice returns two different, unique emails.
- Data created in one test is not visible in the next test (isolation).
"""
EOF

cat << 'EOF' > tests/unit/test_models_users_profiles.py
"""
FILE PURPOSE: Constraint tests for users, examiner_profiles, student_profiles.
DEPENDS ON: tests/conftest.py, app/models/user.py, app/models/examiner_profile.py, app/models/student_profile.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Use the fixtures from conftest. For every IntegrityError case wrap the commit in pytest.raises(sqlalchemy.exc.IntegrityError) and call db.session.rollback() afterwards.
2. Tests to write (one function each, name describes the rule): test_user_role_check, test_user_approval_status_check, test_user_email_unique, test_user_email_case_duplicate_rejected, test_user_defaults (is_active True, approval approved, must_change_password False), test_password_hashing_roundtrip, test_password_hash_not_plaintext, test_examiner_profile_one_per_user, test_examiner_profile_status_check, test_student_roll_number_unique, test_student_roll_number_nullable_many, test_student_profile_one_per_user, test_delete_user_with_profile_restricted.
3. Add one test that User.__repr__ does not contain the password hash.
DEBUGGING:
# print(f"[DEBUG] constraint failure text: {exc_info.value.orig}")
OFFLINE DOCKER TEST CASES:
- All tests above pass offline inside docker compose --profile test run --rm test pytest tests/unit/test_models_users_profiles.py.
- Removing a CHECK from user.py makes the matching test fail (mutation sanity check, done manually once).
"""
EOF

cat << 'EOF' > tests/unit/test_models_courses_exams.py
"""
FILE PURPOSE: Constraint tests for courses, examinations, rubrics and examination_examiners.
DEPENDS ON: tests/conftest.py, app/models/course.py, examination.py, rubric.py, examination_examiner.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Same IntegrityError pattern as the other model tests.
2. Tests: test_course_code_unique, test_course_status_check, test_course_delete_with_exam_restricted, test_exam_type_check, test_exam_status_check, test_exam_duration_positive, test_exam_max_marks_positive, test_exam_creation_window_order, test_exam_booking_window_order, test_exam_windows_must_not_overlap, test_exam_windows_may_touch (slot_creation_end == booking_start is allowed), test_exam_cancellation_deadline_defaults_to_booking_end, test_exam_defaults_draft_and_switches_off, test_rubric_unique_name_per_exam, test_rubric_same_name_other_exam_ok, test_rubric_weightage_range, test_rubric_max_score_positive, test_examiner_assignment_unique, test_assignment_unknown_examiner_rejected, test_mapper_configuration_ok (configure_mappers raises nothing).
3. Use datetime objects from conftest BASE; never call datetime.now().
DEBUGGING:
# print(f"[DEBUG] exam windows: create {exam.slot_creation_start}-{exam.slot_creation_end}, book {exam.booking_start}-{exam.booking_end}")
OFFLINE DOCKER TEST CASES:
- 20 tests pass; the boundary test (windows may touch) proves the CHECK uses <= and not <.
"""
EOF

cat << 'EOF' > tests/unit/test_models_slots_bookings.py
"""
FILE PURPOSE: Tests for the capacity CHECK, the partial unique index and booking relationships (the data side of the flagship feature).
DEPENDS ON: tests/conftest.py, app/models/slot.py, app/models/booking.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_slot_capacity_positive, test_slot_booked_count_cannot_exceed_capacity, test_slot_booked_count_not_negative, test_slot_time_order, test_slot_status_check, test_slot_seats_left_property, test_booking_status_check, test_booking_requires_booked_at, test_active_booking_unique_per_student_exam (two 'booked' rows in different slots of the same examination -> IntegrityError), test_rebook_after_cancel_allowed, test_two_cancelled_allowed, test_booked_and_completed_conflict, test_other_students_not_blocked, test_booking_slot_relationship_loads, test_delete_slot_with_booking_restricted.
2. One test inspects the DDL (sqlite_master) and asserts the index name uq_bookings_active_student_exam exists and its SQL contains "WHERE" with the status list; this proves the partial index was really created.
3. One test creates a booking whose examination_id differs from slot.examination_id and documents (with a comment, no assertion on failure) that the DB allows it and that P5 services must prevent it.
DEBUGGING:
# print(f"[DEBUG] index sql: {row.sql}")
OFFLINE DOCKER TEST CASES:
- 15 tests pass; test_active_booking_unique_per_student_exam fails if the partial index is removed.
"""
EOF

cat << 'EOF' > tests/unit/test_models_evaluations_audit.py
"""
FILE PURPOSE: Tests for evaluations, evaluation_scores and audit_logs.
DEPENDS ON: tests/conftest.py, app/models/evaluation.py, app/models/audit_log.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_one_evaluation_per_booking, test_evaluation_status_check, test_evaluation_total_non_negative, test_score_unique_per_rubric, test_score_non_negative, test_scores_cascade_with_evaluation, test_delete_booking_with_evaluation_restricted, test_audit_actor_nullable, test_audit_requires_action_and_entity_type, test_audit_details_dict_variants, test_audit_entity_index_exists.
2. Build the object chain (admin, examiner, student, course, examination, rubric, slot, booking) with the conftest factories; keep each test under 25 lines.
DEBUGGING:
# print(f"[DEBUG] scores for evaluation {ev.id}: {[s.score for s in ev.scores]}")
OFFLINE DOCKER TEST CASES:
- 11 tests pass; deleting an Evaluation leaves zero rows in evaluation_scores for it.
"""
EOF

cat << 'EOF' > tests/integration/test_init_db_and_pragmas.py
"""
FILE PURPOSE: End-to-end checks of programmatic database creation, Admin seeding and SQLite pragmas (course rule: DB created by code; Admin pre-exists).
DEPENDS ON: app/cli.py, app/extensions.py, tests/conftest.py (uses its own empty temp DB, not the pre-created tables).
PROMPT FOR LLM IMPLEMENTATION:
1. Use app.test_cli_runner() and a temp DB path. Set ADMIN_EMAIL, ADMIN_FULL_NAME, ADMIN_INITIAL_PASSWORD in app.config for the test.
2. Tests: test_init_db_creates_exactly_12_tables (compare with EXPECTED_TIER1_TABLES, ignore sqlite_sequence), test_init_db_creates_one_admin (role admin, approval approved, is_active, must_change_password True, check_password works), test_init_db_is_idempotent (run twice: 1 user, same password_hash, second output says already exists), test_init_db_never_overwrites_changed_admin_password, test_init_db_requires_password_setting (exit code != 0, 0 users), test_init_db_output_hides_password, test_email_normalised_lowercase, test_existing_non_admin_with_same_email_aborts.
3. Pragma tests: test_foreign_keys_on (insert a booking with a missing slot_id -> IntegrityError), test_wal_mode_on_file_db, test_busy_timeout_5000.
4. Config tests: test_relative_sqlite_path_resolves_to_project_root (no instance/instance folder created), test_prod_config_requires_secret_key.
5. Logging test: test_request_id_header_present on GET "/".
6. Also assert that no table named email_logs, tests, payments or any Tier 3 name exists (tier discipline).
DEBUGGING:
# print(f"[DEBUG] cli output: {result.output!r}; exit={result.exit_code}")
OFFLINE DOCKER TEST CASES:
- All tests pass with the network disabled (docker compose --profile test run --rm test).
- After "docker compose up --build" and a first "init-db" inside the container, instance/emp.db exists on the host through the bind mount.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs instance logs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P1 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. For app/__init__.py give it docs/seed_updates/P1_update_app_init.md plus the CURRENT file (do not regenerate it from scratch)."
echo "2. Run 'docker compose --profile test run --rm test' (or 'make test-core') and then 'flask --app app init-db' to test offline."
echo "3. Run 'git add . && git commit -m \"wip: P1 database models\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p1-database-models && git commit -m \"Milestone-1 EMP-Database-Models\" && git tag p1-done && git push origin main --tags'."
echo "5. Patch TDR section 4.1: add users.must_change_password (BOOLEAN, not null, default 0)."
echo "6. Execute P2.sh"
echo "====================================================="
