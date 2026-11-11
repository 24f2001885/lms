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
