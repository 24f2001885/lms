# MASTER PROJECT BLUEPRINT: Examination Management Portal (EMP), v2
### Docker + Git Milestone Workflow

*Inputs: PDR v2, TDR v2, UI/UX Design Plan v2. Read side by side with the Design Plan: screen IDs (ADM-xx, EXM-xx, STU-xx, PUB-xx) appear in the milestone map.*

**The one rule that shapes this whole document:** Tier 3 (online tests, anti-cheat, Razorpay) is built **absolutely last**. It cannot start until every Tier 1 and Tier 2 phase is finished, tested, merged and tagged. The Git workflow enforces this with tags and a gate script.

---

## 1. Unified Directory Structure

Final state of the repository. Folders marked **[T2]** are added during Tier 2; folders marked **[T3]** are created only after Gate B. Nothing built later needs a new top-level folder.

```
emp/
├── app/
│   ├── __init__.py                  # create_app(), blueprint registration, feature-flag checks
│   ├── config.py                    # DevConfig, TestConfig, ProdConfig
│   ├── extensions.py                # db, csrf, [T2] mail, login_manager
│   ├── cli.py                       # flask init-db, flask jobs <name>
│   ├── errors.py                    # BookingError, WindowError, PermissionDenied ... + handlers
│   ├── logging_config.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── examiner_profile.py
│   │   ├── student_profile.py
│   │   ├── course.py
│   │   ├── examination.py
│   │   ├── rubric.py
│   │   ├── examination_examiner.py
│   │   ├── slot.py
│   │   ├── booking.py
│   │   ├── evaluation.py            # Evaluation + EvaluationScore
│   │   ├── audit_log.py
│   │   ├── email_log.py             # [T2]
│   │   └── tier3/                   # [T3] imported only when a T3 flag is on
│   │       ├── __init__.py
│   │       ├── fee.py               # ExaminationFee
│   │       ├── test.py              # Test, TestQuestion, TestOption
│   │       ├── attempt.py           # TestAttempt, AttemptQuestion, AttemptAnswer
│   │       ├── proctoring_event.py
│   │       ├── payment.py           # Payment, SeatHold
│   │       └── refund.py
│   ├── blueprints/
│   │   ├── auth/                    # login, register, logout, change password, pending page
│   │   ├── admin/                   # dashboard, courses, examinations, rubrics, examiners,
│   │   │                            #   students, slots, bookings, search, history
│   │   ├── examiner/                # dashboard, slots, evaluations, profile
│   │   ├── student/                 # dashboard, examinations, bookings, history, results
│   │   ├── api_v1/                  # [T2] JSON API + chart data endpoints
│   │   └── tier3/                   # [T3]
│   │       ├── tests/               # test + question authoring (admin/examiner)
│   │       ├── attempts/            # student test taking
│   │       ├── proctoring/          # events endpoint + admin reports
│   │       └── payments/            # orders, verify, admin payments
│   ├── services/
│   │   ├── booking_engine.py        # book, cancel, reschedule, change examiner
│   │   ├── windows.py               # now_utc(), window checks
│   │   ├── exam_status.py           # status transitions
│   │   ├── evaluation_service.py
│   │   ├── search_service.py
│   │   ├── audit_service.py
│   │   ├── hooks.py                 # pre_booking_hooks, post_cancel_hooks (empty lists in T1)
│   │   ├── mailer.py                # [T2]
│   │   ├── scorecard.py             # [T2]
│   │   ├── chart_data.py            # [T2]
│   │   └── tier3/                   # [T3]
│   │       ├── test_engine.py       # start, get_question, save_answer, finalize
│   │       ├── proctor_policy.py    # grace period, strike counting
│   │       ├── payment_service.py   # orders, verify, holds, refunds
│   │       ├── gateway_razorpay.py
│   │       └── gateway_mock.py
│   ├── forms/                       # WTForms: auth, course, examination, rubric, slot,
│   │                                #   evaluation, profile, [T3] test, question, fee
│   ├── security/
│   │   ├── decorators.py            # login_required, role_required, approved_examiner_required
│   │   ├── auth_helpers.py
│   │   └── rate_limit.py            # [T2]
│   ├── templates/
│   │   ├── base.html
│   │   ├── macros/                  # forms.html, status_badge.html, pagination.html
│   │   ├── errors/                  # 403.html 404.html 500.html
│   │   ├── auth/                    # login, register, pending_approval, inactive, change_password
│   │   ├── admin/                   # base_admin + ADM-xx screens
│   │   ├── examiner/                # base_examiner + EXM-xx screens
│   │   ├── student/                 # base_student + STU-xx screens
│   │   ├── emails/                  # [T2] text templates
│   │   └── tier3/                   # [T3] tests/, attempts/ (focus layout), payments/, proctoring/
│   └── static/
│       ├── vendor/
│       │   ├── bootstrap/           # css + js bundle (offline)
│       │   ├── bootstrap-icons/
│       │   └── chartjs/             # [T2]
│       ├── css/app.css              # variable overrides, custom badges
│       └── js/
│           ├── validation.js        # [T2]
│           ├── charts.js            # [T2]
│           └── tier3/               # [T3]
│               ├── proctor.js
│               ├── attempt_timer.js
│               └── razorpay_checkout.js
├── instance/                        # emp.db (git-ignored)
├── logs/                            # emp.log (git-ignored)
├── migrations/                      # optional Flask-Migrate (batch mode)
├── scripts/
│   ├── check_gate.sh                # blocks tier3/* work unless tag tier2-complete exists
│   ├── seed_demo_data.py            # optional demo data for the viva
│   └── vendor_wheels.sh             # downloads wheels for offline Docker builds
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── e2e/                         # Playwright
│   └── tier3/                       # [T3] only
├── docs/
│   ├── PDR.md  TDR.md  UIUX_Design_Plan.md  Master_Blueprint.md
│   ├── er_diagram.png
│   ├── ai_llm_declaration.md
│   └── report/                      # final report (up to 5 pages) and video link
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml               # services: app; profile "test"
├── .dockerignore
├── .env.example
├── .gitignore
├── Makefile                         # make run, test-core, test-tier3, lint
├── pyproject.toml                   # ruff + black config
├── requirements.txt                 # Tier 1 deps
├── requirements-tier2.txt           # [T2] added deps
├── requirements-tier3.txt           # [T3] razorpay
├── requirements-dev.txt             # pytest, ruff, black, playwright, aiosmtpd
└── README.md
```

