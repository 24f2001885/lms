"""
FILE PURPOSE: ADM-15 bookings overview (read-only in P3).
DEPENDS ON: admin_bp, admin_required, app/forms/common.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/bookings (filters status, examination_id, student q, slot_id, date range; pagination; columns: booking id, student, examination, slot time, examiner, status badge, booked_at, cancelled_at) and GET /admin/bookings/<id> (detail: all fields, evaluation status if any, audit history for the booking).
2. Read-only: the reschedule and cancel buttons are added in P6. Leave a visible but empty "Actions" area only when P6 lands; do not render placeholders now.
3. Use eager loading (joinedload/selectinload) for student, slot, examination to avoid N+1 queries; cap per_page at 100.
DEBUGGING:
# print(f"[DEBUG] bookings list filters={filters} total={page.total}")
OFFLINE DOCKER TEST CASES:
- With 30 fixtures the list pages correctly and the status filter returns only matching rows.
- Booking detail of a missing id returns 404.
- The list view issues a bounded number of SQL queries (assert with a query counter: fewer than 8 for 20 rows).
"""
