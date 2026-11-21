"""
tests/integration/test_init_db_and_pragmas.py - Integration tests for init-db and SQLite pragmas.
"""

from sqlalchemy import text

from app.commands import EXPECTED_TIER1_TABLES
from app.extensions import db
from app.models import User


def test_init_db_creates_exactly_12_tables(app, runner):
    """Verify flask init-db creates all 12 expected Tier 1 tables."""
    result = runner.invoke(args=["init-db"])
    assert result.exit_code == 0
    assert "Created 12 tables" in result.output

    inspector = db.inspect(db.engine)
    tables = [t for t in inspector.get_table_names() if not t.startswith("sqlite_")]
    assert sorted(tables) == sorted(EXPECTED_TIER1_TABLES)


def test_init_db_is_idempotent(app, runner):
    """Verify running init-db twice safely reports admin already exists."""
    runner.invoke(args=["init-db"])
    result2 = runner.invoke(args=["init-db"])
    assert result2.exit_code == 0
    assert "Admin account already exists" in result2.output

    admin_count = User.query.filter_by(role="admin").count()
    assert admin_count == 1


def test_sqlite_foreign_keys_on(app):
    """Verify PRAGMA foreign_keys is 1 (ON)."""
    val = db.session.execute(text("PRAGMA foreign_keys;")).scalar()
    assert val == 1


def test_sqlite_busy_timeout(app):
    """Verify PRAGMA busy_timeout is set to 5000ms."""
    val = db.session.execute(text("PRAGMA busy_timeout;")).scalar()
    assert val == 5000
