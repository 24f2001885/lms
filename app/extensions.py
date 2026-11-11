import sqlite3

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import DateTime, MetaData, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#  Explicit Constraint Naming Convention  
# Guarantees deterministic constraint names for SQLite and migrations
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):

    metadata = metadata


db = SQLAlchemy(model_class=Base)

csrf = CSRFProtect()


# Reusable Timestamp Mixin
# Provides naive UTC created_at and updated_at columns on all models
class TimestampMixin:

    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

# SQLite Concurrency & Integrity Pragmas
_pragmas_registered = False


def register_sqlite_pragmas() -> None:
    """
    Attach an idempotent connect listener to SQLAlchemy's Engine to enforce:
    1. PRAGMA foreign_keys=ON: Enforce relational constraints.
    2. PRAGMA journal_mode=WAL: Enable concurrent read/write transactions.
    3. PRAGMA busy_timeout=5000: Wait up to 5s on locked DB before raising.
    """
    global _pragmas_registered
    if _pragmas_registered:
        return

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.close()

    _pragmas_registered = True


def init_extensions(app: Flask) -> None:
    """Initialize core extensions and hooks on the Flask application."""
    register_sqlite_pragmas()
    db.init_app(app)