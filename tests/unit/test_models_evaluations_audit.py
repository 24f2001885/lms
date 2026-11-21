import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AuditLog, Evaluation, EvaluationScore


def test_one_evaluation_per_booking(
    app, make_examination, make_examiner, make_student, make_slot, make_booking
):
    """Verify unique constraint on booking_id (only 1 evaluation per booking)."""
    exam = make_examination()
    examiner = make_examiner()
    student = make_student()
    slot = make_slot(exam, examiner)
    booking = make_booking(student, slot)

    ev1 = Evaluation(booking_id=booking.id, examiner_id=examiner.id, total_marks=85.0)
    db.session.add(ev1)
    db.session.commit()

    ev2 = Evaluation(booking_id=booking.id, examiner_id=examiner.id, total_marks=90.0)
    db.session.add(ev2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_scores_cascade_with_evaluation(
    app, make_examination, make_examiner, make_student, make_slot, make_booking, make_rubric
):
    """Verify evaluation deletion cascades and deletes child evaluation_scores."""
    exam = make_examination()
    examiner = make_examiner()
    student = make_student()
    slot = make_slot(exam, examiner)
    booking = make_booking(student, slot)
    rubric = make_rubric(exam)

    ev = Evaluation(booking_id=booking.id, examiner_id=examiner.id, total_marks=20.0)
    db.session.add(ev)
    db.session.flush()

    score = EvaluationScore(evaluation_id=ev.id, rubric_id=rubric.id, score=20.0)
    db.session.add(score)
    db.session.commit()

    score_id = score.id
    db.session.delete(ev)
    db.session.commit()

    # Score must be deleted automatically via cascade
    assert db.session.get(EvaluationScore, score_id) is None


def test_audit_log_details_dict(app):
    """Verify details_dict() safely handles valid, empty, and invalid JSON."""
    log1 = AuditLog(action="test.action", entity_type="booking", details='{"slot_id": 5}')
    assert log1.details_dict() == {"slot_id": 5}

    log2 = AuditLog(action="test.action", entity_type="booking", details=None)
    assert log2.details_dict() == {}

    log3 = AuditLog(action="test.action", entity_type="booking", details="invalid json")
    assert log3.details_dict() == {}
