"""
FILE PURPOSE: Flask CLI commands for database setup and scheduled jobs (TDR 11).
"""

import sys

import click
from flask.cli import with_appcontext

from app.services import exam_status, maintenance


def register_cli(app):
    @app.cli.command("init-db")
    @with_appcontext
    def init_db_command():
        from app.extensions import db

        db.create_all()
        click.echo("Database initialized.")

    @app.cli.group("jobs")
    def jobs_group():
        """Periodic maintenance and status synchronization jobs."""

    @jobs_group.command("sync-exam-status")
    @with_appcontext
    def sync_exam_status_command():
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
    @with_appcontext
    def purge_soft_deleted_command(days):
        try:
            count = maintenance.purge_soft_deleted(older_than_days=days)
            click.echo(f"Purged {count} soft-deleted examinations older than {days} days.")
        except Exception as exc:
            click.echo(f"ERROR: purge-soft-deleted failed: {exc}", err=True)
            sys.exit(1)
