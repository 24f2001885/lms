"""
FILE PURPOSE: Shared slot rule(s) used by Admin (P3 change examiner) and Examiner (P4 slot create/update) so the rule exists once.
DEPENDS ON: app/models/slot.py.
PROMPT FOR LLM IMPLEMENTATION:
1. has_overlap(examiner_id, start_at, end_at, exclude_slot_id=None) -> bool: True when the examiner already has a slot whose status is NOT "cancelled" that overlaps the half-open interval [start_at, end_at). Two slots overlap when existing.start_at < end_at AND existing.end_at > start_at; back-to-back slots (end == next start) do NOT overlap. The check spans ALL examinations of that examiner. exclude_slot_id removes the slot being edited from the comparison.
2. find_overlapping(examiner_id, start_at, end_at, exclude_slot_id=None) returns the first conflicting slot or None, so error messages can show its time.
3. Read-only queries; no commits; no flashing; no exceptions.
DEBUGGING:
# print(f"[DEBUG] overlap check examiner={examiner_id} {start_at}->{end_at} exclude={exclude_slot_id} conflict={conflict and conflict.id}")
OFFLINE DOCKER TEST CASES:
- 10:00-11:00 vs existing 10:30-11:30 overlaps; vs existing 11:00-12:00 does not; vs existing 09:00-10:00 does not.
- A cancelled slot never conflicts.
- exclude_slot_id lets a slot be moved within its own time span.
- Overlap is detected across two different examinations of the same examiner, but not between two different examiners.
"""
