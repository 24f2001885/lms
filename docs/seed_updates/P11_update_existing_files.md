<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P11 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file. Apply the sections in order. GOLDEN RULE: the helper names, decorator names, redirect priorities, flash texts and JSON error codes of Tier 1 and P7 stay exactly the same; only the machinery underneath changes, so every earlier test keeps passing.

DESIGN SUMMARY (read first)
- Flask-Login (not Flask-Security-Too) handles the session. No "remember me" cookie exists in this application.
- Session identity token = "<user id>:<fingerprint>" where fingerprint = first 16 hex characters of HMAC-SHA256(SECRET_KEY, user.password_hash). Any password change or Admin temporary password therefore invalidates every older session of that user, WITHOUT a schema change. This closes risk R-21 of the PDR.
- Idle timeout 30 minutes (rolling cookie) plus an absolute lifetime (default 8 hours) stored as login time in the session.
- Brute force: in-process sliding-window limiter, 5 failures per 15 minutes per email plus IP, and a looser per-IP limit.
- Hardening: security headers and a strict Content-Security-Policy that matches the project's local-only assets.

SECTION 1: requirements-tier2.txt
1. Add Flask-Login, pinned with == to the latest stable release that supports Python 3.11 and 3.12 and Flask 3, under the "# Tier 2" comment. No other package is added in P11 (rate limiting and headers are hand-written).

SECTION 2: app/config.py
1. Add settings read from the environment (defaults in brackets): LOGIN_RATE_LIMIT_FAILURES (5), LOGIN_RATE_LIMIT_WINDOW_MINUTES (15), LOGIN_RATE_LIMIT_IP_FAILURES (20, per IP regardless of email), SESSION_ABSOLUTE_LIFETIME_MINUTES (480), SESSION_PROTECTION ("strong"; allowed "strong", "basic"), SECURITY_HEADERS_ENABLED (true), CSP_REPORT_ONLY (false), WTF_CSRF_TIME_LIMIT (None, so a form stays valid for the whole session lifetime; the idle timeout is the control).
2. ProdConfig: SESSION_COOKIE_SECURE forced True, cookie name "__Host-emp-session" (works only over HTTPS with path "/"), refuse to start with SESSION_PROTECTION other than strong or basic. DevConfig and TestConfig keep the plain cookie name and Secure False.
3. TestConfig: the same limiter values as production (tests exercise lockout with the real numbers) and SECURITY_HEADERS_ENABLED true.

SECTION 3: app/extensions.py
1. Add login_manager = LoginManager() and, inside init_extensions(app), configure it: login_view "auth.login", session_protection from config, login_message None (we flash our own text), refresh_view not used, and call login_manager.init_app(app). Keep everything else (db, csrf, TimestampMixin, pragmas, write lock) unchanged.

SECTION 4: app/models/user.py
1. Make User inherit UserMixin (Flask-Login) in addition to its current bases. KEEP the column is_active (the mapped column overrides the mixin property); is_authenticated is True and is_anonymous False from the mixin.
2. Override get_id() to return "<id>:<fingerprint>" using app/security/session_tokens.make_token(user). Do not add any column.

SECTION 5: app/security/auth_helpers.py (same public names and behaviours)
1. login_user_session(user): session.clear() FIRST (fixation), then flask_login.login_user(user, remember=False, force=True) (force is required because inactive users must still reach the inactive notice), set session.permanent = True and session["login_at"] to the current epoch seconds from windows.now_utc(), update last_login_at, commit. Return nothing, as before.
2. logout_user_session(): flask_login.logout_user() then session.clear().
3. load_current_user (the before_request hook): set g.user = the Flask-Login current user when authenticated, otherwise None, so templates, services and the P7 API that read g.user are untouched. get_current_user() and current_user_id() keep their behaviour.
4. Register the Flask-Login user_loader: parse the session token, load the user, return None (anonymous) when the user does not exist, the fingerprint does not match the CURRENT password hash, or the absolute lifetime has passed (session["login_at"] older than SESSION_ABSOLUTE_LIFETIME_MINUTES). Never raise.
5. Register the unauthorized_handler so unauthenticated access behaves EXACTLY as in P2/P7: HTML paths flash "Please log in to continue." (warning) and redirect to auth.login; paths starting /api/ return the JSON 401 "unauthenticated".
6. Add refresh_session_after_password_change(user): after the user changed their own password, call login_user_session-like logic WITHOUT clearing the flash queue so the CURRENT browser stays signed in with the new fingerprint while every other session of that user dies.
7. validate_password_strength, is_safe_redirect_target, verify_credentials and post_login_redirect_url are unchanged (P9 already moved the limits).

