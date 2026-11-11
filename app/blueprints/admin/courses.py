"""
FILE PURPOSE: ADM-02 and ADM-03 course list, create, edit, delete.
DEPENDS ON: admin_bp, admin_required, app/forms/course.py, app/forms/common.py, app/services/catalog_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes (TDR 5.1): GET /admin/courses (list; filters q and status from query string; pagination), GET /admin/courses/new (empty form), POST /admin/courses (create), GET /admin/courses/<id>/edit, POST /admin/courses/<id>/update, POST /admin/courses/<id>/delete. Unknown id -> 404.
2. Each POST validates the form (or ConfirmForm for delete), calls catalog_service, flashes success ("Course created.") or the AppError message (category danger) and redirects (post/redirect/get). On form errors re-render the form with status 200.
3. Delete is offered as a danger button that opens a confirm modal (macro in macros/modals.html); the list shows an "Examinations" count column.
4. Pass actor_id=g.user.id to every service call. No rule logic in this file.
DEBUGGING:
# print(f"[DEBUG] courses {request.method} {request.path} user={g.user.id}")
OFFLINE DOCKER TEST CASES:
- Create, edit and delete a course through the client; each step flashes the right message.
- Deleting a course with an examination flashes "Set it to inactive instead." and the course remains.
- Duplicate code shows "A course with this code already exists." on the form.
- Non-admin POSTs are rejected with 403 and change nothing.
"""
