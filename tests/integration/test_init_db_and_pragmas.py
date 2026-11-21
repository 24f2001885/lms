"""
FILE PURPOSE: End-to-end checks of programmatic database creation, Admin seeding and SQLite pragmas (course rule: DB created by code; Admin pre-exists).
DEPENDS ON: app/cli.py, app/extensions.py, tests/conftest.py (uses its own empty temp DB, not the pre-created tables).
PROMPT FOR LLM IMPLEMENTATION:
1. Use app.test_cli_runner() and a temp DB path. Set ADMIN_EMAIL, ADMIN_FULL_NAME, ADMIN_INITIAL_PASSWORD in app.config for the test.
2. Tests: test_init_db_creates_exactly_12_tables (compare with EXPECTED_TIER1_TABLES, ignore sqlite_sequence), test_init_db_creates_one_admin (role admin, approval approved, is_active, must_change_password True, check_password works), test_init_db_is_idempotent (run twice: 1 user, same password_hash, second output says already exists), test_init_db_never_overwrites_changed_admin_password, test_init_db_requires_password_setting (exit code != 0, 0 users), test_init_db_output_hides_password, test_email_normalised_lowercase, test_existing_non_admin_with_same_email_aborts.
3. Pragma tests: test_foreign_keys_on (insert a booking with a missing slot_id -> IntegrityError), test_wal_mode_on_file_db, test_busy_timeout_5000.
4. Config tests: test_relative_sqlite_path_resolves_to_project_root (no instance/instance folder created), test_prod_config_requires_secret_key.
5. Logging test: test_request_id_header_present on GET "/".
6. Also assert that no table named email_logs, tests, payments or any Tier 3 name exists (tier discipline).
DEBUGGING:
# print(f"[DEBUG] cli output: {result.output!r}; exit={result.exit_code}")
OFFLINE DOCKER TEST CASES:
- All tests pass with the network disabled (docker compose --profile test run --rm test).
- After "docker compose up --build" and a first "init-db" inside the container, instance/emp.db exists on the host through the bind mount.

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
