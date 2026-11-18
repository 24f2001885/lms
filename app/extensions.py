import sqlite3

from flask import Flask, current_app, session
from flask_login import LoginManager
from flask_login.config import SESSION_KEYS
from flask_login.signals import session_protected
from flask_mail import Mail
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

mail = Mail()


class EmpLoginManager(LoginManager):
    """Custom LoginManager fixing Flask-Login strong protection when permanent=True."""

    def _session_protection_failed(self):
        sess = session._get_current_object()
        ident = self._session_identifier_generator()

        app = current_app._get_current_object()
        mode = app.config.get("SESSION_PROTECTION", self.session_protection)

        if not mode or mode not in ["basic", "strong"]:
            return False

        if sess and ident != sess.get("_id", None):
            if mode == "basic":
                if sess.get("_fresh") is not False:
                    sess["_fresh"] = False
                session_protected.send(app)
                return False
            elif mode == "strong":
                for k in SESSION_KEYS:
                    sess.pop(k, None)

                sess["_remember"] = "clear"
                session_protected.send(app)
                return True

        return False


login_manager = EmpLoginManager()


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
_WRITE_LOCK_ATTACHED = False


def write_lock_enabled() -> bool:
    """Return True when the SQLite BEGIN IMMEDIATE listener is registered."""
    return _WRITE_LOCK_ATTACHED


def register_sqlite_pragmas(engine: Engine | type[Engine] | None = None) -> None:
    """Attach idempotent SQLite pragmas and BEGIN IMMEDIATE write locking.

    Trade-off documented per TDR 3.2:
    Every transaction takes SQLite's RESERVED write lock up front via BEGIN IMMEDIATE.
    Concurrent requests queue behind PRAGMA busy_timeout = 5000 rather than failing
    with 'database is locked' during read-then-write booking sequences. Transactions
    must remain short and sessions are always removed at request teardown.
    """
    global _pragmas_registered, _WRITE_LOCK_ATTACHED
    if _pragmas_registered:
        return

    target = engine if engine is not None else Engine
    if hasattr(target, "_emp_sqlite_configured") and target._emp_sqlite_configured:
        return

    @event.listens_for(target, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.close()

    @event.listens_for(target, "begin")
    def _begin_immediate(conn):
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    if hasattr(target, "_emp_sqlite_configured"):
        target._emp_sqlite_configured = True
    _pragmas_registered = True
    _WRITE_LOCK_ATTACHED = True


def init_extensions(app: Flask) -> None:
    """Initialize core extensions and hooks on the Flask application."""
    register_sqlite_pragmas()
    db.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = app.config.get("SESSION_PROTECTION", "strong")
    login_manager.login_message = None
    login_manager.init_app(app)
    mail.init_app(app)
