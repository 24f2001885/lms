#!/usr/bin/env bash
# =====================================================================
# P2.sh - Milestone M2: Authentication & Role-Based Access (Tier 1, Primary)
# Course commit message : Milestone-2 EMP-Authentication-RBAC
# Branch                : phase/p2-authentication-rbac
# Depends on            : P1 (tag p1-done)
# Screens               : PUB-01 to PUB-07 (Design Plan section 5.1)
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files for the LLM implementation step.
# Existing files are NEVER overwritten; changes to app/__init__.py are
# described in docs/seed_updates/P2_update_app_init.md.
# =====================================================================
set -euo pipefail

PHASE="P2"
BRANCH="phase/p2-authentication-rbac"
PREV_TAG="p1-done"

# ---------------------------------------------------------------------
# Pre-flight checks (infrastructure only)
# ---------------------------------------------------------------------
[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P1 first."; exit 1; }
[ -f app/models/user.py ] || { echo "ERROR: app/models/user.py missing (P1 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P2 needs)
# ---------------------------------------------------------------------
mkdir -p app/security app/forms app/blueprints/auth app/blueprints/admin app/blueprints/examiner app/blueprints/student
mkdir -p app/templates/macros app/templates/errors app/templates/auth
mkdir -p app/static/css app/static/vendor/bootstrap/css app/static/vendor/bootstrap/js app/static/vendor/bootstrap-icons
mkdir -p tests/unit tests/integration docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPT ==========================

cat << 'EOF' > docs/seed_updates/P2_update_app_init.md
<!--
FILE PURPOSE: Update prompt for app/__init__.py (implemented in P0, extended in P1). Do not regenerate it from scratch.
HOW TO USE: give your LLM this prompt plus the CURRENT app/__init__.py and ask for the full updated file.
PROMPT FOR LLM IMPLEMENTATION:
1. Initialise CSRF globally: call csrf.init_app(app) (the csrf object already exists in app/extensions.py from P1). Do not edit extensions.py.
2. Register blueprints in this order: auth (no url prefix), admin (url_prefix /admin), examiner (url_prefix /examiner), student (url_prefix /student). Import them inside create_app to avoid circular imports.
3. Register the error handlers from app/errors.py (call register_error_handlers(app)).
4. Register a before_request hook from app/security/auth_helpers.py (load_current_user) so g.user is set on every request from session["user_id"]. It must run AFTER the request-id hook from P1 logging so log lines carry the user id.
5. Register a context processor exposing current_user (g.user or None), role_dashboard_url (callable) and csrf_token to all templates.
6. REMOVE the P0 placeholder route "/" from this file: the auth blueprint now owns "/" (redirect to the role dashboard when signed in, otherwise to /login).
7. Update tests/unit/test_smoke_app.py ONLY as needed: test_root_returns_placeholder_page must now expect a 302 redirect to /login for an anonymous user; the other two smoke tests stay unchanged.
8. Keep create_app free of database access at startup.
DEBUGGING:
# print(f"[DEBUG] blueprints registered: {list(app.blueprints)}; csrf enabled={app.config.get('WTF_CSRF_ENABLED', True)}")
OFFLINE DOCKER TEST CASES:
- list(app.blueprints) equals ["auth", "admin", "examiner", "student"].
- GET / (anonymous) returns 302 with Location ending in /login.
- With TestConfig the app still starts with WTF_CSRF_ENABLED False; with it set True a POST without a token returns 400/redirect handled by the CSRF handler.
-->
EOF

# ============================= SECURITY ==============================

cat << 'EOF' > app/security/__init__.py
"""
FILE PURPOSE: Package marker for authentication helpers and access-control decorators.
PROMPT FOR LLM IMPLEMENTATION:
1. Leave the file empty except for a one-line module docstring. Do NOT re-export helpers here (avoids circular imports with app/models).
DEBUGGING:
# print("[DEBUG] app.security imported")
OFFLINE DOCKER TEST CASES:
- "import app.security" succeeds with no side effects.
"""
EOF

cat << 'EOF' > app/security/auth_helpers.py
"""
FILE PURPOSE: Session-based authentication helpers for Tier 1 (Flask-Login replaces the session plumbing in P11 but keeps these function names).
DEPENDS ON: app/models/user.py, app/extensions.py, app/config.py (MIN_PASSWORD_LENGTH).
PROMPT FOR LLM IMPLEMENTATION:
1. load_current_user(): a before_request function. Read session.get("user_id"); if present load User by primary key and store it in g.user, otherwise g.user = None. If the id points to no row, clear the session. Do NOT clear the session for an inactive user (the inactive notice page must still be reachable); decorators handle that case.
2. login_user_session(user): call session.clear() FIRST (prevents session fixation), then set session["user_id"] = user.id, session.permanent = True, update user.last_login_at to the current UTC time (naive UTC), commit.
3. logout_user_session(): session.clear().
4. get_current_user() returns g.user or None. current_user_id() returns the integer id or None.
5. role_dashboard_url(user) returns the URL for the role: admin -> admin.dashboard, examiner -> examiner.dashboard, student -> student.dashboard; returns the login URL for None. Use url_for with endpoint names, never hard-coded paths.
6. post_login_redirect_url(user) decides where a user lands right after login, in this priority: must_change_password -> auth.change_password; is_active False -> auth.account_inactive; examiner with approval_status "pending" or "rejected" -> auth.pending_approval; otherwise role_dashboard_url(user).
7. validate_password_strength(raw) -> list[str] of human-readable problems: shorter than MIN_PASSWORD_LENGTH (8), no letter, no digit. Return an empty list when acceptable. (Do not impose symbol rules.)
8. is_safe_redirect_target(target) -> bool: True only for relative paths that start with a single "/" and contain no scheme, no "//" prefix, no backslash and no newline characters. Used for an optional "next" parameter; the login view may ignore "next" entirely.
9. verify_credentials(email, password) -> User | None: normalise the email (strip, lowercase), look the user up, and ALWAYS run a password-hash check (against a dummy hash when the user does not exist) so response time does not reveal which emails exist. Return the user only when the hash matches. Do not reveal whether the email or the password was wrong.
10. Never log passwords or hashes. Log INFO "login success user_id=..." and WARNING "login failed" (email only as a short hash or omitted).
DEBUGGING:
# print(f"[DEBUG] login_user_session user_id={user.id} role={user.role} session_keys={list(session.keys())}")
OFFLINE DOCKER TEST CASES:
- After login_user_session the session contains user_id and nothing from the pre-login session (fixation test: set session["x"]=1 before login, assert it is gone).
- validate_password_strength("abc") returns at least 2 problems; "Passw0rdOK" returns [].
- is_safe_redirect_target("/student/dashboard") True; "//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)" all False.
- verify_credentials returns None for an unknown email and for a wrong password, and returns the user for correct credentials with mixed-case email input.
- post_login_redirect_url returns the change-password URL for the seeded admin (must_change_password True).
"""
EOF

cat << 'EOF' > app/security/decorators.py
"""
FILE PURPOSE: Route decorators that enforce authentication and role-based access on EVERY request (PDR 5.2, TDR section 6, risks R-4 and R-5).
DEPENDS ON: app/security/auth_helpers.py, app/errors.py (PermissionDenied).
PROMPT FOR LLM IMPLEMENTATION:
1. login_required: if g.user is None, flash("Please log in to continue.", "warning") and redirect to auth.login. Use functools.wraps.
2. role_required(*roles): a decorator factory that first applies the login_required behaviour, then checks IN THIS ORDER: (a) user.is_active False -> redirect to auth.account_inactive; (b) user.must_change_password True -> redirect to auth.change_password; (c) user.role not in roles -> abort(403) (this is what makes "wrong-role URLs return 403"); (d) for role examiner: approval_status "pending" or "rejected" -> redirect to auth.pending_approval. Only then call the view.
3. approved_examiner_required: shortcut equal to role_required("examiner") plus an explicit re-check of approval_status == "approved" and is_active on every request (not just at login). Use it on all examiner routes later.
4. admin_required, student_required: one-line aliases built on role_required for readability.
5. Add a helper owned_or_404(query, **filters) is NOT part of this phase; ownership checks are written inside each query in P4/P5 (document this in a comment).
6. Every denial writes a WARNING log line "access denied user_id=... role=... path=..." (no personal data beyond ids).
7. The decorators must never import blueprint modules (avoid circular imports) and must not touch the database themselves; they read g.user only.
DEBUGGING:
# print(f"[DEBUG] guard path={request.path} user={getattr(g.user, 'id', None)} role={getattr(g.user, 'role', None)} roles_allowed={roles}")
OFFLINE DOCKER TEST CASES:
- Anonymous GET /admin/dashboard -> 302 to /login.
- Student GET /admin/dashboard -> 403; student GET /examiner/dashboard -> 403.
- Examiner (approved) GET /student/dashboard -> 403.
- Pending examiner GET /examiner/dashboard -> 302 to /pending-approval; after setting approval_status "approved" in the database, the very next request succeeds (flag checked per request).
- Approved examiner whose is_active is set False -> next request redirects to /account-inactive.
- Admin with must_change_password True is redirected to /change-password from /admin/dashboard.
"""
EOF

# ============================== ERRORS ===============================

cat << 'EOF' > app/errors.py
"""
FILE PURPOSE: Domain exception classes with stable error codes, plus HTML error handlers for 403, 404, 500 and CSRF failures (screen PUB-07).
DEPENDS ON: app/templates/errors/*.html, flask.
PROMPT FOR LLM IMPLEMENTATION:
1. Define a base class AppError(Exception) with attributes code (str), message (str), http_status (int, default 400). Subclasses: BookingError, WindowError, PermissionDenied (http_status 403), plus AttemptError and PaymentError are NOT created now (Tier 3). Each subclass accepts code and message in its constructor and keeps the code stable for later API use.
2. Define the Tier 1 error code constants as module-level strings (TDR section 12): BOOKING_CLOSED, SLOT_FULL, DUPLICATE_BOOKING, SLOT_NOT_AVAILABLE, CANCEL_DEADLINE_PASSED, NOT_APPROVED. Do NOT define revisit_not_allowed, answer_locked, attempt_*, payment_required, invalid_signature or hold_expired (Tier 3).
3. register_error_handlers(app): handlers for 403, 404, 500 render errors/403.html, errors/404.html, errors/500.html with the correct status code. The 500 page shows only a reference id (g.request_id) and a friendly sentence, never a stack trace or exception text. Log the 500 with logger.exception including request_id.
4. Handler for AppError: flash(error.message, "danger") and redirect back to request.referrer when it is a same-host URL, otherwise to the role dashboard (or /login when anonymous); keep the HTTP status semantic by using 302. (JSON error shape arrives in P7 for /api/ paths; leave a comment where that branch will go.)
5. Handler for flask_wtf.csrf.CSRFError: flash("Your form expired. Please try again.", "warning") and redirect to a safe same-host referrer or to /login; log WARNING without the token value.
6. Handlers must be safe for anonymous users (no attribute errors when g.user is None) and must work even if the database is unavailable (do not query inside the 500 handler).
DEBUGGING:
# print(f"[DEBUG] error handler status={status} path={request.path} request_id={getattr(g, 'request_id', '-')}")
OFFLINE DOCKER TEST CASES:
- GET /no-such-page returns 404 with the custom page (contains "Page not found") and still renders the base layout.
- A student requesting /admin/dashboard gets the custom 403 page (contains "permission").
- A route that raises RuntimeError returns 500 whose body contains the request id but NOT the word "Traceback" or the exception message.
- Raising BookingError("slot_full", "This slot is full.") inside a test route flashes that message and redirects.
- Anonymous 404 and 403 pages render without a logout button.
"""
EOF

# ============================== FORMS ================================

cat << 'EOF' > app/forms/__init__.py
"""
FILE PURPOSE: Package marker for WTForms classes.
PROMPT FOR LLM IMPLEMENTATION:
1. Keep empty apart from a one-line docstring. Forms are imported from their own modules (app.forms.auth, app.forms.profile).
DEBUGGING:
# print("[DEBUG] app.forms imported")
OFFLINE DOCKER TEST CASES:
- "import app.forms" succeeds.
"""
EOF

cat << 'EOF' > app/forms/auth.py
"""
FILE PURPOSE: WTForms for login, registration and change-password (server-side validation; no JavaScript, per risk R-8).
DEPENDS ON: flask_wtf.FlaskForm, wtforms, app/security/auth_helpers.py (validate_password_strength), app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. LoginForm: email (StringField, DataRequired, Email, filters strip+lowercase), password (PasswordField, DataRequired), submit. Do not validate password strength at login.
2. RegisterForm: role (RadioField, choices ONLY ("student","Student") and ("examiner","Examiner"), DataRequired; "admin" must be impossible - an extra validate_role method rejects any other value even if the POST is tampered), full_name (DataRequired, Length 2-120, strip), email (DataRequired, Email, Length max 254, lowercased), password (DataRequired), confirm_password (DataRequired, EqualTo password with message "Passwords do not match"), department (Optional, Length max 120, label suffix "(examiners)"), contact_phone (Optional, Length max 20, digits plus + - space only, label suffix "(examiners)"). The extra fields are always rendered; they are stored only when role is examiner.
3. RegisterForm.validate_email: reject when a user with that email already exists (case-insensitive) with the message "An account with this email already exists." ; validate_password uses validate_password_strength and raises ValidationError with the first problem.
4. ChangePasswordForm: current_password (DataRequired), new_password (DataRequired, strength check), confirm_new_password (EqualTo new_password). Extra validation in the form: new_password must differ from current_password. The current-password check against the stored hash is done in the view (needs the logged-in user) and documented here in a comment.
5. All forms inherit FlaskForm so CSRF tokens are included automatically; field labels are plain English and match the Design Plan (section 4.1): "Full name", "Email", "Password", "Confirm password".
6. Each field has an explicit id and the form never echoes the password back into the HTML.
DEBUGGING:
# print(f"[DEBUG] form errors: {form.errors}")
OFFLINE DOCKER TEST CASES:
- RegisterForm with role "admin" is invalid (and no user is created by the view).
- Mismatched confirm_password gives the exact message "Passwords do not match".
- Duplicate email differing only by case is rejected.
- A 7-character password and an all-letters password are rejected; "Passw0rdOK" is accepted.
- ChangePasswordForm rejects new == current.
"""
EOF

cat << 'EOF' > app/forms/profile.py
"""
FILE PURPOSE: WTForms for editing the signed-in user's own profile (screen PUB-06, route /profile).
DEPENDS ON: flask_wtf, wtforms, app/models (User, ExaminerProfile, StudentProfile).
PROMPT FOR LLM IMPLEMENTATION:
1. Build ONE form class ProfileForm with these fields: full_name (DataRequired, Length 2-120), contact_phone (Optional, Length max 20, digits plus + - space), department (Optional, Length max 120), designation (Optional, Length max 120), roll_number (Optional, Length max 30), program (Optional, Length max 120).
2. Which fields are shown/used depends on the role, decided in the view/template: admin uses full_name only; examiner uses full_name, contact_phone, department, designation; student uses full_name, contact_phone, roll_number, program. Provide a classmethod or helper fields_for_role(role) returning the list of field names so the view and the template share the same rule.
3. roll_number uniqueness: validate_roll_number rejects a roll number already used by ANOTHER student (compare profile ids; the user's own current value is allowed). Normalise to uppercase and strip.
4. Email is NOT editable here (it is the login identity); role and approval status are never editable through this form (mass-assignment protection: the view copies only whitelisted fields).
DEBUGGING:
# print(f"[DEBUG] profile form role_fields={fields_for_role(role)} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- fields_for_role("admin") == ["full_name"]; examiner and student lists match item 2.
- A student cannot take another student's roll_number but can resubmit their own.
- A forged POST containing role=admin or approval_status=approved does not change those columns.
"""
EOF

# ============================ BLUEPRINTS =============================

cat << 'EOF' > app/blueprints/__init__.py
"""
FILE PURPOSE: Package marker for blueprints.
PROMPT FOR LLM IMPLEMENTATION:
1. Keep empty apart from a one-line docstring.
DEBUGGING:
# print("[DEBUG] app.blueprints imported")
OFFLINE DOCKER TEST CASES:
- "import app.blueprints" succeeds.
"""
EOF

cat << 'EOF' > app/blueprints/auth/__init__.py
"""
FILE PURPOSE: Defines the "auth" blueprint (no url_prefix) and imports its route modules.
DEPENDS ON: app/blueprints/auth/routes.py, app/blueprints/auth/profile.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create auth_bp = Blueprint("auth", __name__, template_folder omitted because templates live in app/templates/auth).
2. At the bottom import the route modules (routes, profile) so their decorators register on auth_bp; add "# noqa: E402,F401" comments for ruff.
3. No logic besides the blueprint object and the imports.
DEBUGGING:
# print(f"[DEBUG] auth_bp endpoints: {[r.endpoint for r in current_app.url_map.iter_rules() if r.endpoint.startswith('auth.')]}")
OFFLINE DOCKER TEST CASES:
- app.url_map contains the endpoints auth.index, auth.login, auth.register, auth.logout, auth.change_password, auth.pending_approval, auth.account_inactive, auth.profile.
"""
EOF

cat << 'EOF' > app/blueprints/auth/routes.py
"""
FILE PURPOSE: Public and shared account routes: root redirect, register, login, logout, change password, pending-approval and inactive notices (screens PUB-01 to PUB-05).
DEPENDS ON: app/blueprints/auth/__init__.py (auth_bp), app/forms/auth.py, app/security/*, app/models, app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET "/" (endpoint index): anonymous -> redirect to auth.login; signed in -> redirect to post_login_redirect_url(user).
2. GET/POST "/register" (endpoint register): signed-in users are redirected to their dashboard. On valid POST create the User with the normalised email, hashed password and role from the form. Student: approval_status "approved". Examiner: approval_status "pending". In the SAME transaction create the matching profile row (StudentProfile, or ExaminerProfile with department and contact_phone). Hard guard in the view: if form.role.data not in ("student","examiner") abort(400) - the Admin can never be created through the UI. On success flash "Account created. Please log in." (examiner: "Account created. An administrator must approve your account before you can sign in to the dashboard.") and redirect to auth.login. Catch IntegrityError on the unique email (race) and show the duplicate-email form error.
3. GET/POST "/login" (endpoint login): signed-in users are redirected onward. On valid POST call verify_credentials; on failure flash "Invalid email or password." with category danger and re-render with status 200 (same message for unknown email and wrong password). On success call login_user_session and redirect to post_login_redirect_url(user); honour an optional ?next= only if is_safe_redirect_target() and the user is allowed to land there (when must_change_password is true ignore next).
4. POST "/logout" (endpoint logout): login_required, CSRF-protected, calls logout_user_session, flashes "You have been logged out." and redirects to auth.login. POST only, as in TDR 5.1 (the PDR appendix lists GET; the TDR wins because logout must not be triggerable by a link or image tag). Do not add a GET route.
5. GET/POST "/change-password" (endpoint change_password): login_required only (must be reachable while must_change_password is true, and by inactive users NOT). Verify current_password with check_password, set the new hash, set must_change_password False, commit, flash "Password updated.", then redirect to post_login_redirect_url. Wrong current password -> form error, no change.
6. GET "/pending-approval" (endpoint pending_approval): login_required; if user is not an examiner, or the examiner is already approved and active, redirect to their dashboard. Render auth/pending_approval.html with variant text for approval_status "rejected".
7. GET "/account-inactive" (endpoint account_inactive): login_required; if user.is_active is True redirect to the dashboard; otherwise render auth/inactive.html. Show a Logout button only.
8. All redirects use url_for; no hard-coded paths. Responses for authentication failures never reveal which part failed.
9. Write INFO audit-style log lines for register, login success and logout (ids only). The audit_logs table is NOT used in this phase.
DEBUGGING:
# print(f"[DEBUG] login attempt email_present={bool(form.email.data)} valid={form.validate_on_submit()} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- Student registers -> user row has role student, approval approved, a student_profiles row exists, password_hash is not the raw password; redirect to /login with the success flash.
- Examiner registers -> approval pending and an examiner_profiles row with department saved.
- POST /register with role=admin returns 400 (or form error) and creates no user.
- Login with a wrong password and with an unknown email returns identical 200 pages containing "Invalid email or password."
- Student login redirects to /student/dashboard; examiner (pending) to /pending-approval; seeded admin to /change-password first, then to /admin/dashboard after changing it.
- GET /logout returns 405; POST /logout (with CSRF disabled in tests) clears the session and redirects to /login.
- Login with ?next=https://evil.example ignores the next value.
"""
EOF

cat << 'EOF' > app/blueprints/auth/profile.py
"""
FILE PURPOSE: Shared profile view/edit for any signed-in role (screen PUB-06, route /profile).
DEPENDS ON: app/blueprints/auth/__init__.py (auth_bp), app/forms/profile.py, app/models.
PROMPT FOR LLM IMPLEMENTATION:
1. GET/POST "/profile" (endpoint profile): role-aware via the decorator login_required plus the inactive and must-change-password checks from role_required(("admin","examiner","student")) - reuse role_required with all three roles.
2. GET: pre-fill ProfileForm from the user and the matching profile row (examiner_profiles or student_profiles; admin has none). Render auth/profile.html with the list of visible fields from fields_for_role.
3. POST: validate, then copy ONLY the whitelisted fields for that role onto the user/profile rows (never role, approval_status, is_active, email, password). If a student has no profile row (legacy data), create it. Commit once, flash "Profile updated." and redirect back to auth.profile (post/redirect/get).
4. Show read-only account facts on the page: email, role, approval status (text), member since date.
DEBUGGING:
# print(f"[DEBUG] profile update user={user.id} fields={sorted(changed)}")
OFFLINE DOCKER TEST CASES:
- Student updates phone, program and roll_number -> persisted in student_profiles; full_name persisted on users.
- Examiner updates department and designation -> persisted in examiner_profiles.
- Admin sees only the full name field.
- POST containing role=admin leaves the user's role unchanged.
- Anonymous GET /profile redirects to /login.
"""
EOF

cat << 'EOF' > app/blueprints/admin/__init__.py
"""
FILE PURPOSE: STUB of the "admin" blueprint so role redirects and 403 tests work in P2. P3 replaces this file's dashboard with the real Admin panel (ADM-01 onward).
DEPENDS ON: app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create admin_bp = Blueprint("admin", __name__, url_prefix="/admin") in this file (the factory imports admin_bp from here; P3 keeps this name).
2. One stub route GET "/dashboard" (endpoint dashboard) protected by admin_required, rendering auth/role_landing_stub.html with role="Admin" and phase="P3".
3. Add the comment "STUB: replaced in P3 by the real dashboard, CRUD and oversight views" at the top. No other routes, no queries.
DEBUGGING:
# print(f"[DEBUG] admin stub dashboard served to user_id={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Admin (password already changed) gets 200 from /admin/dashboard; student and examiner get 403; anonymous gets 302 to /login.
"""
EOF

cat << 'EOF' > app/blueprints/examiner/__init__.py
"""
FILE PURPOSE: STUB of the "examiner" blueprint so the pending-approval gate and 403 tests work in P2. P4 replaces the dashboard with EXM-01 onward.
DEPENDS ON: app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner").
2. One stub route GET "/dashboard" (endpoint dashboard) protected by approved_examiner_required, rendering auth/role_landing_stub.html with role="Examiner" and phase="P4".
3. Top comment "STUB: replaced in P4". No other routes, no queries.
DEBUGGING:
# print(f"[DEBUG] examiner stub dashboard served to user_id={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Approved examiner gets 200; pending examiner is redirected to /pending-approval; rejected examiner too; student and admin get 403.
- Deactivated (is_active False) examiner is redirected to /account-inactive on the next request.
"""
EOF

cat << 'EOF' > app/blueprints/student/__init__.py
"""
FILE PURPOSE: STUB of the "student" blueprint so role redirects work in P2. P5 replaces the dashboard with STU-01 onward.
DEPENDS ON: app/security/decorators.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create student_bp = Blueprint("student", __name__, url_prefix="/student").
2. One stub route GET "/dashboard" (endpoint dashboard) protected by student_required, rendering auth/role_landing_stub.html with role="Student" and phase="P5".
3. Top comment "STUB: replaced in P5". No other routes, no queries.
DEBUGGING:
# print(f"[DEBUG] student stub dashboard served to user_id={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Student gets 200; examiner and admin get 403; anonymous gets 302 to /login.
"""
EOF

# ============================= TEMPLATES =============================

cat << 'EOF' > app/templates/base.html
<!--
FILE PURPOSE: Master layout extended by every page (Design Plan sections 1, 2, 7, 8). P3/P4/P5 add role-specific bases that extend this file.
DEPENDS ON: app/static/css/app.css, vendored Bootstrap files in app/static/vendor/bootstrap/.
PROMPT FOR LLM IMPLEMENTATION:
1. HTML5 document, lang="en", viewport meta, a meta name="csrf-token" tag with the token (used later by fetch calls in Tier 2/3), title block "{% block title %}EMP{% endblock %} - Examination Management Portal".
2. Load Bootstrap 5 CSS and JS bundle ONLY from url_for static paths vendor/bootstrap/css/bootstrap.min.css and vendor/bootstrap/js/bootstrap.bundle.min.js (no CDN, no web fonts), then css/app.css. System font stack only.
3. Skip-to-content link as the first focusable element, a header with a navbar (brand "EMP"), a main element with id="main-content" containing flash messages then the content block, and a simple footer.
4. Navbar is role-aware using current_user from the context processor: anonymous -> Login and Register links; signed in -> Dashboard (role_dashboard_url), Profile, and a Logout FORM (POST to auth.logout with the csrf hidden field, styled as a link button). Show the user's full name and a text role label. Hide the dashboard link for inactive or pending users (they only see Logout).
5. Flash messages: loop get_flashed_messages(with_categories=true) inside a container with aria-live="polite"; map categories success/info/warning/danger to Bootstrap alert classes, each dismissible with role="alert".
6. Blocks: title, content, scripts (empty). One h1 per page is provided by child templates. Use semantic landmarks header, nav, main, footer.
7. Content max-width 1200px via a container; the page background and palette come from app.css.
DEBUGGING:
<!-- DEBUG: render with current_user.role and request.endpoint printed in an HTML comment when app.debug is true -->
OFFLINE DOCKER TEST CASES:
- The rendered page has no reference to any http(s):// asset URL (offline-safe check with a regex on the HTML).
- Anonymous page shows Login and Register; a signed-in student page shows Logout and no Register.
- The Logout control is a form with method post and a csrf_token input.
- Flash message markup contains role="alert" and sits inside an aria-live="polite" region.
-->
EOF

cat << 'EOF' > app/templates/macros/forms.html
<!--
FILE PURPOSE: Reusable Jinja macros for accessible Bootstrap form fields (Design Plan section 7 and 8).
PROMPT FOR LLM IMPLEMENTATION:
1. Macro render_field(field, help_text=None): outputs a div.mb-3 containing a visible label (label for = field id), the field with class form-control (or form-select for SelectField, form-check-input for checkbox/radio), and error messages in div.invalid-feedback. When field.errors is not empty add class is-invalid and set aria-invalid="true" plus aria-describedby pointing to the error/help element ids.
2. Macro render_radio_group(field) for the role RadioField: fieldset with legend, one form-check per choice.
3. Macro render_submit(label, css_class="btn btn-primary"): a button of type submit.
4. Macro csrf_field(form): outputs form.hidden_tag() so every form includes the token.
5. Macros never print password values; password inputs are rendered with value="".
DEBUGGING:
<!-- DEBUG: field {{ field.name }} errors={{ field.errors }} -->
OFFLINE DOCKER TEST CASES:
- Rendering a field with an error output contains is-invalid, invalid-feedback and aria-describedby.
- Every rendered input has a matching label (label for equals input id).
- A password field renders with an empty value attribute even after a failed POST.
-->
EOF

cat << 'EOF' > app/templates/errors/403.html
<!--
FILE PURPOSE: Custom "Forbidden" page (PUB-07).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Access denied"; one sentence "You do not have permission to open this page."; a primary button back to the user's dashboard (role_dashboard_url) when signed in, otherwise to the login page.
2. No technical details, no role names of other users.
DEBUGGING:
<!-- DEBUG: path={{ request.path }} -->
OFFLINE DOCKER TEST CASES:
- Response status is 403 and body contains "permission".
-->
EOF

cat << 'EOF' > app/templates/errors/404.html
<!--
FILE PURPOSE: Custom "Page not found" page (PUB-07). Also used when ownership checks hide another user's record.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Page not found"; sentence "We could not find what you were looking for."; button to the dashboard or login page as in 403.html.
DEBUGGING:
<!-- DEBUG: path={{ request.path }} -->
OFFLINE DOCKER TEST CASES:
- Response status is 404 and body contains "Page not found".
-->
EOF

cat << 'EOF' > app/templates/errors/500.html
<!--
FILE PURPOSE: Custom "Server error" page (PUB-07) showing only a reference id.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Something went wrong"; sentence "Please try again. If the problem continues, quote this reference to the administrator."; show request_id in a monospace code element.
2. Must render even if the database is down: do not use current_user data that requires a query; use only variables passed by the handler.
DEBUGGING:
<!-- DEBUG: request_id={{ request_id }} -->
OFFLINE DOCKER TEST CASES:
- Response status is 500, body contains the request id, and contains neither "Traceback" nor the exception text.
-->
EOF

cat << 'EOF' > app/templates/auth/login.html
<!--
FILE PURPOSE: PUB-01 Login screen (centered card, single column).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html. Centered Bootstrap card (max width about 420px) with h1 "Log in", form method post, csrf via macros, fields Email (type email, autocomplete username, autofocus) and Password (type password, autocomplete current-password), submit "Log in".
2. Link below: "No account? Register" to auth.register. No "forgot password" link: the reset flow is admin-assisted (Design Plan 4.1); show a small muted text "Forgot your password? Contact your administrator."
3. On error show the generic flash message from the view; do not add field-specific hints that reveal whether the email exists.
DEBUGGING:
<!-- DEBUG: form errors {{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- GET /login returns 200 with an h1 "Log in", an email input and a password input, each with a label.
- Page contains the text "Contact your administrator" and no link to a reset URL.
-->
EOF

cat << 'EOF' > app/templates/auth/register.html
<!--
FILE PURPOSE: PUB-02 Registration screen for Students and Examiners.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; centered card; h1 "Create an account"; form method post with csrf.
2. Fields in order: role radio group (Student, Examiner), Full name, Email, Password, Confirm password, then a fieldset "Examiner details (optional)" containing Department and Phone. Hint under the fieldset: "Only needed if you register as an examiner. Examiner accounts must be approved by an administrator."
3. Password hint text: "At least 8 characters with a letter and a number."
4. Submit "Register"; link "Already registered? Log in". There must be NO option or hidden field for the Admin role.
DEBUGGING:
<!-- DEBUG: role selected {{ form.role.data }} errors {{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- GET /register shows exactly two role choices and the page source contains no value="admin".
- Submitting mismatched passwords re-renders the page with "Passwords do not match" next to the field.
-->
EOF

cat << 'EOF' > app/templates/auth/pending_approval.html
<!--
FILE PURPOSE: PUB-03 Notice shown to examiners whose account is not yet approved (or was rejected).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Approval pending". Explain: "Your examiner account is waiting for administrator approval. You will be able to use the dashboard after it is approved." Show the account email.
2. When current_user.approval_status is "rejected" show instead: h1 "Account not approved" and "Your examiner registration was not approved. Please contact the administrator."
3. Provide a Logout form button and a "Check again" link to auth.pending_approval (it redirects to the dashboard once approved). No dashboard links.
DEBUGGING:
<!-- DEBUG: approval_status={{ current_user.approval_status }} -->
OFFLINE DOCKER TEST CASES:
- Pending examiner sees "Approval pending"; after approval in the database, "Check again" redirects to /examiner/dashboard.
- Rejected examiner sees "Account not approved".
-->
EOF

cat << 'EOF' > app/templates/auth/inactive.html
<!--
FILE PURPOSE: PUB-04 Notice shown to deactivated accounts.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Account inactive"; text "Your account has been deactivated. Please contact the administrator."; Logout form button only (no dashboard link, no profile link).
DEBUGGING:
<!-- DEBUG: is_active={{ current_user.is_active }} -->
OFFLINE DOCKER TEST CASES:
- A deactivated user is redirected here from any protected URL and sees the message and a logout button only.
-->
EOF

cat << 'EOF' > app/templates/auth/change_password.html
<!--
FILE PURPOSE: PUB-05 Change-password screen, used on first login of the seeded Admin and after an Admin sets a temporary password.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; card; h1 "Change your password"; when current_user.must_change_password is true show an info alert "You must choose a new password before continuing."
2. Form with csrf: Current password (autocomplete current-password), New password (autocomplete new-password), Confirm new password; hint "At least 8 characters with a letter and a number."; submit "Update password".
3. Show a Cancel link to the dashboard only when must_change_password is false.
DEBUGGING:
<!-- DEBUG: must_change={{ current_user.must_change_password }} errors={{ form.errors }} -->
OFFLINE DOCKER TEST CASES:
- Seeded admin sees the info alert and no Cancel link.
- Wrong current password re-renders with an error and leaves must_change_password True.
- Successful change redirects to /admin/dashboard.
-->
EOF

cat << 'EOF' > app/templates/auth/profile.html
<!--
FILE PURPOSE: PUB-06 Profile view and edit for any signed-in role.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Your profile"; a read-only summary list (dl) with Email, Role, Account status (text), Member since.
2. Edit form with csrf rendering only the fields in the visible_fields list passed by the view (admin: full name; examiner: full name, phone, department, designation; student: full name, phone, roll number, program).
3. Submit "Save changes"; link "Change password" to auth.change_password.
DEBUGGING:
<!-- DEBUG: visible_fields={{ visible_fields }} -->
OFFLINE DOCKER TEST CASES:
- Student page shows roll number and program inputs and no department input; examiner page the reverse.
- Email appears as plain text, never as an input.
-->
EOF

cat << 'EOF' > app/templates/auth/role_landing_stub.html
<!--
FILE PURPOSE: TEMPORARY landing page used by the P2 stub dashboards. Deleted when P3/P4/P5 deliver the real dashboards.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "{{ role }} dashboard"; paragraph "Signed in as {{ current_user.full_name }}. The full {{ role|lower }} dashboard arrives in milestone {{ phase }}."
2. Nothing else: no data from the database.
DEBUGGING:
<!-- DEBUG: stub for role={{ role }} phase={{ phase }} -->
OFFLINE DOCKER TEST CASES:
- Each stub dashboard returns 200 for its own role and contains the role name in the h1.
-->
EOF

# ============================== STATIC ===============================

cat << 'EOF' > app/static/css/app.css
/*
FILE PURPOSE: Brand overrides for Bootstrap 5 using CSS variables (Design Plan section 7). No other CSS framework is allowed.
PROMPT FOR LLM IMPLEMENTATION:
1. On :root set --bs-primary and --bs-primary-rgb to #1F4E79; link colour #1F4E79 with hover #173B5C; body background #F5F7FA; body text #212529; success #198754, warning #FFC107, danger #DC3545, info #0DCAF0, secondary #6C757D (use the matching --bs-*-rgb variables where Bootstrap needs them).
2. Override .btn-primary so background, border and hover/active states use the primary and primary-hover colours; keep a visible 3px focus ring (outline) on all interactive elements for keyboard users.
3. Define the custom badge class .badge-full (background #FD7E14, dark text for contrast) used later for full slots. Do NOT define .badge-refunded (Tier 3).
4. Typography: system font stack system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; monospace stack ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; base 16px, table text 0.9rem.
5. Style the skip-to-content link so it is visually hidden until focused, then appears at the top-left.
6. Provide small utility classes: .auth-card (max-width 420px, margin auto), .page-container (max-width 1200px).
7. Keep the file under 120 lines; no @import of remote resources, no web fonts.
DEBUGGING:
Add temporarily: body { outline: 2px solid magenta; } to check the file is loaded, then remove.
OFFLINE DOCKER TEST CASES:
- The file contains no "http://" or "https://" strings.
- Text/background colour pairs used by .btn-primary and .badge-full meet 4.5:1 contrast (manual check with a contrast tool).
*/
EOF

cat << 'EOF' > app/static/vendor/README.md
<!--
FILE PURPOSE: Instructions for vendoring Bootstrap offline (the demo must work without internet; Design Plan principle 6). The binary files themselves are downloaded manually once, they are not generated by seed scripts.
PROMPT FOR LLM IMPLEMENTATION:
1. List the exact files that must exist after vendoring: bootstrap/css/bootstrap.min.css, bootstrap/js/bootstrap.bundle.min.js, and the bootstrap-icons SVG sprite as bootstrap-icons/bootstrap-icons.svg.
2. Tell the team to download Bootstrap 5.3.x compiled CSS and JS from the official Bootstrap download page and Bootstrap Icons from its official release, copy them to those paths while online, and record the exact versions in this file.
3. Add a licence note: Bootstrap and Bootstrap Icons are MIT licensed; keep their licence headers inside the files.
4. Add a verification command: python -c "import pathlib; print([p.exists() for p in map(pathlib.Path, [...three paths...])])" expecting [True, True, True].
DEBUGGING:
(none: documentation file)
OFFLINE DOCKER TEST CASES:
- With the network disabled, GET /login still renders styled because /static/vendor/bootstrap/css/bootstrap.min.css returns 200.
-->
EOF

# ============================== TESTS ================================

cat << 'EOF' > tests/unit/test_auth_helpers.py
"""
FILE PURPOSE: Unit tests for pure helper functions in app/security/auth_helpers.py.
DEPENDS ON: app/security/auth_helpers.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_password_strength_rules (too short, no digit, no letter, valid), test_safe_redirect_accepts_relative_paths, test_safe_redirect_rejects_external_and_tricky (//evil.com, https://x, /\\x, javascript:, newline injection), test_verify_credentials_success_mixed_case_email, test_verify_credentials_wrong_password_returns_none, test_verify_credentials_unknown_email_returns_none, test_verify_credentials_runs_hash_for_unknown_email (monkeypatch check_password_hash and assert it was called once even for an unknown email), test_post_login_redirect_priority (must_change_password beats inactive beats pending beats role dashboard; use test_request_context for url_for).
2. Use the app fixture for application context; no HTTP calls in this file.
DEBUGGING:
# print(f"[DEBUG] redirect target for {user.role}: {post_login_redirect_url(user)}")
OFFLINE DOCKER TEST CASES:
- 8 tests pass offline; test_verify_credentials_runs_hash_for_unknown_email fails if the dummy-hash step is removed.
"""
EOF

cat << 'EOF' > tests/integration/test_auth_register_login.py
"""
FILE PURPOSE: Integration tests for registration, login, logout, change password and the pending/inactive notices (milestone M2 acceptance).
DEPENDS ON: tests/conftest.py, app/blueprints/auth/routes.py, app/forms/auth.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Register tests: test_student_register_success, test_examiner_register_pending_with_profile, test_register_admin_role_rejected_no_user_created, test_register_duplicate_email_case_insensitive, test_register_password_mismatch, test_register_weak_password, test_register_stores_hash_not_plaintext, test_signed_in_user_redirected_from_register.
2. Login tests: test_login_student_redirects_to_student_dashboard, test_login_wrong_password_generic_message, test_login_unknown_email_same_response_as_wrong_password (compare normalised bodies), test_login_pending_examiner_goes_to_pending_page, test_login_rejected_examiner_sees_not_approved, test_login_inactive_user_goes_to_inactive_page, test_login_updates_last_login_at, test_login_next_param_external_ignored, test_session_fixation_old_session_value_removed.
3. Admin flow: test_seeded_admin_must_change_password_then_dashboard (run init-db helpers or make_admin(must_change_password=True), login, expect redirect to /change-password, change it, expect /admin/dashboard), test_change_password_wrong_current_rejected, test_change_password_same_as_old_rejected, test_change_password_clears_flag.
4. Logout tests: test_logout_requires_post (GET returns 405), test_logout_clears_session_and_redirects, test_protected_page_after_logout_redirects_to_login.
5. Notice pages: test_pending_page_redirects_non_examiners, test_pending_examiner_approved_in_db_gets_dashboard_next_request, test_inactive_page_redirects_active_users.
6. Use client.post with data dicts and follow_redirects=False so redirect targets can be asserted exactly.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')} flashes={list(get_flashed_messages(with_categories=True))}")
OFFLINE DOCKER TEST CASES:
- All 26 tests pass with no network.
- Running the file twice in a row passes both times (no state leaks between tests).
"""
EOF

cat << 'EOF' > tests/integration/test_rbac_access.py
"""
FILE PURPOSE: Role-based access matrix and CSRF behaviour (acceptance: wrong-role URLs return 403, Admin cannot be registered, pending examiner blocked).
DEPENDS ON: tests/conftest.py, app/security/decorators.py, stub blueprints.
PROMPT FOR LLM IMPLEMENTATION:
1. Parametrised matrix test_role_access_matrix over (role, url, expected) for roles anonymous, student, approved_examiner, pending_examiner, inactive_examiner, admin (password-changed) and urls /admin/dashboard, /examiner/dashboard, /student/dashboard, /profile, /change-password. Expected values are 200, 302 (with the exact Location suffix: /login, /pending-approval, /account-inactive, /change-password) or 403, taken from Design Plan section 3 and the decorator order in app/security/decorators.py.
2. test_flags_checked_on_every_request: log in as an approved examiner, flip approval_status to "pending" in the database, next request redirects; flip is_active False, next request redirects to inactive.
3. test_admin_cannot_be_created_through_ui (register with role=admin, tampered role value like "Admin " and "ADMIN"; no admin row beyond the seeded one).
4. test_direct_url_access_without_session_redirects_to_login for every protected URL.
5. test_logout_form_present_for_signed_in_pages and test_no_register_link_when_signed_in.
6. CSRF: test_post_without_csrf_token_is_rejected builds an app with WTF_CSRF_ENABLED True, posts to /login without a token and expects the CSRF handler outcome (flash and redirect, never a 500 and never a successful login); test_post_with_valid_token_succeeds fetches the token from the login page HTML first.
7. test_security_cookie_flags: the session cookie is HttpOnly and SameSite=Lax (inspect Set-Cookie).
DEBUGGING:
# print(f"[DEBUG] matrix role={role} url={url} -> {response.status_code} {response.headers.get('Location')}")
OFFLINE DOCKER TEST CASES:
- The 6 x 5 matrix passes (30 parametrised cases) offline.
- Removing role_required from any stub dashboard makes at least one matrix case fail.
"""
EOF

cat << 'EOF' > tests/integration/test_error_pages.py
"""
FILE PURPOSE: Custom error pages and domain-error handling (screen PUB-07).
DEPENDS ON: tests/conftest.py, app/errors.py, app/templates/errors/*.html.
PROMPT FOR LLM IMPLEMENTATION:
1. Tests: test_404_custom_page (anonymous and signed in), test_403_custom_page_for_wrong_role, test_500_shows_request_id_without_traceback (register a throw-away route that raises RuntimeError("secret detail") in a test-only blueprint or via app.add_url_rule inside the test, with PROPAGATE_EXCEPTIONS False; assert the body has no "secret detail" and no "Traceback"), test_500_page_has_request_id_matching_header, test_app_error_flashes_and_redirects (route raising BookingError with a code and message), test_csrf_error_handler_redirects_with_flash, test_error_pages_render_without_database (monkeypatch db.session to raise and request /no-such-page, still 404 not 500), test_error_pages_have_no_external_urls.
2. Assert every error page includes the base layout (navbar brand "EMP").
DEBUGGING:
# print(f"[DEBUG] {response.status_code} len={len(response.data)} request_id_header={response.headers.get('X-Request-ID')}")
OFFLINE DOCKER TEST CASES:
- 8 tests pass offline; the throw-away route does not leak into other tests (registered on a per-test app instance).
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P2 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. For app/__init__.py give it docs/seed_updates/P2_update_app_init.md plus the CURRENT file; the same update prompt also covers tests/unit/test_smoke_app.py (root now redirects to /login)."
echo "2. Download Bootstrap 5.3.x and Bootstrap Icons into app/static/vendor/ as described in app/static/vendor/README.md (needs internet once)."
echo "3. Run 'docker compose --profile test run --rm test' (or 'make test-core'), then 'flask --app app init-db && flask --app app run --debug' and try register, login, logout and the role URLs."
echo "4. Run 'git add . && git commit -m \"wip: P2 authentication and RBAC\"'  (wip: commits are free-form)."
echo "5. When green: 'git checkout main && git merge --squash phase/p2-authentication-rbac && git commit -m \"Milestone-2 EMP-Authentication-RBAC\" && git tag p2-done && git push origin main --tags'."
echo "6. Execute P3.sh"
echo "====================================================="
