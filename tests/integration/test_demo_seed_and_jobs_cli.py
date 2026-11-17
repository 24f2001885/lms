"""
FILE PURPOSE: Integration tests for scripts/seed_demo_data.py and Flask CLI jobs commands.
"""
import importlib.util
from pathlib import Path

from app.models import Course, Examination, ExaminationSlot, User


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_demo_data", Path("scripts/seed_demo_data.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_demo_data_and_jobs_cli(app, db_session):
    seed_mod = _load_seed_module()
    seed_mod.main(app=app)

    assert Course.query.count() == 2
    assert Examination.query.count() == 3
    assert User.query.filter_by(role="student").count() == 20
    assert User.query.filter_by(role="examiner").count() == 4

    for slot in ExaminationSlot.query.all():
        active = sum(1 for b in slot.bookings if b.status in ("booked", "completed"))
        assert slot.booked_count == active

    runner = app.test_cli_runner()
    res_sync = runner.invoke(args=["jobs", "sync-exam-status"])
    assert res_sync.exit_code == 0

    res_purge = runner.invoke(args=["jobs", "purge-soft-deleted", "--days", "90"])
    assert res_purge.exit_code == 0
    assert "Purged 0" in res_purge.output
