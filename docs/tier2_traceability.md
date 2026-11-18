# Tier 2 Traceability Matrix

| ID | Requirement (from PDR 3.3 and 5.7) | Phase | Automated Test File | Demo Act | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T2-01 | JSON API with at least four HTTP methods (GET, POST, PUT, DELETE) | P7 | `tests/integration/test_api_examinations_slots.py` | Act 1 | yes |
| T2-02 | API errors and pagination contract | P7 | `tests/integration/test_api_contract_errors.py` | Act 1 | yes |
| T2-03 | API reference page | P7 | `tests/integration/test_api_access_matrix.py` | Act 1 | yes |
| T2-04 | Role scoping identical to HTML | P7 | `tests/integration/test_api_access_matrix.py` | Act 1 | yes |
| T2-05 | Admin charts (booking trend, completion, workload) | P8 | `tests/integration/test_chart_pages.py` | Act 2 | yes |
| T2-06 | Examiner charts (students evaluated, participants) | P8 | `tests/integration/test_chart_pages.py` | Act 2 | yes |
| T2-07 | Student charts (history, trend, results) | P8 | `tests/integration/test_chart_pages.py` | Act 2 | yes |
| T2-08 | Chart data-table fallback and offline Chart.js | P8 | `tests/integration/test_chart_pages.py` | Act 2 | yes |
| T2-09 | HTML5 validation attributes | P9 | `tests/integration/test_html5_attributes.py` | Act 3 | yes |
| T2-10 | JavaScript validation mirroring the server | P9 | `tests/e2e/test_client_validation.py` | Act 3 | yes |
| T2-11 | Server validation for dates, timelines, capacity, rubric and marks | P9 | `tests/integration/test_server_validation_matrix.py` | Act 3 | yes |
| T2-12 | Duplicate booking protection (server and submit-once) | P9 | `tests/integration/test_server_validation_matrix.py` | Act 3 | yes |
| T2-13 | Responsive layouts at 375, 768 and 1280 px | P10 | `tests/integration/test_responsive_markup.py` | Act 4 | yes |
| T2-14 | Table cards and off-canvas Admin menu | P10 | `tests/integration/test_responsive_markup.py` | Act 4 | yes |
| T2-15 | WCAG 2.1 AA checks (contrast, keyboard, static audit) | P10 | `tests/integration/test_accessibility_static.py` | Act 4 | yes |
| T2-16 | Flask-Login based sessions with unchanged RBAC | P11 | `tests/integration/test_flask_login_integration.py` | Act 5 | yes |
| T2-17 | Session fixation protection | P11 | `tests/integration/test_flask_login_integration.py` | Act 5 | yes |
| T2-18 | Idle and absolute timeout | P11 | `tests/integration/test_flask_login_integration.py` | Act 5 | yes |
| T2-19 | Password change invalidating other sessions | P11 | `tests/integration/test_flask_login_integration.py` | Act 5 | yes |
| T2-20 | Login lockout (5 failures per 15 minutes) | P11 | `tests/integration/test_login_lockout.py` | Act 5 | yes |
| T2-21 | Security headers and strict CSP | P11 | `tests/integration/test_security_headers_csp.py` | Act 5 | yes |
| T2-22 | Scorecard PDF download for published results only | P12 | `tests/integration/test_scorecard_route_history_tab_jobs.py` | Act 6 | yes |
| T2-23 | Booking confirmation email | P12 | `tests/integration/test_email_triggers.py` | Act 6 | yes |
| T2-24 | Cancellation, reschedule and examiner-approval emails | P12 | `tests/integration/test_email_triggers.py` | Act 6 | yes |
| T2-25 | Result publication email without marks | P12 | `tests/integration/test_email_triggers.py` | Act 6 | yes |
| T2-26 | Email log with failure recording | P12 | `tests/unit/test_email_log_and_events.py` | Act 6 | yes |
| T2-27 | Email failure never blocking a booking | P12 | `tests/integration/test_email_triggers.py` | Act 6 | yes |
| T2-28 | retry-failed-emails job | P12 | `tests/integration/test_scorecard_route_history_tab_jobs.py` | Act 6 | yes |
| T2-29 | Email log retention | P12 | `tests/integration/test_scorecard_route_history_tab_jobs.py` | Act 6 | yes |
