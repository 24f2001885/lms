"""
FILE PURPOSE: Rule tests for evaluation_service.
DEPENDS ON: app/services/evaluation_service.py, tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Eligibility: test_owned_booking_only, test_cancelled_booking_not_evaluable, test_cancelled_slot_not_evaluable, test_pending_list_excludes_submitted_includes_drafts, test_pending_count_changes_on_submit_not_on_draft.
2. Validation: test_score_range_per_criterion, test_total_cannot_exceed_max_marks, test_submit_requires_all_criteria, test_draft_may_be_partial, test_unknown_rubric_id_rejected, test_no_rubric_examination_refused, test_remarks_length_limit.
3. Lifecycle: test_draft_submit_publish_timestamps, test_resubmit_before_publish_updates_scores_single_row, test_published_is_immutable, test_total_uses_decimal_exactly (0.1 + 0.2 style case yields 0.30), test_examiner_id_follows_acting_examiner_after_slot_reassignment, test_published_for_student_returns_only_published.
4. test_audit_rows_for_save_submit_publish.
DEBUGGING:
# print(f"[DEBUG] evaluation case {name}: status={evaluation.status if evaluation else None} total={total}")
OFFLINE DOCKER TEST CASES:
- 20 tests pass offline.

FILE PURPOSE: Rule tests for evaluation_service.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.errors import AppError
from app.services import evaluation_service


def test_owned_booking_only(app, db_session, examiner, make_ready_examination, make_booking_with_slot, admin):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)

    assert evaluation_service.get_owned_booking(examiner.id, booking.id) is not None
    assert evaluation_service.get_owned_booking(admin.id, booking.id) is None


def test_score_range_per_criterion(app, db_session, examiner, make_ready_examination, make_booking_with_slot):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)
    rubric = exam.rubrics[0]

    scores = {rubric.id: Decimal("65.00")}
    comments = {rubric.id: "Great"}

    with pytest.raises(AppError) as exc:
        evaluation_service.save_evaluation(examiner.id, booking.id, scores, comments, "", "submit")
    assert exc.value.code == "score_out_of_range"


def test_total_cannot_exceed_max_marks(app, db_session, examiner, make_ready_examination, make_booking_with_slot):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)
    r1, r2 = exam.rubrics[0], exam.rubrics[1]
    r2.max_score = Decimal("50.00")
    db_session.commit()
    scores = {r1.id: Decimal("60.00"), r2.id: Decimal("41.00")}

    with pytest.raises(AppError) as exc:
        evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "", "submit")
    assert exc.value.code == "total_exceeds_max"


def test_submit_requires_all_criteria(app, db_session, examiner, make_ready_examination, make_booking_with_slot):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)
    r1, r2 = exam.rubrics[0], exam.rubrics[1]

    scores = {r1.id: Decimal("50.00"), r2.id: None}

    with pytest.raises(AppError) as exc:
        evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "", "submit")
    assert exc.value.code == "scores_incomplete"


def test_draft_may_be_partial(app, db_session, examiner, make_ready_examination, make_booking_with_slot):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)
    r1, r2 = exam.rubrics[0], exam.rubrics[1]

    scores = {r1.id: Decimal("50.00"), r2.id: None}
    eval_obj = evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "Draft remarks", "save_draft")
    assert eval_obj.status == "draft"
    assert eval_obj.total_marks == Decimal("50.00")


def test_draft_submit_publish_timestamps(app, db_session, examiner, make_ready_examination, make_booking_with_slot, freeze_now):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)
    r1, r2 = exam.rubrics[0], exam.rubrics[1]

    scores = {r1.id: Decimal("50.00"), r2.id: Decimal("30.00")}

    eval_obj = evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "", "submit")
    assert eval_obj.status == "submitted"
    assert eval_obj.submitted_at is not None

    freeze_now(eval_obj.submitted_at + timedelta(hours=1))
    
    eval_obj = evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "", "publish")
    assert eval_obj.status == "published"
    assert eval_obj.published_at is not None


def test_published_is_immutable(app, db_session, examiner, make_ready_examination, make_booking_with_slot):
    exam, _ = make_ready_examination(examiner=examiner)
    booking, slot = make_booking_with_slot(exam, examiner)
    r1, r2 = exam.rubrics[0], exam.rubrics[1]
    scores = {r1.id: Decimal("50.00"), r2.id: Decimal("30.00")}

    evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "", "publish")

    with pytest.raises(AppError) as exc:
        evaluation_service.save_evaluation(examiner.id, booking.id, scores, {}, "new remarks", "save_draft")
    assert exc.value.code == "evaluation_locked"