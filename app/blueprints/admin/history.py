"""
FILE PURPOSE: ADM-18 historical data view (PDR: Admin can view all historical data).
DEPENDS ON: admin_bp, admin_required, app/services/audit_service.py, app/models.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/history with query parameter tab = examinations | bookings | evaluations | audit (default examinations) plus filters (examination_id, student q, date range) and pagination.
2. Tabs: examinations (all, INCLUDING soft-deleted with a Deleted badge, with status and window dates); bookings (all statuses with booked_at, cancelled_at, cancelled_by, rescheduled_from); evaluations (status, total, examiner, submitted/published times); audit (action, entity, actor, time, details formatted from the JSON, newest first).
3. Read-only; no export in this milestone. Never display password hashes or temporary passwords (they are never stored in audit details anyway).
DEBUGGING:
# print(f"[DEBUG] history tab={tab} total={page.total}")
OFFLINE DOCKER TEST CASES:
- Each of the four tabs returns 200 for Admin and 403 for other roles.
- A soft-deleted examination appears on the examinations tab with a Deleted badge.
- Audit tab shows the course.create row written during the same test.
- An unknown tab value falls back to examinations.
"""
