"""
FILE PURPOSE: ADM-11 and ADM-12 student list and detail (read-only plus temporary password).
DEPENDS ON: admin_bp, admin_required, app/forms/common.py, app/forms/admin_actions.py, app/services/search_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/students (q filter by name, email, roll number or id; pagination) and GET /admin/students/<id> (detail, 404 if the user is not a student).
2. Detail shows profile data, all bookings of the student with status badges (any status), examination history and the audit history; empty states say "No bookings yet." (bookings appear from P5 on).
3. The temporary-password form posts to /admin/users/<id>/temporary-password (route lives in examiners.py).
4. Read-only otherwise: Admin cannot edit or delete students in this milestone.
DEBUGGING:
# print(f"[DEBUG] students list q={q!r} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Searching by roll number finds the student; paging works with 25 students.
- Detail of an examiner id returns 404.
- Detail lists cancelled and completed bookings too.
"""
