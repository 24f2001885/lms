#!/usr/bin/env bash
# =====================================================================
# P11.sh - Phase P11: Flask-Login Integration & Security (Tier 2)
# Course commit message : Milestone-11 EMP-Flask-Login-Security
# Branch                : phase/p11-flask-login-security
# Depends on            : P10 (tag p10-done), Gate A (tag tier1-complete)
# Source of truth       : PDR 5.7 + risk R-21, TDR 6 (sessions, CSRF, rate limiting),
#                         TDR 9/16 (LOGIN_RATE_LIMIT_* variables), Master Blueprint
#                         3.2 (P11 row)
# Acceptance            : all RBAC tests still pass; the session fixation test
#                         passes; lockout works.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P11_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P11"
BRANCH="phase/p11-flask-login-security"
PREV_TAG="p10-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P10 first."; exit 1; }
git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || { echo "GATE A CLOSED: tag tier1-complete is missing."; exit 1; }
[ -f app/security/auth_helpers.py ] || { echo "ERROR: app/security/auth_helpers.py missing (Tier 1 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
bash scripts/check_gate.sh "$BRANCH" || { echo "ERROR: gate check refused this branch."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P11 needs)
# ---------------------------------------------------------------------
mkdir -p app/security app/templates/errors scripts docs docs/seed_updates
mkdir -p tests/unit tests/integration tests/e2e

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P11_update_existing_files.md
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
EOF

# ============================== SECURITY MODULES =====================

cat << 'EOF' > app/security/session_tokens.py
"""
FILE PURPOSE: Builds and verifies the Flask-Login session identity token "<user id>:<fingerprint>" so a password change or an Admin temporary password kills every older session of that user without any database change (PDR risk R-21).
DEPENDS ON: hmac, hashlib, flask (current_app.config SECRET_KEY), app/models/user.py (read only).
PROMPT FOR LLM IMPLEMENTATION:
1. fingerprint(user) -> str: the first 16 hex characters of HMAC-SHA256 keyed with the application SECRET_KEY over user.password_hash (encode as UTF-8). It must change whenever the stored hash changes and must not reveal anything about the hash or the key.
2. make_token(user) -> str: f"{user.id}:{fingerprint(user)}".
3. parse_token(token) -> tuple[int, str] | None: split once on ":"; the id must be a positive integer and the fingerprint a 16-character hex string; any other shape returns None (never raises).
4. verify_token(token, loader) -> User | None: parse, load the user through the given loader function (so the module stays free of database code), compare fingerprints with hmac.compare_digest, return the user or None.
5. absolute_lifetime_exceeded(login_at_epoch, now_epoch, max_minutes) -> bool: True when login_at is missing, not a number, in the future by more than 60 seconds, or older than max_minutes. Missing values count as exceeded (fail closed).
6. No logging of tokens, fingerprints or hashes anywhere.
DEBUGGING:
# print(f"[DEBUG] token check user_id={user_id} match={match}")   (never print the fingerprint itself)
OFFLINE DOCKER TEST CASES:
- make_token then verify_token returns the user; after changing password_hash the same token returns None.
- parse_token("5:zz"), parse_token("abc:0123456789abcdef"), parse_token("") and parse_token(None) return None.
- Two users with the same password get different fingerprints (different salts); the fingerprint length is 16.
- absolute_lifetime_exceeded: just under the limit False, just over True, None True, a far-future value True.
- Changing SECRET_KEY invalidates previously issued tokens.
"""
EOF

cat << 'EOF' > app/security/rate_limit.py
"""
FILE PURPOSE: Small in-process sliding-window rate limiter and the rate_limited decorator used for login and change-password (TDR 6: 5 failures per 15 minutes per email plus IP, no extra dependency).
DEPENDS ON: threading, collections, hashlib, flask (request, g, make_response), app/services/windows.py (now_utc for the clock), app/services/audit_service.py (lockout audit row), app/errors.py (error_response for JSON paths).
PROMPT FOR LLM IMPLEMENTATION:
1. Class SlidingWindowLimiter(max_failures, window_seconds, max_keys=10000): thread-safe (one Lock) store key -> deque of failure timestamps (float seconds from windows.now_utc()). Methods: check(key) -> (allowed: bool, retry_after_seconds: int) which prunes timestamps older than the window and blocks when the count is at or above max_failures, retry_after = seconds until the OLDEST counted failure leaves the window (at least 1); record_failure(key) -> bool (True when THIS failure made the key blocked, used to write the lockout audit once); reset(key); clear(). When the store holds more than max_keys keys evict the least recently used ones. Never store plain emails or IPs in memory dumps: keys are strings built by the helpers below.
2. Module-level limiters created lazily from the app config (so tests can change config before first use): login_limiter (LOGIN_RATE_LIMIT_FAILURES per LOGIN_RATE_LIMIT_WINDOW_MINUTES), ip_limiter (LOGIN_RATE_LIMIT_IP_FAILURES), password_limiter (same numbers as login). reset_all() clears them (used by the test fixture).
3. Key helpers: login_keys(email, ip) -> [ "login:<sha256(email.strip().lower())[:16]>:<ip>", "ip:<ip>" ]; password_key(user_id) -> "pw:<id>". The client address is request.remote_addr (document that behind a reverse proxy the proxy must be configured with ProxyFix, not done here).
4. rate_limited(kind) decorator for a view: BEFORE the view on POST requests, check every key of that kind; if any is blocked return the 429 response (HTML: render the view's own login template through a callback named blocked_response(kind, retry_after) provided by the auth blueprint, status 429, header Retry-After; JSON paths: error_response("too_many_requests", message, 429) with Retry-After). The message is "Too many failed attempts. Try again in N minutes." with N rounded up, identical for existing and non-existing emails. AFTER the view read g.auth_outcome: "failure" -> record_failure on every key (write the AUTH_LOCKOUT audit row only when record_failure returns True); "success" -> reset the email key (the per-IP counter is NOT reset by a success); None (validation errors, GET requests) -> count nothing.
5. The decorator never changes the view's own behaviour for allowed requests, never logs emails or passwords (log WARNING with the short key hash and the kind), and works under both Flask test client and threads.
6. Document the limits in the module docstring: counters live in process memory (a restart or another worker has its own counters), which is accepted for the local single-process deployment; a shared store would be needed for production.
DEBUGGING:
# print(f"[DEBUG] limiter kind={kind} key={key[:20]} count={count} blocked={blocked} retry_after={retry_after}")
OFFLINE DOCKER TEST CASES:
- 5 failures for one key: the 6th check is blocked with retry_after between 1 and 900; after the clock moves past the window the key is allowed again.
- A success resets the email key but not the IP key; 20 failures from one IP with different emails block that IP.
- The first blocking failure returns True from record_failure, later failures return False (one audit row).
- Eviction: with max_keys=3 inserting 5 keys keeps at most 3 and keeps the most recently used.
- 50 threads recording failures concurrently never exceed the stored maximum and never raise.
- A blocked login for an unknown email returns the same status, body text and Retry-After as for an existing email.
"""
EOF

cat << 'EOF' > app/security/headers.py
"""
FILE PURPOSE: Security response headers and a strict Content-Security-Policy that fits the project (all scripts, styles, fonts and images are local; Tier 3 may extend the policy for the payment widget through add_csp_source).
DEPENDS ON: flask (request, current_app), flask_login (current_user), app config SECURITY_HEADERS_ENABLED and CSP_REPORT_ONLY.
PROMPT FOR LLM IMPLEMENTATION:
1. build_csp(extra=None) -> str: directives default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline' (templates use style attributes for progress widths; CSSOM changes made by Bootstrap and Chart.js are not affected by CSP); img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'. The extra argument is a dict directive -> list of sources appended to that directive (used later by Tier 3; Tier 2 passes nothing). A module function add_csp_source(directive, source) registers an extra source (idempotent, validates that the directive is known and the source is an https origin or a keyword in quotes).
2. register_security_headers(app): when SECURITY_HEADERS_ENABLED is false do nothing; otherwise an after_request that sets on EVERY response (HTML, JSON, errors, static): Content-Security-Policy (or Content-Security-Policy-Report-Only when CSP_REPORT_ONLY), X-Content-Type-Options nosniff, X-Frame-Options DENY, Referrer-Policy same-origin, Cross-Origin-Opener-Policy same-origin, Cross-Origin-Resource-Policy same-origin, Permissions-Policy camera=(), microphone=(), geolocation=() (do not restrict fullscreen: Tier 3 uses it); Strict-Transport-Security max-age=31536000 ONLY when request.is_secure.
3. For responses to AUTHENTICATED users (flask_login current_user.is_authenticated) that are HTML or JSON, also set Cache-Control: no-store, max-age=0 and Vary: Cookie so the browser back button after logout cannot show a cached private page; never override a Cache-Control already set by a view, and never apply it to /static/.
4. The policy must not break any page: no inline scripts, no inline event handlers and no external hosts exist in the templates (a test crawls every page to prove it). The application/json block used by validation.js is data, not a script, and is allowed.
5. No header value contains user input or request data.
DEBUGGING:
# print(f"[DEBUG] security headers applied path={request.path} csp_len={len(csp)} authenticated={current_user.is_authenticated}")
OFFLINE DOCKER TEST CASES:
- Every response (200, 302, 403, 404, 500, JSON, static) carries the six headers; HSTS is absent on http and present on a request made with base_url https.
- The CSP string contains "frame-ancestors 'none'" and does not contain "unsafe-inline" except in style-src-attr, and never "unsafe-eval".
- With CSP_REPORT_ONLY true the header name is Content-Security-Policy-Report-Only.
- An authenticated HTML response has Cache-Control no-store; an anonymous /static/ file does not.
- add_csp_source("script-src", "https://example.com") appears in the next build and add_csp_source("bogus", "x") raises ValueError.
"""
EOF

cat << 'EOF' > app/templates/errors/429.html
<!--
FILE PURPOSE: Custom "Too many requests" page (rate limit reached on JSON or non-login paths; the login page shows its own inline message).
PROMPT FOR LLM IMPLEMENTATION:
1. Extend base.html; h1 "Too many attempts"; paragraph "Please wait {{ minutes }} minute(s) before trying again." using the retry_after value passed by the handler (rounded up to whole minutes, minimum 1); a link back to the login page or the dashboard depending on whether the user is signed in.
2. No technical details, no mention of which key was limited, no counters.
3. The page must render without a database query.
DEBUGGING:
DEBUG (add as an HTML comment while debugging): retry_after={{ retry_after }}
OFFLINE DOCKER TEST CASES:
- Response status 429 with a Retry-After header and the text "Too many attempts".
-->
EOF

# ================================ SCRIPTS ============================

cat << 'EOF' > scripts/security_check.sh
#!/usr/bin/env bash
# FILE PURPOSE: One command that runs the project's offline security checks ("make security"); used before Gate B.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Bash with "set -uo pipefail"; collect failures and print a PASS/FAIL line per check and a final "SECURITY CHECK PASSED" or "FAILED (n)". Exit 0 only without failures.
# 2. Check 1: ruff check app scripts --select S (flake8-bandit rules, configured in pyproject.toml); any finding fails.
# 3. Check 2: secrets: git ls-files must not contain .env; no tracked file matches rzp_live_, a private key header, or an assignment of SECRET_KEY, ADMIN_INITIAL_PASSWORD, MAIL_PASSWORD or RAZORPAY_KEY_SECRET to anything other than an obvious placeholder (reuse the patterns of scripts/check_gate.sh).
# 4. Check 3: templates contain no inline executable script, no on* event handler attributes, no javascript: URLs and no http(s) asset URLs (grep over app/templates; application/json script blocks are allowed).
# 5. Check 4: run pytest -m security -q (the marker covers the limiter, session, header and CSP tests).
# 6. Check 5: header probe: with python -c build the app (testing config), request /login, /api/v1/docs and an error page with the test client and assert the six security headers and the CSP string are present.
# 7. Check 6: dependency pins: every line of requirements*.txt that is not a comment or an -r include must use == (no unpinned or range requirements).
# 8. Check 7: debug off: app/config.py ProdConfig has DEBUG False and refuses a missing SECRET_KEY (a small python -c assertion).
# 9. No network access is used anywhere.
# DEBUGGING:
# echo "[DEBUG] check=${NAME} status=${STATUS}" >&2   (when SEC_DEBUG=1)
# OFFLINE DOCKER TEST CASES:
# - On the finished project the script prints SECURITY CHECK PASSED and exits 0.
# - Adding an inline onclick attribute to any template makes check 3 fail.
# - An unpinned requirement (for example "flask>=3") makes check 6 fail.
EOF

# ================================ DOCS ===============================

cat << 'EOF' > docs/security_notes.md
<!--
FILE PURPOSE: Short threat-model and control table for the report and the viva ("what did you do about security?"), mapping every control to the file and the test that proves it.
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Security notes". Intro: scope is a local single-machine deployment; the goal is to show sound practice, not production hardening.
2. A table "Threats and controls" with columns Threat, Control, Where in code, Test. Rows: password theft from the database (scrypt hashes, never logged), guessing passwords (lockout 5 failures per 15 minutes per email and IP, per-IP limit 20), session fixation (session cleared at login), stolen cookie after password change or Admin reset (fingerprint token), stolen idle session (30 minute idle timeout, 8 hour absolute limit), cross-site request forgery (CSRF tokens, SameSite Lax, JSON header), cross-site scripting (autoescape, no inline scripts, strict CSP), clickjacking (frame-ancestors none, X-Frame-Options), privilege escalation (decorator order, ownership in queries, URL matrix tests), data leakage (role-scoped queries, redaction, visibility test), open redirect (safe next), SQL injection (ORM only, escaped LIKE), mass assignment (whitelisted form fields, API unknown-field rejection), cached private pages after logout (no-store), double submission (submit-once plus engine rules), overbooking (guarded UPDATE plus write lock), secrets in Git (gate and security scripts).
3. A section "Known limitations" prefilled with: rate limiter is in-process and resets on restart, no two-factor authentication, no self-service password reset (Admin-assisted), email registration reveals whether an address is taken, strong session protection can sign a user out when the client IP changes, HTTPS and HSTS depend on the deployment.
4. A section "How to verify" listing make security, make test-security and the manual checks (open two browsers, change password in one).
5. Keep it under 90 lines of plain Markdown.
DEBUGGING:
(none: documentation file)
OFFLINE DOCKER TEST CASES:
- Every "Where in code" path exists in the repository and every "Test" file exists (a small test greps the table).
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_session_tokens_and_limiter.py
"""
FILE PURPOSE: Unit tests for session_tokens and the rate limiter.
DEPENDS ON: app/security/session_tokens.py, app/security/rate_limit.py, tests/conftest.py (freeze_now, reset_rate_limits).
PROMPT FOR LLM IMPLEMENTATION:
1. Tokens: test_token_roundtrip, test_token_dies_when_password_hash_changes, test_parse_token_rejects_garbage (table of 8 bad inputs), test_fingerprint_length_and_hex, test_same_password_different_fingerprint, test_secret_key_change_invalidates, test_absolute_lifetime_boundaries (under, over, None, bad type, far future), test_no_secret_in_repr_or_logs (caplog contains no fingerprint).
2. Limiter: test_five_failures_then_blocked, test_retry_after_range_and_decreases_with_clock, test_window_expiry_unblocks, test_success_resets_email_key_not_ip_key, test_ip_limit_blocks_many_emails, test_first_block_returns_true_once, test_lru_eviction_keeps_recent, test_thread_safety_50_threads, test_keys_do_not_contain_plain_email_or_ip_in_logs, test_reset_all_clears, test_config_driven_thresholds (change config before first use).
3. Use freeze_now for every time-dependent case; never sleep.
DEBUGGING:
# print(f"[DEBUG] limiter case {name}: allowed={allowed} retry_after={retry_after}")
OFFLINE DOCKER TEST CASES:
- 21 tests pass offline.
"""
EOF

cat << 'EOF' > tests/unit/test_security_headers.py
"""
FILE PURPOSE: Unit tests for headers.py (policy string and registration).
DEPENDS ON: app/security/headers.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_build_csp_directives_exact (assert each directive and that unsafe-eval never appears and unsafe-inline appears only in style-src-attr), test_add_csp_source_validation, test_extra_sources_merge_per_directive, test_report_only_header_name, test_disabled_flag_adds_no_headers, test_hsts_only_on_https, test_no_store_for_authenticated_html_and_json, test_existing_cache_control_not_overridden, test_static_not_no_store, test_headers_on_error_responses (403, 404, 405, 429, 500), test_header_values_have_no_user_input (request with a hostile Host and query string).
DEBUGGING:
# print(f"[DEBUG] header case {name}: {dict(response.headers)}")
OFFLINE DOCKER TEST CASES:
- 12 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_flask_login_integration.py
"""
FILE PURPOSE: Proves the Flask-Login migration changed nothing visible and added the new session protections.
DEPENDS ON: tests/conftest.py (client, factories, freeze_now).
PROMPT FOR LLM IMPLEMENTATION:
1. Compatibility: test_helper_names_and_signatures_unchanged (inspect login_user_session, logout_user_session, load_current_user, verify_credentials, post_login_redirect_url), test_g_user_still_set_for_authenticated_and_none_for_anonymous, test_context_processor_current_user_none_for_anonymous, test_unauthorized_html_redirects_with_same_flash, test_unauthorized_api_returns_json_401, test_inactive_user_can_reach_inactive_page (login_user force), test_no_remember_cookie_ever_set.
2. Session security: test_session_fixation_pre_login_data_removed, test_idle_timeout_30_minutes_rolling (activity extends, inactivity expires, using freeze_now and the permanent session lifetime), test_absolute_lifetime_ends_session_even_when_active, test_cookie_flags_httponly_samesite_and_secure_in_prod_config, test_prod_cookie_name_prefix.
3. R-21 proof: test_password_change_kills_other_sessions_but_keeps_current (two clients of the same user), test_admin_temporary_password_kills_user_sessions, test_deactivation_blocks_next_request, test_approval_flip_blocks_next_request, test_logout_clears_session_and_token_not_reusable (replay the old cookie after logout: anonymous because the session cookie is the only store, so replaying works only until password change; document the expected result exactly in the test comment and assert the real behaviour).
4. strong protection: test_strong_protection_user_agent_change_signs_out, test_basic_protection_config_allows_user_agent_change.
5. The whole RBAC matrix of P2 and P7 is re-run unchanged by the existing test files (not copied here).
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.headers.get('Location')} cookie={client.get_cookie('session') is not None}")
OFFLINE DOCKER TEST CASES:
- 21 tests pass offline; removing the fingerprint from get_id makes the R-21 tests fail.
"""
EOF

cat << 'EOF' > tests/integration/test_login_lockout.py
"""
FILE PURPOSE: HTTP-level tests of the lockout (acceptance: "lockout works").
DEPENDS ON: tests/conftest.py (login_attempts, freeze_now, factories).
PROMPT FOR LLM IMPLEMENTATION:
1. test_five_wrong_passwords_then_429_with_retry_after, test_sixth_attempt_with_correct_password_still_blocked, test_lockout_message_text_and_minutes, test_window_expiry_allows_login_again, test_success_before_limit_resets_counter, test_unknown_email_locks_identically (same status, same body text, same Retry-After as a real email), test_other_email_same_ip_not_blocked_until_ip_limit, test_ip_limit_20_failures, test_validation_errors_do_not_count (blank email, malformed email), test_locked_user_other_ip_can_login (use REMOTE_ADDR in environ_overrides), test_lockout_audit_row_written_once_without_email, test_password_change_limiter_5_wrong_current_passwords, test_get_login_never_limited, test_json_path_429_shape (a limited endpoint through /api/v1 if any, else the handler directly), test_429_page_template_and_no_database_query.
2. Never sleep: move the clock with freeze_now.
DEBUGGING:
# print(f"[DEBUG] attempt={n} status={response.status_code} retry_after={response.headers.get('Retry-After')}")
OFFLINE DOCKER TEST CASES:
- 15 tests pass offline; changing LOGIN_RATE_LIMIT_FAILURES to 3 in the config changes the number of attempts needed (parametrised check).
"""
EOF

cat << 'EOF' > tests/integration/test_security_headers_csp.py
"""
FILE PURPOSE: Crawls every page and proves the CSP assumptions (no inline scripts, no handlers, no external hosts) plus header presence everywhere.
DEPENDS ON: tests/conftest.py (page_urls fixture from P10), app/security/headers.py.
PROMPT FOR LLM IMPLEMENTATION:
1. test_every_page_has_all_security_headers (public, admin, examiner, student pages), test_no_inline_executable_scripts (only script tags with src or type application/json), test_no_inline_event_handler_attributes (no attribute starting with on), test_no_javascript_urls, test_no_external_hosts_in_pages_or_css, test_forms_post_to_same_origin (form-action 'self'), test_authenticated_pages_are_no_store, test_error_pages_have_headers, test_csp_covers_static_and_json, test_api_docs_page_headers.
2. Mark with @pytest.mark.security.
DEBUGGING:
# print(f"[DEBUG] csp crawl {role} {url} scripts={script_count} inline={inline_count}")
OFFLINE DOCKER TEST CASES:
- All pages (about 60) pass; adding an onclick attribute or an inline script to any template fails the matching test and names the page.
"""
EOF

cat << 'EOF' > tests/e2e/test_security_e2e.py
"""
FILE PURPOSE: Browser-level proof that the strict CSP breaks nothing and the session protections work in a real browser.
DEPENDS ON: tests/e2e/conftest.py (live_server, browser fixtures, clock).
PROMPT FOR LLM IMPLEMENTATION:
1. Mark @pytest.mark.e2e and @pytest.mark.security.
2. test_no_csp_violations_on_any_page: walk a representative page list for each role (dashboards, forms, charts, API docs) while capturing console messages and the securitypolicyviolation event; assert zero violations and no console errors; charts and validation still work.
3. test_lockout_in_browser: five wrong passwords show the inline error each time, the sixth attempt shows the lockout message in the aria-live region, a correct password is still refused, after moving the clock past the window login works.
4. test_password_change_signs_out_other_context: the same student signed in in two browser contexts; changing the password in context A keeps A signed in and context B is sent to the login page on its next navigation.
5. test_admin_temporary_password_signs_user_out: Admin sets a temporary password for a student who is signed in; the student's next click lands on the login page; logging in with the temporary password forces the change-password screen.
6. test_idle_timeout: advance the clock 31 minutes and the next navigation lands on login; with activity every 20 minutes the session stays alive until the 8 hour absolute limit.
7. test_back_button_after_logout_shows_no_private_page: log out then history back; the page is the login page or a reload, never cached private content (no-store).
8. test_cookie_attributes_in_browser: the session cookie is HttpOnly and SameSite Lax and not readable from page JavaScript (document.cookie does not contain it).
DEBUGGING:
# print(f"[DEBUG] e2e security step={step} url={page.url} clock={windows.now_utc()}")
OFFLINE DOCKER TEST CASES:
- All tests pass with the network disabled; relaxing the CSP makes no test fail but removing a local asset reference or adding an inline handler makes test_no_csp_violations_on_any_page fail.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs scripts -type d -empty -exec touch {}/.gitkeep \;
chmod +x scripts/*.sh 2>/dev/null || true

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P11 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P11_update_existing_files.md in ORDER (config, extensions, user model, auth helpers, decorators first) with the CURRENT files; the rule is that all earlier tests pass unchanged except the fixation test."
echo "2. Run 'make test-core', 'make test-security' and 'make security'; then try the lockout and the two-browser password change by hand."
echo "3. Run 'git add . && git commit -m \"wip: P11 flask-login and security\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p11-flask-login-security && git commit -m \"Milestone-11 EMP-Flask-Login-Security\" && git tag p11-done && git push origin main --tags'."
echo "5. Decisions to confirm: Flask-Login chosen over Flask-Security-Too; password-hash fingerprint in the session id (closes R-21 without a schema change); absolute session lifetime 8 hours; per-IP limit of 20 failures; strict CSP with style-src-attr 'unsafe-inline'; no-store on authenticated pages."
echo "6. Execute P12.sh"
echo "====================================================="
