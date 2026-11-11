"""
FILE PURPOSE: Admin rules for people and slots: examiner approval lifecycle, temporary passwords, changing a slot's examiner, and the dashboard totals.
DEPENDS ON: app/models, app/services/slot_rules.py, app/services/audit_service.py, app/errors.py, werkzeug.security.
PROMPT FOR LLM IMPLEMENTATION:
1. dashboard_totals() returns a dict of six main numbers plus sub-numbers: courses (all), examinations (not soft-deleted), examiners (all examiner accounts; sub: pending_approval), students (all), slots (not cancelled), bookings (status booked or completed; sub: cancelled). Use COUNT queries only (no row loading).
2. Examiner lifecycle (each audits and commits once): approve_examiner(actor_id, user_id) pending or rejected -> approved, profile status active; reject_examiner(...) pending -> rejected; deactivate_user(...) sets users.is_active False and, for examiners, examiner_profiles.status "inactive" (an Admin cannot deactivate themselves: AppError "cannot_deactivate_self"); activate_user(...) reverses it. Only role examiner is approvable; calling approve on a student raises AppError("not_an_examiner").
3. create_examiner(actor_id, full_name, email, phone, department, designation, temporary_password): creates an APPROVED, active examiner with must_change_password True plus the profile row; email normalised lowercase and unique ("email_taken"). The temporary password is validated with validate_password_strength.
4. set_temporary_password(actor_id, user_id, new_password=None) works for examiners and students only (never for another admin): when new_password is None generate one with secrets.token_urlsafe(9); store the hash, set must_change_password True, audit "user.temp_password" WITHOUT the password, and RETURN the plain password once so the view can flash it a single time. Note in a comment: existing signed cookies stay valid until they expire (stateless sessions); accepted limitation, revisited in P11.
5. change_slot_examiner(actor_id, slot_id, new_examiner_id): slot status must be available or full (not cancelled or completed: "slot_not_changeable"); the new examiner must be assigned to the slot's examination (examination_examiners), approved and active ("examiner_not_eligible"); must differ from the current one; slot_rules.has_overlap must be False ("examiner_overlap" with the conflicting time in the message). Update slot.examiner_id, audit "slot.examiner_change" with {"from": old, "to": new}. Existing bookings and evaluations stay attached; evaluations.examiner_id keeps the examiner who actually evaluated (TDR 3.4). P6 moves this logic into booking_engine.change_examiner and leaves this function as a thin wrapper.
6. Every function raises AppError with stable codes; none flashes or redirects.
DEBUGGING:
# print(f"[DEBUG] admin_service {name} actor={actor_id} target={target_id}")
OFFLINE DOCKER TEST CASES:
- approve_examiner flips pending to approved; the examiner's next request reaches /examiner/dashboard (integration test).
- deactivate_user on the Admin's own id raises cannot_deactivate_self.
- create_examiner stores must_change_password True and the examiner can log in and is forced to /change-password.
- set_temporary_password returns a string of at least 12 characters, the stored hash verifies against it, and no audit row contains it.
- change_slot_examiner to an unassigned examiner raises examiner_not_eligible; to an examiner with an overlapping slot raises examiner_overlap; success keeps booked_count and bookings unchanged.
- dashboard_totals returns six integers matching hand-counted fixtures.
"""
