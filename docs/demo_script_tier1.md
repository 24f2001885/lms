# Tier 1 Demo Script (10-Minute Viva Walkthrough)

## Prerequisites
1. Clone repository, create virtualenv, install `requirements.txt` and `requirements-dev.txt`.
2. Copy `.env.example` to `.env`, run `flask --app app init-db`, then `make demo-data`.
3. Start server: `flask --app app run --debug` and open `http://127.0.0.1:5000/login`.

| Role | Email | Password |
| :--- | :--- | :--- |
| Admin | From `.env` (`ADMIN_EMAIL`) | From `.env` (`ADMIN_INITIAL_PASSWORD`) |
| Examiner (Approved) | `examiner1@demo.local` | `Demo#12345` (`DEMO_PASSWORD`) |
| Examiner (Pending) | `examiner.pending@demo.local` | `Demo#12345` |
| Student | `student01@demo.local` | `Demo#12345` |

---

## Act 1: Admin Setup & Oversight (2.5 mins)
- **Goal:** Demonstrate pre-seeded admin login, dashboard totals, examiner approval, rubric validation, and search.
- **Steps:**
  1. Log in as Admin; complete first-login password prompt if shown.
  2. Review the 6 dashboard totals (`ADM-01`).
  3. Navigate to **Examiners** (`ADM-09`), filter by *Pending*, and approve `examiner.pending@demo.local`.
  4. Open **Examinations** -> *Practical - Databases* (`ADM-06`), show slot creation controls and rubric weightage sum = 100 (`ADM-07`).
  5. Use **Search** (`ADM-17`) to locate `student01` by name and by numeric ID.

## Act 2: Examiner Slot Management & Evaluation (2.5 mins)
- **Goal:** Demonstrate approval gate, slot creation window enforcement, and rubric grading.
- **Steps:**
  1. Log in as `examiner1@demo.local` (`EXM-01`).
  2. Open *Practical - Databases* and create a new slot (`EXM-05`) inside the active creation window.
  3. Open *Viva - Data Structures* (where booking is already open) and confirm slot editing/deletion is locked.
  4. Open **Evaluations** (`EXM-07`), select a booked student, enter rubric scores + remarks (`EXM-08`), save draft, submit, and publish.

## Act 3: Student Discovery, Booking & Results (2.5 mins)
- **Goal:** Demonstrate search/filter, capacity enforcement, duplicate protection, cancellation, and published results.
- **Steps:**
  1. Log in as `student01@demo.local` (`STU-01`).
  2. Browse **Examinations** (`STU-02`), open *Viva - Data Structures* (`STU-03`).
  3. Observe the *Full* slot badge and disabled button; book a seat on an *Available* slot (`STU-04`).
  4. Verify duplicate booking prevention on another slot of the same examination.
  5. Open **My Bookings** (`STU-05`), cancel before deadline to release the seat, and check **History** (`STU-08`).
  6. Open **Results** (`STU-09`) and view the published scorecard and feedback (`STU-10`).

## Act 4: Admin Conflict Resolution & History Timeline (1.5 mins)
- **Goal:** Demonstrate Admin reschedule, examiner reassignment, admin cancel with reason, and role-redacted timelines.
- **Steps:**
  1. As Admin, open an active booking (`ADM-15`) -> **Reschedule** (`ADM-16`) to another available slot of the same exam.
  2. Reassign a slot's examiner (`ADM-14`) and verify existing bookings remain intact.
  3. Cancel a booking with an audit reason and inspect the **History** timeline (noting that students see *"Cancelled by the administration"* without the internal reason).

## Act 5: Concurrency, Security & Code-First DB Proof (1.0 min)
- **Goal:** Prove zero overbooking under race conditions and RBAC protection.
- **Steps:**
  1. Run `pytest -m concurrency` in terminal (20 threads competing for 5 seats -> exact 5 bookings).
  2. Attempt to visit `/admin/dashboard` while logged in as a student -> `403 Forbidden`.

---

## Troubleshooting Quick Reference
| Symptom | Fix |
| :--- | :--- |
| Windows appear closed during live demo | Delete `instance/emp.db`, run `flask --app app init-db && make demo-data` |
| Port 5000 already in use | Run `flask --app app run --port 5001` |

## 12 Viva Rehearsal Questions
1. **How is overbooking prevented under concurrent requests?** `BEGIN IMMEDIATE` write locks (`app/extensions.py`) combined with guarded conditional `UPDATE` statements (`app/services/booking_engine.py`).
2. **How does SQLite enforce one active booking per student per exam?** Partial unique index `uq_bookings_active_student_exam` on `(student_id, examination_id) WHERE status IN ('booked', 'completed')`.
3. **Why are timestamps stored in naive UTC?** Consistent comparison across timezones via `windows.now_utc()`, formatted to `APP_TIMEZONE` only in Jinja templates (`localdt`).
4. **How are unapproved examiners blocked?** `approved_examiner_required` decorator checks `approval_status == 'approved'` and `is_active` on every request (`app/security/decorators.py`).
5. **Can an admin self-register?** No; `/register` strictly whitelists `student` and `examiner` roles; Admin is seeded idempotently via `flask init-db`.
6. **What happens when a slot reaches `max_capacity`?** `booking_engine.book_slot` atomically flips `slot.status` to `'full'`; cancelling a booking flips it back to `'available'`.
7. **Why do we soft-delete examinations?** To preserve historical booking and evaluation integrity; `maintenance.purge_soft_deleted` only purges exams older than 90 days with zero bookings.
8. **How is timeline data redacted for students?** `history_service.booking_timeline` strips admin cancellation reasons, slot IDs, and IP addresses when `viewer_role == 'student'`.
9. **Can an admin edit rubric scores?** No; `evaluation_service.admin_publish` only transitions `'submitted'` evaluations to `'published'`.
10. **What prevents an examiner from grading another examiner's student?** Ownership queries filter by `slot.examiner_id == g.user.id`, returning `404` otherwise.
11. **How are extension hooks designed for Tier 3?** `app/services/hooks.py` defines empty `pre_booking_hooks` and `post_cancel_hooks` lists so Tier 1/2 never import Tier 3 code.
12. **What verifies Gate A readiness?** `scripts/verify_gate_a.sh` audits tags, commit messages, test suites, concurrency, >=80% branch coverage, and traceability.
