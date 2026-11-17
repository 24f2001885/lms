# Security notes

This document summarizes the threat model and controls for the Examination Management Portal (EMP). The target deployment is a local, single-machine environment.

## Threats and controls

| Threat | Control | Where in code | Test |
|---|---|---|---|
| Password theft from DB | `scrypt` hashing via Werkzeug, never logged | `app/models/user.py` | `test_models_users_profiles.py` |
| Guessing passwords (Brute force) | Sliding-window rate limiter: 5 failures / 15 min / email+IP, 20 per IP | `app/security/rate_limit.py` | `test_login_lockout.py` |
| Session fixation | `session.clear()` called at login before issuing new token | `app/security/auth_helpers.py` | `test_flask_login_integration.py` |
| Stolen cookie after password change | Session ID includes fingerprint of password hash (closes R-21) | `app/security/session_tokens.py` | `test_flask_login_integration.py` |
| Stolen idle session | 30-min idle timeout, 8-hour absolute lifetime | `app/config.py`, `auth_helpers.py` | `test_flask_login_integration.py`, `test_security_e2e.py` |
| Cross-site request forgery (CSRF) | Flask-WTF tokens, `SameSite=Lax`, JSON `X-CSRFToken` header | `app/extensions.py`, `app/blueprints/api_v1/common.py` | `test_rbac_access.py`, `test_api_access_matrix.py` |
| Cross-site scripting (XSS) | Jinja autoescape, no inline scripts, strict CSP | `app/security/headers.py` | `test_security_headers_csp.py`, `test_security_e2e.py` |
| Clickjacking | `X-Frame-Options: DENY`, `frame-ancestors 'none'` in CSP | `app/security/headers.py` | `test_security_headers_csp.py` |
| Privilege escalation | Role decorators, ownership checks in queries | `app/security/decorators.py`, `app/services/` | `test_admin_access_control.py`, `test_examiner_access_ownership.py`, `test_student_access_ownership.py` |
| Data leakage | Role-scoped queries, timeline redaction | `app/services/history_service.py`, `student_queries.py`, `api_queries.py` | `test_role_scoped_visibility.py` |
| Open redirect | `is_safe_redirect_target` prevents external/malicious URLs | `app/security/auth_helpers.py` | `test_auth_helpers.py` |
| SQL injection | SQLAlchemy ORM, escaped `LIKE` wildcards | `app/services/search_service.py` | `test_audit_search_slot_rules.py` |
| Mass assignment | Whitelisted form fields, API `validate` rejects unknown fields | `app/blueprints/auth/profile.py`, `app/blueprints/api_v1/validation.py` | `test_server_validation_matrix.py`, `test_api_validation_serializers.py` |
| Cached private pages | `Cache-Control: no-store` on authenticated HTML/JSON | `app/security/headers.py` | `test_security_headers_csp.py` |
| Double submission | JS `data-submit-once`, engine transaction locks | `app/static/js/validation.js`, `app/services/booking_engine.py` | `test_client_validation.py`, `test_booking_engine_concurrency.py` |
| Overbooking | Guarded `UPDATE` + `BEGIN IMMEDIATE` lock | `app/services/booking_engine.py`, `app/extensions.py` | `test_booking_engine_concurrency.py` |
| Secrets in Git | CI gate checks, `flake8-bandit`, grep filters | `scripts/check_gate.sh`, `scripts/security_check.sh` | `check_gate.sh` |

## Known limitations
- Rate limiter is in-process and resets on restart.
- No two-factor authentication.
- No self-service password reset (Admin-assisted only).
- Email registration reveals whether an address is taken.
- Strong session protection can sign a user out when their client IP/User-Agent changes.
- HTTPS and HSTS depend on the external deployment configuration (e.g., reverse proxy).

## How to verify
Run `make security` and `make test-security`.
Manual checks: Open two browsers as the same user, change the password in one, and verify the other is logged out on its next request. Test login lockout by submitting 5 incorrect passwords.
