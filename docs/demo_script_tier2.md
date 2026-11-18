# Tier 2 Demo Script (8-Minute Viva Walkthrough)

## Prerequisites
1. Fresh database initialized and seeded: `flask --app app init-db && make demo-data`.
2. Start SMTP test sink in a separate terminal: `make mail-sink` (listens on `localhost:1025`).
3. Set `MAIL_SUPPRESS_SEND=false` in `.env` so transactional emails travel over SMTP to the sink.
4. Use standard demo accounts: Admin (`ADMIN_EMAIL`), Examiner (`examiner1@demo.local`), Student (`student01@demo.local`). Password: `Demo#12345`.

---

## Act 1: RESTful JSON API (`/api/v1`) (1.5 mins)
- **Goal:** Demonstrate interactive OpenAPI/Swagger docs, CRUD operations across HTTP methods, and RFC 7807 error envelopes.
- **Steps:**
  1. Open `/api/v1/docs` in browser; demonstrate Swagger UI documentation for examinations, slots, and bookings.
  2. Execute `GET /api/v1/examinations` via Swagger UI or curl; inspect pagination and payload structure.
  3. Submit invalid JSON payload to trigger `422 Unprocessable Entity`; attempt duplicate booking to trigger `409 Conflict`.
- **Expected Result:** Uniform JSON responses conforming to schema; error responses contain `title`, `status`, and `detail`.
- **Say This:** "Our API layer enforces exact role scoping, token auth, and standard HTTP error semantics without exposing internal database details."

## Act 2: Interactive Charts & Accessible Data Fallbacks (1.0 min)
- **Goal:** Show visual analytics across Admin, Examiner, and Student roles with complete accessibility fallback.
- **Steps:**
  1. Navigate to Admin, Examiner, and Student dashboards; inspect responsive Chart.js visual metrics.
  2. Click the "Toggle Data Table" control beneath any chart to inspect screen-reader accessible tabular representation.
  3. Log in as a newly registered student with zero bookings to verify clean empty-state presentation.
- **Expected Result:** High-contrast charts render smoothly offline; table toggles seamlessly for screen readers.
- **Say This:** "Per WCAG 2.1 guidelines, every visual Chart.js canvas is paired with an accessible HTML data table fallback."

## Act 3: Dual-Layer Validation & Double-Submit Protection (1.0 min)
- **Goal:** Prove strict synchronization between client-side JavaScript validation and backend WTForms / service constraints.
- **Steps:**
  1. Attempt to submit an invalid date or negative rubric score; observe inline validation errors and focus shift.
  2. Disable JavaScript in dev tools and submit the same invalid payload; verify identical server error messages.
  3. Rapidly double-click a slot booking button; observe immediate button disabling and submit-once protection.
- **Expected Result:** Input rejection is immediate on client and authoritative on server; zero duplicate submissions possible.
- **Say This:** "Validation rules are declared once and enforced on both client and server to prevent tampering."

## Act 4: Responsive Design & Accessibility Audits (1.5 mins)
- **Goal:** Verify fluid responsive breakpoints (375px mobile, 768px tablet, 1280px desktop) and keyboard navigation.
- **Steps:**
  1. Open dev tools device emulation and toggle 375px, 768px, and 1280px viewports; note table card conversions.
  2. Open and navigate the off-canvas Admin navigation drawer entirely using the `Tab` and `Esc` keys.
  3. Execute `make a11y` in terminal to run the automated Pa11y / axe accessibility test suite.
- **Expected Result:** All views adapt cleanly without horizontal overflow; automated accessibility checks pass 100%.
- **Say This:** "The UI uses a mobile-first responsive grid with keyboard traps and high contrast meeting WCAG 2.1 AA."

## Act 5: Enterprise Security & Session Controls (1.5 mins)
- **Goal:** Demonstrate Flask-Login session protection, fingerprinting, brute-force lockout, and strict CSP headers.
- **Steps:**
  1. Attempt 5 consecutive invalid logins on the same account; observe rate-limiter lockout for 15 minutes.
  2. Log in on two different browsers; change password in browser A, verify browser B session is immediately invalidated.
  3. Inspect Network response headers in dev tools: verify `Content-Security-Policy`, `X-Frame-Options: DENY`, `HSTS`.