---

## 2. Git + Docker Workflow

### 2.1 Branches
| Branch | Purpose |
|---|---|
| `main` | Always green and runnable. Receives one merge per finished phase. |
| `phase/pN-<slug>` | Work for Tier 1 and Tier 2 phase N (example: `phase/p5-student-booking`). Cut from `main`. |
| `tier3/pN-<slug>` | Work for Tier 3 phases P13 to P17. **May only be created from the tag `tier2-complete`.** |
| `hotfix/<slug>` | Small fixes to `main`; must add or fix a test. |

Never commit directly to `main`. Branch names are lowercase with hyphens.

### 2.2 Commits and tags
- Work-in-progress commits on a phase branch are free-form but must start with `wip:`.
- When a phase passes its checks, merge into `main` with a squash so the history has **exactly one commit per phase** carrying that phase's unique message (the course requires a unique message per milestone). Then push.
- Message format: `Milestone-<N> EMP-<Short-Name>`. P0 is fixed by the course as `Milestone-0 EMP-MAD-1`; the final submission commit is `Milestone-EMP Final-Submission`. Never reuse a message.
- Tags: `p0-done` ... `p17-done` after each merge; **`tier1-complete`** after P6; **`tier2-complete`** after P12; `tier3-complete` after P17.
- Push after every phase merge so the course collaborator account (`MADI-cs2003`) can track progress.

### 2.3 Gates (hard stops)
**Gate A (before any Tier 2 work):**
- P0 to P6 are merged and tagged.
- `make test-core` is green (unit, integration, e2e).
- Booking-engine concurrency test passes (20 threads on a 5-seat slot yields exactly 5 bookings).
- Every Tier 1 requirement in PDR section 3.2 is demonstrable; the demo script runs clean for all three roles.
- Tag `tier1-complete` created.

