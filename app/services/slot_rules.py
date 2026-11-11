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

app/services/slot_rules.py - Slot validation and overlap detection engine.

Implements the half-open interval overlap check [start_at, end_at)
spanning all examinations assigned to an examiner.
"""

from datetime import datetime

from app.models.slot import ExaminationSlot


def has_overlap(
    examiner_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_slot_id: int | None = None,
) -> bool:
    """
    Return True if examiner already has a non-cancelled slot overlapping [start_at, end_at).
    Two slots overlap when: existing.start_at < end_at AND existing.end_at > start_at.
    Back-to-back slots (existing.end_at == start_at) do NOT overlap.
    """
    return find_overlapping(examiner_id, start_at, end_at, exclude_slot_id) is not None


def find_overlapping(
    examiner_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_slot_id: int | None = None,
) -> ExaminationSlot | None:
    """Return the first overlapping slot or None."""
    query = ExaminationSlot.query.filter(
        ExaminationSlot.examiner_id == examiner_id,
        ExaminationSlot.status != "cancelled",
        ExaminationSlot.start_at < end_at,
        ExaminationSlot.end_at > start_at,
    )
    if exclude_slot_id is not None:
        query = query.filter(ExaminationSlot.id != exclude_slot_id)

    return query.first()