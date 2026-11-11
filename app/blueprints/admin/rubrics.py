"""
FILE PURPOSE: ADM-07 rubric management for one examination.
DEPENDS ON: admin_bp, admin_required, app/forms/rubric.py, app/forms/common.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examinations/<id>/rubrics (list + add form + running total), POST /admin/examinations/<id>/rubrics (add), GET /admin/examinations/<id>/rubrics/<rid>/edit, POST /admin/examinations/<id>/rubrics/<rid>/update, POST /admin/examinations/<id>/rubrics/<rid>/delete.
2. The page shows a progress bar of the weightage total toward 100 (text "Total 90 of 100: add 10 more" or "Total 100: ready"), the sum of max scores with the informational warning when it differs from the examination's maximum marks, and a lock notice when rubric_locked applies (evaluations exist).
3. All rules come from catalog_service; flash AppError messages; a rubric id that does not belong to the examination in the URL is a 404.
DEBUGGING:
# print(f"[DEBUG] rubrics exam={exam_id} total={total} max_total={max_total}")
OFFLINE DOCKER TEST CASES:
- Adding criteria 60 and 40 shows "Total 100: ready"; adding another 10 is rejected with weightage_over_100.
- Duplicate criterion name shows the friendly message.
- After an evaluation exists the add/edit/delete forms are hidden and POSTs are refused.
- Mismatch between sum of max scores and max marks shows a warning but does not block anything.
"""
