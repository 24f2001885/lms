"""
app/commands.py - Custom Flask CLI commands for LMS.

Implements the 'init-db' command for programmatic database schema creation
and idempotent Administrator account seeding (PDR Section 2.1, Course Requirement).
"""

import click
from flask import Flask

from app.extensions import db

EXPECTED_TIER1_TABLES = (
    "audit_logs",
    "bookings",
    "courses",
    "evaluation_scores",
    "evaluations",
    "examination_examiners",
    "examination_rubrics",
    "examination_slots",
    "examinations",
    "examiner_profiles",
    "student_profiles",
    "users",
)
EXPECTED_TIER2_TABLES = ("email_logs",)


def create_database() -> list[str]:
    """Execute db.create_all() and return the sorted list of created table names."""
    db.create_all()
    inspector = db.inspect(db.engine)
    tables = sorted(inspector.get_table_names())
    return [t for t in tables if not t.startswith("sqlite_")]


def seed_admin(flask_app: Flask) -> str:
    """
    Idempotently seed the initial Administrator user from environment config.

    Returns:
        'created' if a new Admin was inserted, or 'exists' if already present.
    """
    from app.models.user import User

    email = flask_app.config.get("ADMIN_EMAIL", "").strip().lower()
    full_name = flask_app.config.get("ADMIN_FULL_NAME", "System Admin").strip()
    password = flask_app.config.get("ADMIN_INITIAL_PASSWORD", "")

    if not email or not password:
        raise click.ClickException(
            "Configuration Error: ADMIN_EMAIL and ADMIN_INITIAL_PASSWORD must be set in .env"
        )

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        if existing_user.role != "admin":
            raise click.ClickException(
                f"Conflict: Account with email '{email}' already exists with role '{existing_user.role}'."
            )
        return "exists"

    admin_user = User(
        email=email,
        full_name=full_name,
        role="admin",
        approval_status="approved",
        is_active=True,
        must_change_password=True,
    )
    admin_user.set_password(password)

    db.session.add(admin_user)
    db.session.commit()
    return "created"


@click.command("init-db")
def init_db_command():
    """Programmatically initialize database schema and seed initial Admin."""
    from flask import current_app

    click.echo("Initializing LMS database schema...")
    tables = create_database()
    click.echo(f"Database ready at: {current_app.config['SQLALCHEMY_DATABASE_URI']}")
    tier1_found = [t for t in EXPECTED_TIER1_TABLES if t in tables]
    tier2_found = [t for t in EXPECTED_TIER2_TABLES if t in tables]
    click.echo(f"Tier 1 tables: {len(tier1_found)}, Tier 2 tables: {len(tier2_found)}")
    click.echo(f"Created {len(tables)} tables: {', '.join(tables)}")

    missing_tier1 = set(EXPECTED_TIER1_TABLES) - set(tables)
    if missing_tier1:
        click.echo(f"WARNING: Expected Tier 1 tables missing: {', '.join(sorted(missing_tier1))}")
    missing_tier2 = set(EXPECTED_TIER2_TABLES) - set(tables)
    if missing_tier2:
        click.echo(f"WARNING: Expected Tier 2 tables missing: {', '.join(sorted(missing_tier2))}")

    admin_status = seed_admin(current_app)
    admin_email = current_app.config["ADMIN_EMAIL"]
    if admin_status == "created":
        click.echo(f"Admin account successfully created: {admin_email}")
    else:
        click.echo(f"Admin account already exists: {admin_email}")


@click.group("jobs")
def jobs_group():
    """Periodic maintenance and status synchronization jobs."""


@jobs_group.command("sync-exam-status")
def sync_exam_status_command():
    import sys

    from app.services import exam_status

    try:
        summary = exam_status.sync_all()
        click.echo(
            f"Synced {summary['examinations']} examinations: "
            f"{summary['slots_completed']} slots completed, "
            f"{summary['bookings_completed']} bookings completed, "
            f"{summary['status_changes']} status changes."
        )
    except Exception as exc:
        click.echo(f"ERROR: sync-exam-status failed: {exc}", err=True)
        sys.exit(1)


@jobs_group.command("purge-soft-deleted")
@click.option("--days", default=90, show_default=True, type=int, help="Minimum age in days.")
def purge_soft_deleted_command(days):
    import sys

    from app.services import maintenance

    try:
        count = maintenance.purge_soft_deleted(older_than_days=days)
        click.echo(f"Purged {count} soft-deleted examinations older than {days} days.")
    except Exception as exc:
        click.echo(f"ERROR: purge-soft-deleted failed: {exc}", err=True)
        sys.exit(1)


@jobs_group.command("retry-failed-emails")
@click.option(
    "--max-attempts", default=None, type=int, help="Maximum attempts before terminal failure."
)
def retry_failed_emails_command(max_attempts):
    import sys

    from flask import current_app

    from app.services import mailer

    try:
        if max_attempts is None:
            max_attempts = current_app.config.get("MAIL_MAX_ATTEMPTS", 3)
        summary = mailer.retry_failed(max_attempts=max_attempts)
        click.echo(
            f"Retry summary: {summary['considered']} considered, "
            f"{summary['sent']} sent, {summary['still_failed']} still failed."
        )
    except Exception as exc:
        click.echo(f"ERROR: retry-failed-emails failed: {exc}", err=True)
        sys.exit(1)


@jobs_group.command("purge-email-logs")
@click.option("--days", default=None, type=int, help="Retention period in days.")
def purge_email_logs_command(days):
    import sys

    from flask import current_app

    from app.services import mailer

    try:
        if days is None:
            days = current_app.config.get("EMAIL_LOG_RETENTION_DAYS", 90)
        count = mailer.purge_old(days=days)
        click.echo(f"Purged {count} email logs older than {days} days.")
    except Exception as exc:
        click.echo(f"ERROR: purge-email-logs failed: {exc}", err=True)
        sys.exit(1)


def register_cli(flask_app: Flask) -> None:
    """Register custom CLI commands with the Flask application instance."""
    flask_app.cli.add_command(init_db_command)
    flask_app.cli.add_command(jobs_group)
