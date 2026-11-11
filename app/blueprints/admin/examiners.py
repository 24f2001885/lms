"""
FILE PURPOSE: ADM-09 and ADM-10 examiner list and detail, approval lifecycle, creating examiners and setting temporary passwords (also for students).
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py, app/forms/common.py, app/services/admin_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Routes: GET /admin/examiners (filters status = pending/approved/inactive/rejected and q; pagination), GET /admin/examiners/<id> (detail), GET /admin/examiners/new and POST /admin/examiners (create approved examiner), POST /admin/examiners/<id>/approve, /reject, /deactivate, /activate, and POST /admin/users/<id>/temporary-password (works for examiners and students).
2. Filter semantics: pending = approval_status pending; approved = approved and is_active; inactive = is_active False; rejected = approval_status rejected.
3. Detail shows profile data, assigned examinations, number of slots and of booked students (counts only), the audit history of that user, and the action buttons that apply to the current state (Approve/Reject only when pending; Deactivate when active; Activate when inactive).
4. The temporary password is shown ONCE: store it in flash with category warning and a "copy now" text ("Temporary password for <name>: <password>. It will not be shown again.") and never log it.
5. Error messages from AppError are flashed; all POSTs are CSRF-protected forms.
DEBUGGING:
# print(f"[DEBUG] examiners {request.method} {request.path} target={user_id}")
OFFLINE DOCKER TEST CASES:
- Pending examiner appears under ?status=pending; Approve moves them to approved and the audit history shows the action.
- Deactivate then next request by that examiner lands on /account-inactive; Activate restores access.
- Temp password flash appears once and the user is forced to /change-password on next login.
- POST approve on a student id returns the not_an_examiner message and changes nothing.
"""