**Gate B (before any Tier 3 work):**
- P7 to P12 are merged and tagged; Gate A still holds.
- `make test-core` is green including Tier 2 tests.
- The **Tier 1+2 submission package is ready**: `submission_core.zip`, report draft, demo video link, AI/LLM declaration.
- No `ENABLE_*` flag is set in `.env.example` defaults.
- Tag `tier2-complete` created. `scripts/check_gate.sh` (run by CI and by `make tier3-branch`) refuses to create or build any `tier3/*` branch if this tag is missing.

**Gate C (before Tier 3 ships in the submission):** P17 regression passes (all Tier 1, Tier 2 and Tier 3 suites), flags verified on and off, and the viva demo script rehearsed. If this fails, Tier 3 ships disabled or is left out.

### 2.4 Tests relative to commits
1. Write the test with the feature (service tests first for engines).
2. `make lint test-core` must pass locally and in Docker before the phase branch is squash-merged.
3. A phase is "done" only when its acceptance checks in section 3 pass. Failing tests block the merge; they are never skipped.
4. Tier 3 phases additionally run `make test-core` first (regression) and then `make test-tier3`.

### 2.5 Offline Docker testing, in practice for this stack
- The stack has one container because SQLite is a file. No external services are needed for tests.
- `scripts/vendor_wheels.sh` downloads wheels once (`pip download -r requirements*.txt -d wheels/`); the Dockerfile installs with `pip install --no-index --find-links=wheels/` so builds work without internet.
- The `test` compose profile runs with `network_mode: none`, a throw-away SQLite file in a tmpfs volume, `MAIL_SUPPRESS_SEND=true`, `RAZORPAY_MODE=mock`, and Playwright browsers preinstalled in the image.
- Commands: `docker compose --profile test run --rm test make test-core` and (after Gate B) `... make test-tier3`.
- Local virtualenv runs are equivalent and are the primary development path; Docker proves the project is reproducible.

### 2.6 Definition of Done for every phase
Code merged to `main`; tests added and green; README and `.env.example` updated; screens match the Design Plan IDs; a short "known issues" entry in the README (the course asks to log issues and resolutions); phase tag pushed.

---

## 3. Milestone → Feature → Commit Map

**How this map relates to the P0 to P6 convention:** P0 to P6 are the course's seven Tier 1 milestones (M0 to M6) one-to-one. Because Tier 2 and Tier 3 exist, the same numbering continues: **P7 to P12 = Tier 2**, **P13 to P17 = Tier 3**. Seed scripts for the first pipeline pass cover P0 to P6; later passes cover P7 onwards. Later phases depend only on earlier ones.

### 3.1 Tier 1: Primary (mandatory course scope)

| Phase | Course milestone | Features delivered | Depends on | Target goal / acceptance | Commit message |
|---|---|---|---|---|---|
| **P0** | M0 GitHub Repository Setup (due **17/11/2026**) | Private repo, `README.md`, `.gitignore`, directory skeleton, `requirements.txt`, `.env.example`, Dockerfile and compose, `Makefile`, `scripts/check_gate.sh`; add collaborator `MADI-cs2003` | none | Repo cloneable; app skeleton runs `flask run` showing a placeholder page; collaborator invited | `Milestone-0 EMP-MAD-1` |
| **P1** | M1 Database Models & Schema | `create_app`, config, extensions, all Tier 1 models and relationships, DB constraints and partial indexes, SQLite pragmas, `flask init-db`, idempotent Admin seed | P0 | DB created from code on a clean machine; constraints reject bad data (tests); Admin exists after init | `Milestone-1 EMP-Database-Models` |
| **P2** | M2 Authentication & Role-Based Access | Register/login/logout, hashing, CSRF, `role_required`, examiner pending flow, role redirects, error pages, change password. Screens PUB-01 to PUB-07 | P1 | Student and examiner can register; examiner blocked until approved; wrong-role URLs return 403; Admin cannot be registered | `Milestone-2 EMP-Authentication-RBAC` |
| **P3** | M3 Admin Dashboard & Examination Management | ADM-01 to ADM-18: totals, course/examination/rubric CRUD, examiner assignment and approve/deactivate, timeline switches, search, history, slot examiner change; `windows.py`, `exam_status.py`, audit logging | P2 | Admin completes the setup flow 4.4; weightages total 100; all listed Admin capabilities work | `Milestone-3 EMP-Admin-Dashboard-Exams` |
| **P4** | M4 Examiner Dashboard & Slot Management | EXM-01 to EXM-09: dashboard counts, slot create/update/delete with window rules and overlap check, booked students, rubric evaluation (draft, submit, publish), ownership checks | P3 | Slots only inside the creation window and editable only before booking starts; examiner cannot touch others' slots or students | `Milestone-4 EMP-Examiner-Slots-Evaluation` |
| **P5** | M5 Student Dashboard & Slot Booking | STU-01 to STU-10: dashboard, search/filter, slot list, `booking_engine.book_slot` and `cancel`, My Bookings, schedule, history, results, profile; `hooks.py` with empty extension lists | P4 | Student completes flow 4.2; booking blocked when closed, full or duplicate; cancel before deadline frees the seat | `Milestone-5 EMP-Student-Booking` |
| **P6** | M6 Booking History & Evaluation Tracking | Engine hardening (`BEGIN IMMEDIATE`, CHECK and unique-index fallbacks), reschedule and change-examiner flows, auto-close at capacity, status tracking jobs (`sync-exam-status`), complete history views, evaluation records and role-scoped visibility | P5 | Concurrency test: exactly capacity bookings; reschedule keeps counts correct; students see only their own data; **Gate A passes** | `Milestone-6 EMP-Booking-History-Tracking` |

