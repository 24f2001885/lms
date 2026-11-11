"""
FILE PURPOSE: ADM-04, ADM-05, ADM-06, ADM-08 examination list, create/edit, detail with timeline switches and the assigned-examiners panel.
DEPENDS ON: admin_bp, admin_required, app/forms/examination.py, app/forms/admin_actions.py, app/forms/common.py, app/services/catalog_service.py, app/services/windows.py, app/services/exam_status.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examinations (list; filters q, course_id, exam_type, status, show_deleted; pagination), GET /admin/examinations/new, POST /admin/examinations (create), GET /admin/examinations/<id> (detail), GET /admin/examinations/<id>/edit, POST /admin/examinations/<id>/update, POST /admin/examinations/<id>/delete, POST /admin/examinations/<id>/slot-creation/toggle, POST /admin/examinations/<id>/booking/toggle, POST /admin/examinations/<id>/examiners (assign), POST /admin/examinations/<id>/examiners/<examiner_id>/remove.
2. Detail page (ADM-06) loads: the examination with course, rubric summary (total weightage with an OK / needs-100 indicator), assigned examiners panel (ADM-08), slot count and booking counts, and windows.window_state(exam) to render the TWO timeline switches with their status text and the reason line. Call exam_status.refresh_status(exam) and commit before rendering so the badge is current (lazy status).
3. Toggle routes read the desired state from a hidden field "open" ("1" or "0") inside a ConfirmForm-style form, call catalog_service.toggle_*; errors (no_examiner_assigned, rubric_total_not_100) are flashed and the page redirects back to the detail view.
4. Assign form (AssignExaminerForm) is populated in the view with approved, active, not-yet-assigned examiners; if there are none show a muted message and a link to /admin/examiners?status=pending.
5. Datetimes shown with the localdt filter; forms pre-filled via populate_from.
6. Edit/delete errors are flashed with the AppError message; no rule logic in the route.
DEBUGGING:
# print(f"[DEBUG] exam {exam.id} status={exam.status} state={windows.window_state(exam)}")
OFFLINE DOCKER TEST CASES:
- Admin setup flow: create exam -> add rubric -> assign examiner -> open slot creation -> page shows "Open" with the dates; closing sets it back to "Closed".
- Opening booking with rubrics totalling 90 flashes the rubric_total_not_100 message and the switch stays closed.
- Detail page for a soft-deleted examination is reachable by Admin and shows a "Deleted" badge; the list hides it unless show_deleted is on.
- Remove-examiner refused while the examiner has a slot, with the examiner_has_slots message.
"""