- **Expected Result:** Lockout message displayed; session token revocation is instant; security headers strictly enforced.
- **Say This:** "We implement in-memory sliding window lockout and session fingerprinting to stop session hijacking and brute force."

## Act 6: Event-Driven Transactional Emails & Scorecard PDF (1.5 mins)
- **Goal:** Demonstrate post-commit domain events, background SMTP dispatch, email logging, and PDF scorecard download.
- **Steps:**
  1. Book an exam slot as a student; switch to the mail sink terminal and view the rendered plain-text confirmation email.
  2. Inspect Admin -> History -> Emails tab to see logged status (`sent`), recipient, and template name.
  3. Intentionally change `MAIL_PORT` to an invalid port; book another slot to prove email failure never blocks booking.
  4. Run `flask --app app jobs retry-failed-emails` to show background retry capabilities.
  5. As student, open published evaluation and click "Download scorecard (PDF)"; open generated PDF to verify layout.
- **Expected Result:** Emails are asynchronously queued via domain events; scorecard renders cleanly in ReportLab with cryptographic headers.
- **Say This:** "Domain events decouple business actions from email dispatch, ensuring transaction isolation and fault tolerance."

---

## Troubleshooting Quick Reference
| Symptom | Fix |
| :--- | :--- |
| Mail sink not receiving messages | Ensure `make mail-sink` is running on port 1025 and `MAIL_SUPPRESS_SEND=false` in `.env`. |
| Port 1025 / 5000 in use | Kill lingering process or update `MAIL_PORT` / `PORT` in `.env`. |
| Account locked out during rehearsal | Restarting the Flask process resets the in-memory rate-limiter tracker. |
| Missing fonts in scorecard PDF | Scorecard automatically falls back to standard Helvetica safely if TTF fonts are absent. |

## 12 Viva Rehearsal Questions
1. **Why migrate to Flask-Login?** Provides standardized session management, user loading, and remember-me security primitives (`app/extensions.py`).
2. **How does session fingerprinting prevent hijacking?** User-Agent and client IP hashes are verified on each request; mismatches force re-authentication (`app/security/auth_helpers.py`).
3. **Why use an in-memory sliding window for rate limiting?** High performance and zero external Redis dependency while preventing brute-force attacks (`app/security/rate_limit.py`).
4. **What attacks does our strict Content-Security-Policy prevent?** Prevents XSS, malicious script injection, and clickjacking by restricting script/style sources (`app/security/headers.py`).
5. **Why are charts paired with accessible data tables?** Satisfies WCAG 2.1 AA requirement that visual data visualizations must have screen-reader equivalents (`app/templates/macros/charts.html`).
6. **Why validate on both client and server?** Client validation provides immediate UX feedback; server validation guarantees authoritative boundary security (`app/services/validation_service.py`).
7. **How do emails avoid blocking database transactions?** Services emit domain events after `db.session.commit()`; mailer dispatches asynchronously via threads (`app/services/hooks.py`).
8. **What are the domain events used in Tier 2?** `booking.created`, `booking.cancelled`, `booking.rescheduled`, `examiner.approved`, and `evaluation.published`.
9. **How are failed emails handled?** Recorded as `failed` in `email_logs` and retried up to `MAIL_MAX_ATTEMPTS` via `retry-failed-emails` CLI job (`app/services/mailer.py`).
10. **How does the PDF scorecard ensure determinism in tests?** When `SCORECARD_DETERMINISTIC=True`, ReportLab sets fixed timestamps and invariant PDF metadata (`app/services/scorecard.py`).
11. **Why does the PDF route return 404 for foreign bookings?** Uniform 404 responses prevent ID enumeration attacks for unauthorized or unpublished records (`app/blueprints/student/scorecard.py`).
12. **What does Gate B verify?** Complete automated test suite, >=80% branch coverage, accessibility, security audits, and clean submission package (`scripts/verify_gate_b.sh`).
