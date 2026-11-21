"""
tests/unit/test_audit_search_slot_rules.py - Unit tests for audit_service, search_service, slot_rules.
"""

from datetime import datetime

import pytest

from app.extensions import db
from app.models.audit_log import AuditLog
from app.services import audit_service, search_service, slot_rules


def test_log_action_not_committed_until_caller_commits(app):
    audit_service.log_action(actor_id=1, action="test.stage", entity_type="test")
    db.session.rollback()
    assert AuditLog.query.filter_by(action="test.stage").first() is None


def test_details_json_roundtrip_with_datetime(app, make_admin):
    admin = make_admin()
    dt_val = datetime(2030, 1, 1, 12, 0)
    audit_service.log_action(
        actor_id=admin.id, action="test.dt", entity_type="test", details={"time": dt_val}
    )
    db.session.commit()

    log = AuditLog.query.filter_by(action="test.dt").first()
    assert log is not None
    assert "2030-01-01" in log.details


def test_student_search_case_insensitive(app, make_student):
    s = make_student(full_name="Diana Prince", email="diana@hero.test")
    res = search_service.search("student", "diana")
    assert res is not None
    assert s in res.items


def test_search_by_numeric_id_first(app, make_student):
    s1 = make_student()
    res = search_service.search("student", str(s1.id))
    assert res is not None
    assert res.items[0].id == s1.id


def test_like_wildcards_escaped(app, make_student):
    make_student(full_name="Student 100%")
    make_student(full_name="Student Regular")

    res = search_service.search("student", "100%")
    assert res is not None
    # Must only match the exact literal 100%, not all rows
    assert res.total == 1


def test_invalid_kind_raises(app):
    with pytest.raises(ValueError):
        search_service.search("invoice", "any")


def test_empty_query_returns_none(app):
    assert search_service.search("student", "") is None
    assert search_service.search("student", "   ") is None


def test_slot_overlap_detected(app, make_examination, make_examiner, make_slot):
    exam = make_examination()
    examiner = make_examiner()

    make_slot(
        exam, examiner, start_at=datetime(2030, 1, 15, 10, 0), end_at=datetime(2030, 1, 15, 11, 0)
    )

    # 10:30 - 11:30 overlaps
    assert (
        slot_rules.has_overlap(
            examiner.id, datetime(2030, 1, 15, 10, 30), datetime(2030, 1, 15, 11, 30)
        )
        is True
    )

    # 11:00 - 12:00 back-to-back does NOT overlap
    assert (
        slot_rules.has_overlap(
            examiner.id, datetime(2030, 1, 15, 11, 0), datetime(2030, 1, 15, 12, 0)
        )
        is False
    )

    # 09:00 - 10:00 does NOT overlap
    assert (
        slot_rules.has_overlap(
            examiner.id, datetime(2030, 1, 15, 9, 0), datetime(2030, 1, 15, 10, 0)
        )
        is False
    )


def test_cancelled_slot_ignored(app, make_examination, make_examiner, make_slot):
    exam = make_examination()
    examiner = make_examiner()

    slot = make_slot(
        exam, examiner, start_at=datetime(2030, 1, 15, 10, 0), end_at=datetime(2030, 1, 15, 11, 0)
    )
    slot.status = "cancelled"
    db.session.commit()

    assert (
        slot_rules.has_overlap(
            examiner.id, datetime(2030, 1, 15, 10, 0), datetime(2030, 1, 15, 11, 0)
        )
        is False
    )
