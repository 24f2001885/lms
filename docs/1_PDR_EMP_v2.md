# PROJECT DEFINITION REPORT (PDR): Examination Management Portal (EMP), v2

*Course: Modern Application Development I (MAD-I). Sources: appdev1_project_statement_sep26, Milestones for Examination Management Portal, plus the tertiary-tier additions requested in chat (online tests, anti-cheat, Razorpay fee payment).*

**Delivery model in one line:** Tier 1 (Primary, mandatory course scope) → Tier 2 (Secondary, recommended/optional course scope) → Tier 3 (Tertiary, extra scope). **Nothing in Tier 3 may be started until every Tier 1 and Tier 2 item is finished, tested and tagged in Git.**

---

## 1. Executive Summary

Institutions still run viva, practical and project-demo examinations on spreadsheets, email and manual coordination, which makes it hard to schedule slots, avoid double-booking and keep reliable evaluation records.

The **Examination Management Portal (EMP)** is a role-based web application for **Admins**, **Examiners** and **Students**.

- **Tier 1 (Primary):** Admins configure courses, examinations, rubrics and time windows and approve examiners. Examiners create slots and evaluate booked students. Students book slots, cancel, and see results. Capacity, time-window and ownership rules are enforced automatically.
- **Tier 2 (Secondary):** JSON API, charts, validation, responsive UI, Flask-Login security, scorecard download, email notifications.
- **Tier 3 (Tertiary):** An online test module (three delivery modes), anti-cheat monitoring with auto-submit and an admin violation report, and Razorpay (test mode) payment of the examination fee.

Stack (mandatory): **Flask, Jinja2/HTML/CSS/Bootstrap, SQLite**. The demo must run on a local machine and the database must be created programmatically.

---

## 2. Project Objectives

### 2.1 Primary Objectives (Tier 1)
1. Three role-based experiences (Admin, Examiner, Student) with separate dashboards and strict access control.
2. Admin manages courses, examinations, rubrics, timelines, examiner approval, slot-creation window and booking window.
3. Examiners create and manage slots only in the creation period, and evaluate only students booked into their own slots.
4. Students discover examinations, book and cancel slots, and view status, history, results and feedback.
5. Data integrity: no overbooking, no duplicate bookings per examination, automatic slot closure at capacity, complete booking history.
6. Programmatic database creation with a pre-seeded Admin.

### 2.2 Secondary Objectives (Tier 2)
- JSON APIs for examinations, examiners, students, slots and bookings.
- Charts for booking trends, examiner workload and examination completion.
- Frontend (HTML5/JS) and backend validation.
- Responsive Bootstrap UI.
- Flask-Login / Flask-Security role-based route protection.
- Downloadable examination scorecard and email notifications (booking confirmation, result publication).

### 2.3 Tertiary Objectives (Tier 3, started only after Tier 1 and Tier 2 are complete)
1. **Online tests** attached to an examination, in three delivery modes:
   - **Standard:** same questions for all students, free navigation.
   - **Randomised, forward-only:** each student gets a random question set/order; once answered, no question can be revisited.
   - **Randomised, revisitable:** each student gets a random question set/order; questions can be revisited and answers changed until submission.
2. **Anti-cheat monitoring:** if the student leaves the test (tab/window/app focus lost, fullscreen exit), the test is auto-submitted and the event is recorded and reported to the Admin.
3. **Razorpay payment (sandbox/test mode)** of the examination fee before a booking is confirmed.

---

## 3. Scope of Work

### 3.1 Delivery Tiers and Gate Rules

| Tier | Contents | Origin | Start condition |
|---|---|---|---|
| **Tier 1: Primary** | Milestones M0 to M6 (phases P0 to P6) | Mandatory in course statement | Immediately |
| **Tier 2: Secondary** | Optional enhancements (phases P7 to P12) | Recommended/optional in course statement | **Gate A:** every Tier 1 acceptance check passes, `tier1-complete` tag exists |
| **Tier 3: Tertiary** | Online tests, anti-cheat, Razorpay (phases P13 to P17) | Added by the team, not in the course statement | **Gate B:** every Tier 1 and Tier 2 check passes, `tier2-complete` tag exists, final-submission package for Tier 1+2 is ready |

