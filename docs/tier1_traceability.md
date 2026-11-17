# Tier 1 Traceability Matrix

| ID | Requirement (PDR 3.2) | Phase | Automated Test File | Demo Script Act | Verified |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T1-01 | Programmatic SQLite creation & schema constraints | P1 | `tests/unit/test_models_courses_exams.py` | Act 5 | yes |
| T1-02 | Pre-seeded Admin without UI registration | P1, P2 | `tests/integration/test_auth_register_login.py` | Act 1 | yes |
| T1-03 | Examiner & Student registration and login | P2 | `tests/integration/test_auth_register_login.py` | Act 2, Act 3 | yes |
| T1-04 | Examiner approval gate & deactivation check | P2, P3 | `tests/integration/test_rbac_access.py` | Act 1, Act 2 | yes |
| T1-05 | Admin dashboard six totals | P3 | `tests/integration/test_admin_access_control.py` | Act 1 | yes |
| T1-06 | Course, Examination & Rubric CRUD (weightage=100) | P3 | `tests/integration/test_admin_courses_exams_rubrics.py` | Act 1 | yes |
| T1-07 | Examiner add, approve, deactivate & assignment | P3 | `tests/integration/test_admin_examiners_students_slots.py` | Act 1 | yes |
| T1-08 | Timeline windows & open/close creation/booking switches | P3 | `tests/unit/test_windows.py` | Act 1 | yes |
| T1-09 | Admin search by name or ID across entities | P3 | `tests/integration/test_admin_search_history_flow.py` | Act 1 | yes |
| T1-10 | Admin view all slots, bookings & historical audit data | P3, P6 | `tests/integration/test_role_scoped_visibility.py` | Act 4 | yes |
| T1-11 | Admin reschedule booking & change slot examiner | P3, P6 | `tests/unit/test_booking_engine_admin_ops.py` | Act 4 | yes |
| T1-12 | Examiner dashboard counts & assigned examinations | P4 | `tests/integration/test_examiner_access_ownership.py` | Act 2 | yes |
| T1-13 | Examiner slot create/update/remove with window & overlap rules | P4 | `tests/unit/test_slot_service.py` | Act 2 | yes |
| T1-14 | Examiner view booked students & cancel slot with reason | P4, P6 | `tests/integration/test_admin_booking_actions_and_tracking.py` | Act 2 | yes |
| T1-15 | Rubric evaluation (draft, submit, publish) within max marks | P4, P6 | `tests/unit/test_evaluation_service.py` | Act 2 | yes |
| T1-16 | Student dashboard, search/filter & examination discovery | P5 | `tests/integration/test_student_browse_book_cancel.py` | Act 3 | yes |
| T1-17 | Student slot booking, capacity enforcement & auto-full status | P5, P6 | `tests/unit/test_booking_engine_concurrency.py` | Act 3, Act 5 | yes |
| T1-18 | Duplicate booking prevention & cancel before deadline | P5 | `tests/unit/test_booking_engine_rules.py` | Act 3 | yes |
| T1-19 | Student schedule, history timeline & published results view | P5, P6 | `tests/unit/test_history_service.py` | Act 3 | yes |
| T1-20 | Status tracking jobs (`sync-exam-status`) & soft-delete purge | P6 | `tests/unit/test_status_jobs_and_maintenance.py` | Act 4 | yes |
