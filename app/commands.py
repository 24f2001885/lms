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
    click.echo(f"Created {len(tables)} tables: {', '.join(tables)}")

    missing = set(EXPECTED_TIER1_TABLES) - set(tables)
    if missing:
        click.echo(f"WARNING: Expected tables missing: {', '.join(sorted(missing))}")

    admin_status = seed_admin(current_app)
    admin_email = current_app.config["ADMIN_EMAIL"]
    if admin_status == "created":
        click.echo(f"Admin account successfully created: {admin_email}")
    else:
        click.echo(f"Admin account already exists: {admin_email}")


def register_cli(flask_app: Flask) -> None:
    """Register custom CLI commands with the Flask application instance."""
    flask_app.cli.add_command(init_db_command)  