Rules:
1. No Tier 3 file, table, route, dependency or branch is created before Gate B.
2. Tier 3 code lives in isolated modules and is switched off by default with feature flags (`ENABLE_ONLINE_TESTS`, `ENABLE_PROCTORING`, `ENABLE_PAYMENTS`). If Tier 3 is unfinished at submission time, the flags stay off and the app still meets every course requirement.
3. A Tier 3 defect must never break a Tier 1 or Tier 2 flow. The full Tier 1 and Tier 2 regression suite must pass before each Tier 3 phase is merged.

### 3.2 In-Scope: Tier 1 (Primary)
- Programmatic SQLite creation; pre-created Admin (no Admin registration).
- Registration/login for Examiners and Students; login for Admin; Admin approval gate for Examiners.
- Admin dashboard totals (courses, examinations, examiners, students, slots, bookings).
- Admin CRUD for Courses, Examinations, Rubrics; add/approve/deactivate examiners; timelines; open/close slot creation; open/close student booking.
- Admin: view/search students, examiners, examinations, bookings by name or ID; view all slots; reschedule bookings; change assigned examiner; view all historical data.
- Examiner dashboard (assigned examinations, created slots, students booked, pending evaluations); slot create/update/remove with window rules; view booked students; rubric evaluation with marks and remarks.
- Student dashboard (available examinations, slots, upcoming, booked, results); search/filter; book; cancel before deadline; status, schedule, history, results, feedback; profile edit.
- Business rules: capacity, duplicate prevention, auto-close on full, status tracking.
- Deliverables: zip, report (up to 5 pages), demo video, AI/LLM declaration, one unique Git commit message per milestone.

