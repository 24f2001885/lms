"""
FILE PURPOSE: ADM-13 slots overview and ADM-14 change slot examiner.
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py, app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/slots (filters examination_id, examiner_id, status, date_from, date_to; pagination; columns: examination, examiner, start, end, seats booked/capacity, status badge), GET /admin/slots/<id> (detail with the list of booked students), GET /admin/slots/<id>/examiner (change form) and POST /admin/slots/<id>/examiner (TDR 5.1).
2. Change form lists only eligible examiners (assigned, approved, active, not the current one). POST calls admin_service.change_slot_examiner; flash AppError messages (examiner_overlap, examiner_not_eligible, slot_not_changeable) or "Examiner changed."; redirect to the slot detail.
3. Reschedule and cancel controls are NOT here (ADM-16 and admin cancel arrive in P6).
DEBUGGING:
# print(f"[DEBUG] slot {slot.id} examiner {slot.examiner_id} -> {new_id}")
OFFLINE DOCKER TEST CASES:
- Filtering by status "full" shows only full slots; date filters use local dates converted to UTC.
- Changing to an unassigned examiner is impossible (not in the select) and a forged POST is refused with examiner_not_eligible.
- After a successful change the slot detail shows the new examiner and the audit history contains slot.examiner_change.
"""