SECTION 6: app/security/decorators.py
1. Replace direct session reads by flask_login.current_user (is_authenticated, is_active, role...) while keeping the check ORDER, redirects, flashes and JSON codes of TDR 6. The decorators still import nothing from blueprint modules.

SECTION 7: app/blueprints/auth/routes.py
1. POST /login: wrap the view with the rate_limited decorator ("login"); the route sets g.auth_outcome to "failure" when verify_credentials returns None and "success" after login_user_session; a blocked request returns 429 with the login template (form kept, password never echoed), the message from the limiter, and the Retry-After header. The response text for a blocked attempt does not depend on whether the email exists.
2. POST /change-password: wrap with rate_limited("password") keyed by the user id; wrong current password sets g.auth_outcome "failure". After a successful change call refresh_session_after_password_change(user) and write the audit row AUTH_PASSWORD_CHANGE (actor = user, no password data).
3. A lockout writes ONE audit row AUTH_LOCKOUT (actor null, details {"scope": "login"}; no email, only the short hash prefix of the key) the first time a key becomes blocked.
4. The session fixation behaviour of P2 stays: data set in the session before login is gone after login.

SECTION 8: app/services/audit_service.py
1. Add constants AUTH_LOCKOUT = "auth.lockout" and AUTH_PASSWORD_CHANGE = "auth.password_change".

SECTION 9: app/errors.py and templates
1. Add ERROR_HTTP_STATUS entry "too_many_requests": 429 and a handler for 429: HTML paths render errors/429.html (status 429, Retry-After header), /api/ paths return the JSON shape with code "too_many_requests" and Retry-After. The new template errors/429.html is seeded by this phase.
2. app/templates/auth/login.html: add an aria-live="polite" region above the form that shows the lockout message when present ("Too many failed attempts. Try again in N minutes.").

SECTION 10: app/__init__.py
1. Call register_security_headers(app) from app/security/headers.py after the blueprints are registered. Make sure the context processor that exposes current_user (P2) is registered AFTER login_manager.init_app so it still wins (templates expect None for anonymous users, not the Flask-Login proxy).
2. Nothing else; create_app stays free of database access.

SECTION 11: .env.example, pyproject.toml, Makefile, README.md, tests/conftest.py
1. .env.example: add the P11 variables with comments (LOGIN_RATE_LIMIT_FAILURES=5, LOGIN_RATE_LIMIT_WINDOW_MINUTES=15, LOGIN_RATE_LIMIT_IP_FAILURES=20, SESSION_ABSOLUTE_LIFETIME_MINUTES=480, SECURITY_HEADERS_ENABLED=true, CSP_REPORT_ONLY=false).
2. pyproject.toml: add the ruff rule set "S" (flake8-bandit checks, no new dependency) with per-file ignores for tests (S101 assert, S105/S106 test passwords); register the marker security.
3. Makefile: add target security (bash scripts/security_check.sh) and test-security (pytest -m security).
4. README.md: a "Security" section (what is protected, lockout numbers, session rules, headers, the note that the limiter is in-process and resets on restart).
5. tests/conftest.py: add an autouse fixture reset_rate_limits that clears the in-process limiter before every test; fixture login_attempts(client, email, passwords) that posts several logins and returns the responses; and make freeze_now also drive the limiter and session lifetime clock.

SECTION 12: tests from earlier phases
1. tests/integration/test_auth_register_login.py: the session-fixation test must now also assert that a session created before login does not survive and that the session cookie contains the Flask-Login keys; everything else is unchanged.
2. tests/integration/test_rbac_access.py: unchanged; it must pass without edits (this is the acceptance proof that the decorators behave identically).
DEBUGGING:
# print("[DEBUG] applied P11 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the complete P0-P10 suite passes without changing any assertion except the fixation test of section 12.
- Anonymous GET /admin/dashboard still redirects to /login with the same flash; anonymous GET /api/v1/examinations still returns JSON 401.
- Changing a password in one browser context makes a second context of the same user anonymous on its next request.
-->