### 3.3 In-Scope: Tier 2 (Secondary)
JSON API, Chart.js charts, HTML5/JS plus server validation, Bootstrap responsive polish, Flask-Login/Security, scorecard PDF download, email notifications. (Scorecard and email are listed in the course statement's recommended features but have no milestone of their own; they are scheduled here as phase P12.)

### 3.4 In-Scope: Tier 3 (Tertiary)
- **Question bank and test builder:** Admin or assigned Examiner creates a test for an examination: title, duration, delivery mode, number of questions drawn, marks per question, pass mark, availability window; MCQ questions with options and one correct answer (single choice).
- **Test delivery:** per-student attempt with its own saved question order, a server-enforced deadline, auto-submit on timeout, auto-scoring, and result visible to the student per the publish setting.
- **Anti-cheat:** browser-side event reporting (visibility change, window blur, fullscreen exit, copy/paste/context-menu attempts), server-side violation log, auto-submit on violation (default: first violation; configurable strikes), Admin report and per-attempt violation timeline.
- **Payments:** examination fee per examination (in paise), Razorpay order creation, checkout, server-side signature verification, payment records, seat hold while paying, refund-on-cancel (test mode), Admin payments view.

### 3.5 Out-of-Scope
- Any database other than SQLite; manual DB creation; any CSS framework other than Bootstrap; JavaScript for core Tier 1 logic.
- Native mobile apps; Admin self-registration; production cloud deployment.
- Live video proctoring, webcam/screen recording, face detection, OS-level app monitoring, or detecting *which* other app was opened (not possible from a web browser; see Risk R-14).
- Subjective/essay questions with manual grading in the test module (MCQ only in Tier 3).
- Real-money payments, live Razorpay keys, payouts, invoicing and GST handling.
- Support ticketing (not in the statement).
- Exact replication of the supplied wireframe.

---

## 4. User Personas

| Persona | Description | Primary needs |
|---|---|---|
| **Admin** | Pre-existing superuser managing the whole system. | Configure courses, exams, rubrics and windows; approve examiners; oversee everything; fix conflicts. *(Tier 3)* Build or review tests, view violation reports and payments. |
| **Examiner** | Approved faculty member. | See assigned examinations; publish slots; evaluate booked students. *(Tier 3)* Author questions for own examinations, view attempt scores. |
| **Student** | Registered user. | Find and book a slot, cancel, track history and results. *(Tier 3)* Pay the examination fee, take the online test fairly and clearly informed of the monitoring rules. |

---

## 5. Functional Requirements

### 5.1 Admin Control Panel (Tier 1, Priority #1)
- Dashboard counts of courses, examinations, examiners, students, slots, bookings.
- Course CRUD (ID, Code, Name, Description, Status, extras).
- Examination CRUD (ID, Course, Name, Type: Viva / Practical / Project Demo / Assessment, Duration, Maximum Marks, Slot Creation Start/End, Slot Booking Start/End, Status, extras).
- Rubric management per examination (Weightage, Description, extras).
- Examiner add/approve/deactivate; timeline configuration; open/close slot creation; open/close booking.
- Oversight: view all slots, students, examiners, examinations, bookings; search by name or ID; reschedule bookings; change assigned examiner; view all history.
- Admin cannot be registered through the UI; it must pre-exist.

### 5.2 Authentication & Role Access (Tier 1)
- Login for all roles; registration for Examiners and Students only.
- Examiner dashboard locked until Admin approval ("pending approval" page).
- Role-specific redirect after login and role-restricted routes; hashed passwords; protected sessions.

### 5.3 Examiner Slot Management (Tier 1)
- Create slots (Date, Start, End, Max Capacity) only during the slot-creation period; update or remove only before student booking starts.
- Slot status: Available, Full, Cancelled, Completed. Available seats = capacity minus active bookings.
- Examiners manage slots only on examinations assigned to them.

### 5.4 Student Slot Booking (Tier 1)
- Search/filter examinations; view available slots; book only while booking is open.
- No overbooking; auto "Full" at capacity; one active booking per student per examination; cancel only before the deadline (seat is freed).
- Booking status: Booked / Cancelled / Completed; cancelled bookings stay in history.
- Admin may reschedule a booking to another slot of the same examination.

### 5.5 Evaluation & Results (Tier 1)
- Examiners see only students in their own slots; evaluate with the rubric; submit marks (not above Maximum Marks) and remarks.
- "Pending evaluations" counter; students see only their own published results and feedback.
- Examination status: Draft, Slot Creation, Booking Open, Closed, Completed.

### 5.6 Booking History & Reporting (Tier 1)
Complete per-student history; Admin sees all history; students see booking history, examination history, schedule, upcoming examinations.

### 5.7 Recommended / Optional Features (Tier 2, after Gate A)
JSON API; charts (Admin: bookings, completion, workload; Examiner: students evaluated, participants; Student: history, trends, results); HTML5/JS plus server validation; responsive UI; Flask-Login/Security; scorecard PDF; email notifications.

### 5.8 Online Test Module (Tier 3, after Gate B)

**Test authoring**
- Admin (any) or assigned Examiner (own examinations) creates a test linked to an examination: title, instructions, duration (minutes), delivery mode, questions per attempt, marks per question, negative marking (optional, default 0), pass mark, availability window, result-publish mode (immediate or manual).
- Question bank per test: question text, 2 to 6 options, one correct option, marks (default from test), optional explanation.
- A test can only be edited while it has no attempts.

**Delivery modes**

| Mode (`delivery_mode`) | Question set | Order | Navigation | Answer change |
|---|---|---|---|---|
| `standard` | Same for all students | Fixed (author order) | Free (previous/next, jump) | Allowed until submit |
| `random_forward_only` | Random subset per student, fixed at attempt start | Random per student | **Forward only**, one question at a time, no going back | **Not allowed** after moving on |
| `random_revisitable` | Random subset per student, fixed at attempt start | Random per student | Free (previous/next, jump, mark for review) | Allowed until submit |

Rules for all modes:
- A student may start a test only if they hold a valid booking (and, when payments are on, a paid booking) for that examination and the availability window is open.
- One attempt per student per test (admin may reset an attempt, which is logged).
- The question set and order are generated once at attempt start and stored, so a page refresh or reconnect returns the same questions.
- The deadline is server-side: `started_at + duration`. The browser timer is cosmetic. Late answers are rejected, and the attempt auto-submits on expiry.
- Scoring is automatic on submit; the result is shown per the publish mode.
- In forward-only mode the server rejects any request for a question index lower than the current pointer, so the rule holds even if a student edits the URL.

**Anti-cheat monitoring**
- Test runs in a monitored page; the student must accept a rules notice before starting.
- Browser script reports: tab hidden, window blur, fullscreen exit (if fullscreen is required), copy/cut/paste and right-click attempts.
- Server records each event with timestamp, event type, duration away and question index.
- Policy per test: `max_violations` (default 1). Reaching the limit auto-submits the attempt with status `auto_submitted_violation`.
- Admin report: list of attempts with violation counts, a timeline per attempt, filter by test/student/date, export as CSV.
- Honest limitation: the browser can report that the page lost focus, not which application or website was opened. The report shows *when and for how long* the student left, not *what* they opened. (Optional extra for the future: periodic "still here" heartbeats to detect closed or frozen sessions.)

### 5.9 Examination Fee Payments (Tier 3, after Gate B)
- Each examination has `fee_amount_paise` (0 means free; free examinations skip payment).
- Student flow: choose slot, a **seat hold** reserves the seat for 10 minutes, create Razorpay order, pay in the Razorpay checkout, server verifies the signature, booking becomes `Booked` and payment `paid`. Failure or timeout releases the seat.
- Receipt and payment status visible to the student; Admin payments list with filters.
- Cancellation before the deadline triggers a refund request in test mode and sets payment `refunded`.
- Test keys only; keys come from environment variables and are never committed.

---

## 6. Non-Functional Requirements

- **Security:** hashed passwords; server-side role checks on every route; CSRF protection on all forms; ORM or parameterised queries only; secrets in `.env`.
- **Integrity:** DB constraints (unique, foreign key, check) plus transactional booking logic.
- **Performance:** pages under 500 ms p95 locally with about 1,000 students and 10,000 bookings; paginated lists. *(Tier 3)* Answer-save requests under 300 ms; 100 simultaneous test takers on a local machine without errors.
- **Availability:** zero crashes in the viva demo flow.
- **Compatibility:** latest Chrome, Edge, Firefox; mobile, tablet, desktop widths. *(Tier 3)* Anti-cheat targets desktop browsers; mobile test taking is allowed but flagged as weaker monitoring.
- **Accessibility:** WCAG 2.1 AA target.
- **Maintainability:** modular Flask blueprints; README with setup and known issues. Tier 3 modules isolated behind feature flags.
- **Reproducibility:** DB and Admin created by code on first run.
- **Privacy (Tier 3):** violation logs contain only event type, time and duration; no screenshots, no webcam, no keystroke capture. Students are told what is monitored before starting.

---

## 7. System Architecture (Overview)

A **monolithic, server-rendered Flask application** (MVC-style: models, blueprints/controllers, Jinja2 templates) with one SQLite file. Chosen because the stack is mandated, the user base is modest and a monolith is simplest to demo and debug.

- Browser → Flask blueprints (`auth`, `admin`, `examiner`, `student`, later `api`) → service layer → SQLAlchemy models → SQLite.
- Role decorators guard every route; business rules live in a service layer so the API and HTML views share them.
- **Tier 3 additions** are separate blueprints and services (`tests`, `proctoring`, `payments`) registered only when their feature flag is on.
- Outbound integration (Tier 3): Razorpay REST API (test mode) over HTTPS. Everything else works offline.
- Deployment: local machine (virtualenv; Docker optional for reproducibility). Submitted as a single zip.

---

## 8. Database Schema (Summary)

**Tier 1 entities:** `users`, `examiner_profiles`, `student_profiles`, `courses`, `examinations`, `examination_rubrics`, `examination_examiners`, `examination_slots`, `bookings`, `evaluations`, `evaluation_scores`, `audit_logs`.

**Tier 2 entity:** `email_logs`.

**Tier 3 entities (created only after Gate B):** `examination_fees`, `tests`, `test_questions`, `test_options`, `test_attempts`, `attempt_questions`, `attempt_answers`, `proctoring_events`, `payments`, `seat_holds`, `refunds`. Tier 3 is purely additive: no Tier 1 or Tier 2 table is altered (the fee lives in `examination_fees` and the payment-pending seat reservation in `seat_holds`).

Key relationships:
- Course 1-N Examination; Examination 1-N Rubric, Slot; Examination N-N Examiner (via `examination_examiners`).
- Slot 1-N Booking; Student 1-N Booking; Booking 1-1 Evaluation; Evaluation 1-N EvaluationScore (per rubric criterion).
- *(Tier 3)* Examination 1-N Test; Test 1-N Question; Question 1-N Option; Booking 1-N TestAttempt (one allowed); Attempt 1-N AttemptQuestion/AttemptAnswer/ProctoringEvent; Booking 1-N Payment; Payment 1-N Refund.

*Assumption:* the statement allows adding or removing tables; Evaluation, junction and audit tables are added for the evaluation and "change examiner" requirements. Full column definitions are in the TDR. An ER diagram is required in the final report.

---

## 9. Technology Stack

| Layer | Choice | Tier |
|---|---|---|
| Backend | Python 3, Flask | 1 |
| ORM | Flask-SQLAlchemy | 1 |
| Frontend | Jinja2, HTML5, CSS, Bootstrap (no other CSS framework) | 1 |
| Database | SQLite, created programmatically | 1 |
| Forms/CSRF | Flask-WTF | 1 |
| Auth | Werkzeug hashing; session auth in Tier 1; Flask-Login in Tier 2 | 1/2 |
| API | Flask-RESTful or manual JSON controllers | 2 |
| Charts | Chart.js | 2 |
| Email | Flask-Mail with a local debug SMTP | 2 |
| Scorecard PDF | ReportLab (or WeasyPrint) | 2 |
| Anti-cheat client | Small vanilla JS using Page Visibility, blur and Fullscreen APIs | 3 |
| Payments | `razorpay` Python SDK, Razorpay Checkout JS, test mode | 3 |
| Tooling | Git + private GitHub repo (collaborator `MADI-cs2003`), virtualenv, `requirements.txt`, optional Docker | 1 |

JavaScript is not used for Tier 1 core requirements. Tier 3 needs JS only for anti-cheat reporting, the cosmetic timer and the Razorpay popup; every rule (forward-only, deadline, scoring, signature check) is enforced on the server.

---

## 10. Development Phases & Timeline

Core (Tier 1) phases may be done in any order, as the course allows; the order below is the recommended dependency order. Each phase ends with a unique Git commit message, a push, and a green test run.

| Phase | Course milestone | Goal / key features | Est. time | Tier |
|---|---|---|---|---|
| P0 | M0 GitHub Repository Setup (due 17/11/2026) | Private repo, README, .gitignore, initial push, add `MADI-cs2003`. Commit `Milestone-0 EMP-MAD-1` | 1 day | 1 |
| P1 | M1 Database Models & Schema | Models, relationships, programmatic Admin seed | 5-7 days | 1 |
| P2 | M2 Authentication & Role-Based Access | Registration/login, examiner approval gate, role redirects | 5 days | 1 |
| P3 | M3 Admin Dashboard & Examination Management | Dashboard, CRUD, windows, search, reschedule, change examiner | 7-9 days | 1 |
| P4 | M4 Examiner Dashboard & Slot Management | Slots with window rules, booked students, evaluation | 7 days | 1 |
| P5 | M5 Student Dashboard & Slot Booking | Search, book, cancel, history, results | 7 days | 1 |
| P6 | M6 Booking History & Evaluation Tracking | Capacity engine, statuses, history, evaluation records | 5 days | 1 |
| **GATE A** | | All Tier 1 acceptance checks pass; tag `tier1-complete` | | |
| P7 | API Integration | JSON APIs, at least 4 HTTP methods | 7 days | 2 |
| P8 | Charts & Visualization | Chart.js for three roles | 5 days | 2 |
| P9 | Frontend & Backend Validation | HTML5/JS plus server validation | 5 days | 2 |
| P10 | Responsive UI & Styling | Bootstrap polish, responsive layouts | 5 days | 2 |
| P11 | Flask-Login Integration & Security | Flask-Login/Security, protected sessions | 5-7 days | 2 |
| P12 | Scorecard & Email Notifications | PDF scorecard, booking/result emails (added beyond the 5 course enhancements) | 4-5 days | 2 |
| **GATE B** | | All Tier 1 and 2 checks pass; tag `tier2-complete`; Tier 1+2 submission package ready | | |
| P13 | T1 Test Engine Foundation | Question bank, test builder, test/attempt tables, feature flag | 5-7 days | 3 |
| P14 | T2 Test Delivery Modes | Standard, random forward-only, random revisitable; timer; scoring | 8-11 days | 3 |
| P15 | T3 Anti-Cheat & Violation Reports | Event capture, auto-submit, admin report | 4-6 days | 3 |
| P16 | T4 Razorpay Fee Payments | Order, checkout, signature verification, seat hold, refund | 4-6 days | 3 |
| P17 | T5 Tier 3 Integration & Hardening | Cross-feature edge cases, load check, regression, docs | 4-5 days | 3 |
| Final | Final Submission | ZIP, report (up to 5 pages), video (5-10 min), AI declaration. Commit `Milestone-EMP Final-Submission` | 2 days | all |

### Complexity impact

| | Effort | Tables | Relative complexity |
|---|---|---|---|
| Tier 1 | about 37-41 days | 12 | 1.0x (baseline) |
| Tier 2 | about 31-37 days (mostly mechanical polish) | 0 new | about 1.4x cumulative |
| Tier 3 | about 25-35 days | +11 new tables, no existing table changed | **about 1.7-1.9x cumulative** |

The hardest Tier 3 parts are the attempt state machine (modes, deadline, refresh safety) and payment consistency (seat hold, verification, refunds), not the anti-cheat script.

**Submission planning:** the course Final Submission can be made at Gate B (Tier 1+2 only, flags off). Tier 3 is added to the submission only if P17 passes completely before the freeze date (problem statement frozen on or before 10/10/2026); otherwise it ships disabled or is left out.

---

## 11. Admin & Permission Model

Yes = allowed, No = denied, Limited = with the restriction shown.

| Resource / Action | Admin | Examiner | Student |
|---|---|---|---|
| Register / log in | Log in only (pre-seeded) | Yes (needs approval) | Yes |
| Courses / examinations / rubrics CRUD | Yes | No | No |
| Approve / deactivate examiners | Yes | No | No |
| Timelines, open/close slot creation and booking | Yes | No | No |
| View examinations | Yes, all | Limited: assigned | Limited: available |
| Create / update / remove slots | No | Limited: own exams, window rules | No |
| Book / cancel a booking | Cancel: Yes | No | Limited: window and deadline rules |
| Reschedule booking, change examiner | Yes | No | No |
| View booked students | Yes, all | Limited: own slots | No |
| Evaluate, submit marks and remarks | No | Limited: own slots only | No |
| View results and feedback | Yes, all | Limited: own | Limited: own |
| Search all records, view all history | Yes | No | No |
| *(T3)* Create tests and questions | Yes | Limited: own examinations | No |
| *(T3)* Take a test | No | No | Limited: valid booking (and payment), window open, one attempt |
| *(T3)* View attempt scores | Yes, all | Limited: own tests | Limited: own, per publish mode |
| *(T3)* View violation reports | Yes | No | No |
| *(T3)* Reset an attempt | Yes (logged) | No | No |
| *(T3)* Pay examination fee | No | No | Yes |
| *(T3)* View payments / refund | Yes, all | No | Limited: own |

---

## 12. Risk Analysis & Mitigation

| ID | Risk | Impact | Mitigation |
|---|---|---|---|
| R-1 | Race condition on the last seat | Overbooking | Single write transaction, check-and-insert, partial unique index, capacity CHECK constraint |
| R-2 | Duplicate bookings across slots | Inconsistent data | Server check plus partial unique index on (student, examination) for active bookings |
| R-3 | Time-window bugs (timezone, date vs datetime) | Wrong open/close behaviour | One window helper, UTC storage, boundary tests |
| R-4 | Broken access control | Data exposure, unfair evaluation | Role decorators, ownership checks on queries, direct-URL tests |
| R-5 | Pending/deactivated examiner stays active | Unauthorised access | Check flags on every request |
| R-6 | Manual DB creation or missing Admin | Rule violation, failed viva | Idempotent `create_db` seeding |
| R-7 | Cascading deletes destroy history | Data loss | Soft delete, block deletes with bookings |
| R-8 | JS used for core logic, or non-Bootstrap CSS | Rule violation | Checklist before each phase; keep logic server-side |
| R-9 | AI/LLM over-reliance | Viva failure | Understand every file; keep the AI-use log |
| R-10 | Missed Git/commit rules | Lost marks | Unique message per phase; push after each |
| R-11 | **Scope creep: Tier 3 started early** | Core incomplete, deadline missed | Gate A/B rules, feature flags, no Tier 3 branch before `tier2-complete` |
| R-12 | **Tier 3 breaks core flows** | Failed demo | Isolated blueprints, flags default off, full regression before every Tier 3 merge |
| R-13 | **Attempt state bugs** (refresh, double submit, timer drift, revisit in forward-only mode) | Unfair or lost attempts | Server-side deadline, stored question order, idempotent submit, per-request pointer check |
| R-14 | **Anti-cheat limits:** browser cannot identify which app was opened; can be bypassed | False sense of security, disputes | State the limits in the UI and report; log only what is observable; Admin can review and reset; treat as deterrent |
| R-15 | **False positives** (notification pop-ups, accidental blur) auto-submit a test | Student harm, complaints | Rules notice before start; configurable strikes; Admin review and reset; short grace for blur under 1 second (configurable) |
| R-16 | **Razorpay/offline demo:** no internet in viva, key leak, unverified payments | Demo failure, security issue | Test keys in env only; server-side signature verification; a mock-gateway mode for offline demos; never trust the client success callback |
| R-17 | **Payment and seat inconsistency** (paid but no seat, or seat held forever) | Money/seat mismatch | Pending-booking hold with expiry job, idempotent verification, reconciliation view for Admin |
| R-18 | **Viva scope risk:** explaining a much larger codebase | Weak viva | Tier 3 is optional; build in small commits; rehearse the test engine and payment flow |

---

## 13. Success Metrics

### Technical KPIs
- 100% of Tier 1 features work end to end locally with no crashes; Gate A recorded in Git.
- 0 overbookings and 0 duplicate bookings under concurrent-booking tests.
- 100% of protected routes reject unauthorised roles.
- DB and Admin created from code on a clean machine.
- One unique Git commit message per phase.
- *(Tier 3)* 0 successful revisits in forward-only mode in automated tests; 100% of attempts auto-submit at the deadline; every violation event reaches the Admin report; 100% of payments verified by signature before a booking is confirmed; no regressions in Tier 1/2 suites.

### Business KPIs
- Admin configures a full examination cycle in under 10 minutes.
- 100% of bookings and evaluations traceable in history.
- All submission artefacts delivered.
- *(Tier 3)* Admin can see who left a test, when, and for how long within two clicks; every fee payment reconciles with a booking.

### User Adoption KPIs
- Student books a slot in under 2 minutes; examiner creates a slot in under 1 minute and evaluates in under 3.
- *(Tier 3)* Student completes payment and booking in under 3 minutes in test mode; student understands the monitoring rules before starting (acknowledgement recorded).

---

## 14. Appendices

### 14.1 API Endpoint Summary (high level; exact payloads in the TDR)

| Area | Method | Path | Tier |
|---|---|---|---|
| Auth | GET/POST | `/register`, `/login`; GET `/logout` | 1 |
| Admin | GET/POST | `/admin/dashboard`, `/admin/courses`, `/admin/examinations`, `/admin/examinations/<id>/rubrics` | 1 |
| Admin | POST | `/admin/examiners/<id>/approve`, `/deactivate`; `/admin/bookings/<id>/reschedule` | 1 |
| Examiner | GET/POST | `/examiner/dashboard`, `/examiner/slots`, `/examiner/bookings/<id>/evaluate` | 1 |
| Student | GET/POST | `/student/dashboard`, `/student/examinations`, `/student/slots/<id>/book`, `/student/bookings/<id>/cancel` | 1 |
| JSON API | GET/POST/PUT/DELETE | `/api/v1/examinations`, `/api/v1/slots`, `/api/v1/bookings`, `/api/v1/examiners`, `/api/v1/students` | 2 |
| Tests | GET/POST | `/admin/tests`, `/examiner/tests`, `/student/tests/<id>/start` | 3 |
| Attempts | GET/POST | `/student/attempts/<id>/questions/<n>`, `/student/attempts/<id>/submit` | 3 |
| Proctoring | POST | `/student/attempts/<id>/events` | 3 |
| Admin reports | GET | `/admin/proctoring/reports` | 3 |
| Payments | POST | `/student/payments/orders`, `/student/payments/verify` | 3 |

### 14.2 Notification Templates
- **Examiner Approved**, **Booking Confirmed**, **Booking Cancelled / Rescheduled**, **Results Published** (Tier 2 email).
- *(Tier 3)* **Test Auto-Submitted (violation)**: sent to the student and shown in the Admin report. **Payment Received / Refund Initiated**: sent to the student.
- In-app flash messages (Tier 1): booking success, slot full, booking closed, duplicate booking, access denied. *(Tier 3)* "Payment pending", "Test window closed", "Leaving this page will submit your test".

### 14.3 Glossary
- **Tier 1/2/3:** Primary / Secondary / Tertiary scope.
- **Gate A / Gate B:** Checkpoints that must pass before Tier 2 / Tier 3 work may begin.
- **Delivery mode:** How a test selects, orders and navigates questions.
- **Forward-only:** A mode where answered questions cannot be revisited.
- **Attempt:** One student's run of one test, with a stored question set.
- **Violation event:** A recorded sign that the student left the test page or used a blocked action.
- **Seat hold:** A temporary reservation while the student pays.
- **EMP / MAD-I / Viva / Rubric / Booking / Slot:** as in the course statement.

### Assumptions and Notes
1. Tier 3 features are not in the course statement. They are team-added extras; the course's own requirement list is unchanged.
2. The "two types of test" request was modelled as three delivery modes (standard, random forward-only, random revisitable). If a different split was intended, only section 5.8 and the `delivery_mode` enum change.
3. "Detect which app was opened and report it" is not possible from a web page; the design reports page-leave events with timestamps and duration instead.
4. The report page limit (up to 5 vs "3-5") and video length (5-10 vs "3-10") differ in the source documents; the stricter values are assumed.
5. Rubric attributes were partly visible; the remainder is inferred.