**GATE A → tag `tier1-complete`**

### 3.2 Tier 2: Secondary (course recommended/optional). Starts only after Gate A.

| Phase | Course milestone | Features delivered | Depends on | Target goal / acceptance | Commit message |
|---|---|---|---|---|---|
| **P7** | API Integration | `api_v1` blueprint: examinations, examiners, students, slots, bookings with GET/POST/PUT/DELETE; consistent error shape; pagination; API reference page PUB-08 | P6 | Contract tests pass; role scoping identical to HTML routes; at least 4 HTTP methods | `Milestone-7 EMP-API-Integration` |
| **P8** | Charts & Visualization | `chart_data.py`, chart endpoints, Chart.js vendored; ADM-19, EXM-10, STU-11 and dashboard widgets | P7 | Charts show admin (exams, bookings, completion, workload), examiner (students evaluated, participants) and student (history, trends, results) data | `Milestone-8 EMP-Charts-Visualization` |
| **P9** | Frontend & Backend Validation | HTML5 attributes, `validation.js`, server validators for dates, timelines, capacity, rubric and marks limits, duplicate bookings | P6 | Invalid input rejected on both client and server with clear messages; server rejects even when JS is disabled | `Milestone-9 EMP-Validation` |
| **P10** | Responsive UI & Styling | Bootstrap polish, breakpoints per Design Plan section 8, off-canvas Admin sidebar, card-style tables on phones, accessibility pass | P9 | Screens usable at 375, 768 and 1280 px; contrast and keyboard checks pass | `Milestone-10 EMP-Responsive-UI` |
| **P11** | Flask-Login Integration & Security | Replace session helpers with Flask-Login, same decorators, session protection, login rate limiting, idle timeout | P6 | All RBAC tests still pass; session fixation test passes; lockout works | `Milestone-11 EMP-Flask-Login-Security` |
| **P12** | Scorecard & Email Notifications *(added beyond the course's five enhancements)* | `email_log` model, `mailer.py`, templates, scorecard PDF, `retry-failed-emails` job | P7, P9 | Emails recorded in `email_logs`; PDF downloads for published results; email failure never blocks bookings | `Milestone-12 EMP-Scorecard-Email` |

**GATE B → tag `tier2-complete` (Tier 1+2 submission package ready)**

*Course "Final Submission" can be executed here as **Final-A** (flags off): ZIP, report up to 5 pages, demo video, AI declaration, commit `Milestone-EMP Final-Submission`.*

### 3.3 Tier 3: Tertiary (team-added extras). Absolutely last. Starts only after Gate B.

Every Tier 3 phase: branch `tier3/pN-...` from tag `tier2-complete` (or from the previous Tier 3 phase on `main` after merge), flags default off, regression `make test-core` green before merge.

| Phase | Feature set | Features delivered | Depends on | Target goal / acceptance | Commit message |
|---|---|---|---|---|---|
| **P13** | T1 Test Engine Foundation | `requirements-tier3.txt`, flags in config, T3 model modules (tests, questions, options, attempts), `ExaminationFee` model, test authoring UIs ADM-20 to ADM-24, EXM-11 to EXM-12, question editor, publish rules | Gate B | Tests and questions can be authored and published; flags off hides all T3 UI; Tier 1/2 suites unchanged and green | `Milestone-13 EMP-T3-Test-Foundation` |
| **P14** | T2 Test Delivery Modes | `test_engine.py` (start, get_question, save_answer, finalize), three modes, stored per-student order, server deadline, timer JS, scoring, publish modes, `finalize-expired-attempts` job, screens STU-12 to STU-14, STU-16, STU-18, STU-19, then STU-15 | P13 | Refresh returns same questions; forward-only rejects revisit and edited URLs (409); revisitable allows changes; timeout auto-submits; score computed once and idempotently | `Milestone-14 EMP-T3-Test-Delivery-Modes` |
| **P15** | T3 Anti-Cheat & Violation Reports | `proctor.js`, `proctor_policy.py`, events endpoint, strike handling and auto-submit, warning banner STU-13 and STU-17, Admin reports ADM-25 to ADM-27, CSV export, attempt reset with audit, retention job | P14 | Tab switch (emulated) triggers auto-submit at the limit; grace period honoured; events visible in the Admin timeline; limits of detection stated on screen | `Milestone-15 EMP-T3-AntiCheat-Reports` |
| **P16** | T4 Razorpay Fee Payments | `payment_service.py`, gateways (mock and Razorpay test mode), `payments`, `seat_holds`, `refunds`, fee setup ADM-29, payments ADM-28, student screens STU-20 to STU-23, hooks registered (`payment_required`, refund on cancel), `expire-seat-holds` and `reconcile-payments` jobs | P15 (and P5 hooks) | Valid signature confirms a booking; invalid signature rejected; hold expiry releases seat; late payment auto-refunded; free exams unaffected | `Milestone-16 EMP-T3-Razorpay-Payments` |
| **P17** | T5 Tier 3 Integration & Hardening | End-to-end flows (pay → book → take test → violation → admin review), edge cases (refresh, double submit, expired hold during checkout), small load check (100 simultaneous test takers), flags on/off verification, docs, README updates, viva rehearsal script | P13 to P16 | **Gate C passes**: all suites green; Tier 1/2 behaviour identical with flags off | `Milestone-17 EMP-T3-Integration-Hardening` |

**Tag `tier3-complete`.** Only now may the submission be refreshed as **Final-B** (flags on, only if Gate C passed).

### 3.4 Final Submission

| Step | Description | Commit message |
|---|---|---|
| Final-A | Submission after Gate B with Tier 1+2 only: ZIP of code (single zip, folder structure per course), report up to 5 pages (student details, project details and approach, AI/LLM declaration, frameworks and libraries, ER diagram, API endpoints, video link), demo video 5 to 10 minutes on a Drive link with "anyone with the link" access, viva portal upload | `Milestone-EMP Final-Submission` |
| Final-B *(optional, only if Gate C passes before the freeze)* | Refreshed ZIP and report that mention Tier 3 | `Milestone-EMP Final-Submission-T3` |

### 3.5 Effort and timeline summary
| Tier | Phases | Estimated effort | Cumulative complexity |
|---|---|---|---|
| Tier 1 | P0 to P6 | about 37-41 days | 1.0x |
| Tier 2 | P7 to P12 | about 31-37 days | about 1.4x |
| Tier 3 | P13 to P17 | about 25-35 days | about 1.7-1.9x |

Key dates: problem statement frozen on or before 10/10/2026; **P0 due 17/11/2026**. Because Tier 3 is last, any schedule slip drops Tier 3 first and never touches the course requirements.

---

### Assumptions and flags
1. P7 to P12 and P13 to P17 extend the P0 to P6 convention; confirm the seed-script generator should handle phases beyond P6 in later passes.
2. P12 (scorecard and email) is listed in the course's recommended features without a milestone of its own; it is scheduled as its own Tier 2 phase here.
3. Commit-message wording beyond M0 and Final is chosen here; the course only requires uniqueness per milestone. Confirm the exact format your course team expects.
4. The squash-merge rule produces one commit per phase on `main`; if your course tracker needs every commit visible, merge without squashing and keep the unique message on the final commit of each phase instead.
