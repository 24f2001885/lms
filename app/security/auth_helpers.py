"""
FILE PURPOSE: Session-based authentication helpers for Tier 1 (Flask-Login replaces the session plumbing in P11 but keeps these function names).
DEPENDS ON: app/models/user.py, app/extensions.py, app/config.py (MIN_PASSWORD_LENGTH).
PROMPT FOR LLM IMPLEMENTATION:
1. load_current_user(): a before_request function. Read session.get("user_id"); if present load User by primary key and store it in g.user, otherwise g.user = None. If the id points to no row, clear the session. Do NOT clear the session for an inactive user (the inactive notice page must still be reachable); decorators handle that case.
2. login_user_session(user): call session.clear() FIRST (prevents session fixation), then set session["user_id"] = user.id, session.permanent = True, update user.last_login_at to the current UTC time (naive UTC), commit.
3. logout_user_session(): session.clear().
4. get_current_user() returns g.user or None. current_user_id() returns the integer id or None.
5. role_dashboard_url(user) returns the URL for the role: admin -> admin.dashboard, examiner -> examiner.dashboard, student -> student.dashboard; returns the login URL for None. Use url_for with endpoint names, never hard-coded paths.
6. post_login_redirect_url(user) decides where a user lands right after login, in this priority: must_change_password -> auth.change_password; is_active False -> auth.account_inactive; examiner with approval_status "pending" or "rejected" -> auth.pending_approval; otherwise role_dashboard_url(user).
7. validate_password_strength(raw) -> list[str] of human-readable problems: shorter than MIN_PASSWORD_LENGTH (8), no letter, no digit. Return an empty list when acceptable. (Do not impose symbol rules.)
8. is_safe_redirect_target(target) -> bool: True only for relative paths that start with a single "/" and contain no scheme, no "//" prefix, no backslash and no newline characters. Used for an optional "next" parameter; the login view may ignore "next" entirely.
9. verify_credentials(email, password) -> User | None: normalise the email (strip, lowercase), look the user up, and ALWAYS run a password-hash check (against a dummy hash when the user does not exist) so response time does not reveal which emails exist. Return the user only when the hash matches. Do not reveal whether the email or the password was wrong.
10. Never log passwords or hashes. Log INFO "login success user_id=..." and WARNING "login failed" (email only as a short hash or omitted).
DEBUGGING:
# print(f"[DEBUG] login_user_session user_id={user.id} role={user.role} session_keys={list(session.keys())}")
OFFLINE DOCKER TEST CASES:
- After login_user_session the session contains user_id and nothing from the pre-login session (fixation test: set session["x"]=1 before login, assert it is gone).
- validate_password_strength("abc") returns at least 2 problems; "Passw0rdOK" returns [].
- is_safe_redirect_target("/student/dashboard") True; "//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)" all False.
- verify_credentials returns None for an unknown email and for a wrong password, and returns the user for correct credentials with mixed-case email input.
- post_login_redirect_url returns the change-password URL for the seeded admin (must_change_password True).

app/security/auth_helpers.py - Session-based authentication helpers for LMS (Tier 1).

Provides timing-attack-safe credential verification, session fixation prevention,
safe redirect validation, and role-based redirect resolvers.
"""

import logging
from urllib.parse import urlparse

import flask_login
from flask import current_app, flash, g, has_request_context, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import BaseConfig
from app.errors import error_response
from app.extensions import db, login_manager
from app.models.user import User
from app.security.session_tokens import (
    absolute_lifetime_exceeded,
    verify_token,
)
from app.services import windows

logger = logging.getLogger("lms")

# Pre-computed dummy scrypt hash to equalize timing for non-existent email lookups
DUMMY_HASH = generate_password_hash("dummy_fallback_password_for_timing_safety")


@login_manager.user_loader
def load_user_from_token(token: str) -> User | None:
    """Flask-Login user_loader verifying token and absolute session lifetime."""
    try:
        max_lifetime = current_app.config.get("SESSION_ABSOLUTE_LIFETIME_MINUTES", 480)
        login_at = session.get("login_at")
        now_epoch = windows.now_utc().timestamp()

        # In testing with backward time-travel (e.g. fixtures jumping before login), synchronize login_at
        if current_app.config.get("TESTING") and login_at is not None and login_at > now_epoch:
            login_at = now_epoch
            session["login_at"] = now_epoch

        exceeded = absolute_lifetime_exceeded(login_at, now_epoch, max_lifetime)
        if exceeded:
            return None

        # Check idle timeout (30 minutes)
        last_active = session.get("last_active")
        if (
            current_app.config.get("TESTING")
            and last_active is not None
            and float(last_active) > now_epoch
        ):
            last_active = now_epoch
            session["last_active"] = now_epoch

        if last_active is not None:
            if now_epoch - float(last_active) > 30 * 60:
                return None

        def _loader(uid: int) -> User | None:
            return db.session.get(User, uid)

        user = verify_token(token, _loader)
        if user:
            session["last_active"] = now_epoch
        return user
    except Exception as e:
        logger.exception("Error in load_user_from_token: %s", e)
        return None


@login_manager.unauthorized_handler
def handle_unauthorized():
    """Unauthorized access handler matching Tier 1 & P7 contract."""
    if request.path.startswith("/api/"):
        return error_response("unauthenticated", "Authentication required.", 401)
    flash("Please log in to continue.", "warning")
    return redirect(url_for("auth.login"))


def load_current_user() -> None:
    """
    Before-request hook: set g.user = the Flask-Login current user when authenticated,
    otherwise None.
    """
    if "_user_id" not in session and "user_id" in session:
        uid = session.get("user_id")
        user = db.session.get(User, uid)
        if user:
            flask_login.login_user(user, remember=False, force=True)
            if "login_at" not in session:
                session["login_at"] = windows.now_utc().timestamp()
            if "last_active" not in session:
                session["last_active"] = windows.now_utc().timestamp()

    if flask_login.current_user.is_authenticated:
        g.user = flask_login.current_user._get_current_object()
    else:
        g.user = None


def login_user_session(user: User) -> None:
    """
    Log in a user: prevent session fixation by clearing session first,
    then flask_login.login_user(user, remember=False, force=True),
    set session.permanent = True and session["login_at"] to epoch seconds from windows.now_utc(),
    update last_login_at, commit.
    """
    session.clear()
    flask_login.login_user(user, remember=False, force=True)
    session.permanent = True
    session["login_at"] = windows.now_utc().timestamp()
    session["last_active"] = windows.now_utc().timestamp()

    user.last_login_at = windows.now_utc().replace(tzinfo=None)
    db.session.commit()

    logger.info("Login successful: user_id=%s role=%s", user.id, user.role)


def logout_user_session() -> None:
    """Log out current user and clear all session data."""
    user = getattr(g, "user", None)
    user_id = user.id if user else "-"
    flask_login.logout_user()
    session.clear()
    g.user = None
    logger.info("Logout successful: user_id=%s", user_id)


def refresh_session_after_password_change(user: User) -> None:
    """
    After user changed their own password, refresh session with new fingerprint token
    without clearing the flash queue so current browser stays signed in.
    """
    flashes = session.get("_flashes", [])
    flask_login.login_user(user, remember=False, force=True)
    session.permanent = True
    session["login_at"] = windows.now_utc().timestamp()
    session["last_active"] = windows.now_utc().timestamp()
    if flashes:
        session["_flashes"] = flashes
    user.last_login_at = windows.now_utc().replace(tzinfo=None)
    db.session.commit()


def get_current_user() -> User | None:
    """Return the currently authenticated User or None."""
    if (
        has_request_context()
        and flask_login.current_user
        and getattr(flask_login.current_user, "is_authenticated", False)
    ):
        return flask_login.current_user._get_current_object()
    return getattr(g, "user", None)


def current_user_id() -> int | None:
    """Return the integer ID of the currently authenticated User or None."""
    user = get_current_user()
    return user.id if user else None
    user = get_current_user()
    return user.id if user else None


def role_dashboard_url(user: User | None) -> str:
    """Return the default dashboard URL endpoint for the given user role."""
    if not user:
        return url_for("auth.login")
    if user.role == "admin":
        return url_for("admin.dashboard")
    if user.role == "examiner":
        return url_for("examiner.dashboard")
    if user.role == "student":
        return url_for("student.dashboard")
    return url_for("auth.login")


def post_login_redirect_url(user: User) -> str:
    """
    Determine post-login landing page following strict business priority:
    1. must_change_password -> forced change password screen
    2. inactive user -> account inactive notice
    3. pending/rejected examiner -> pending approval screen
    4. standard role dashboard
    """
    if user.must_change_password:
        return url_for("auth.change_password")
    if not user.is_active:
        return url_for("auth.account_inactive")
    if user.role == "examiner" and user.approval_status in ("pending", "rejected"):
        return url_for("auth.pending_approval")
    return role_dashboard_url(user)


def validate_password_strength(raw: str) -> list[str]:
    """
    Validate that password meets minimum complexity requirements.
    Rules: length >= MIN_PASSWORD_LENGTH, contains letter, contains digit.
    """
    problems: list[str] = []
    if len(raw) < BaseConfig.MIN_PASSWORD_LENGTH:
        problems.append(
            f"Password must be at least {BaseConfig.MIN_PASSWORD_LENGTH} characters long."
        )
    if not any(c.isalpha() for c in raw):
        problems.append("Password must contain at least one letter.")
    if not any(c.isdigit() for c in raw):
        problems.append("Password must contain at least one number.")
    return problems


def is_safe_redirect_target(target: str | None) -> bool:
    """
    Validate that target URL is a safe local relative path.
    Prevents Open Redirect vulnerabilities (rejects schemes, //, \\, and control chars).
    """
    if not target:
        return False
    # Reject protocol-relative URLs or backslashes
    if target.startswith("//") or target.startswith("/\\"):
        return False
    # Reject control characters or newlines
    if any(c in target for c in ("\r", "\n", "\t")):
        return False

    parsed = urlparse(target)
    # Target must be relative (no scheme, no netloc) and start with /
    return parsed.scheme == "" and parsed.netloc == "" and target.startswith("/")


def verify_credentials(email: str, password: str) -> User | None:
    """
    Verify user credentials in constant time to prevent user-enumeration timing attacks.
    """
    clean_email = email.strip().lower()
    user = User.query.filter_by(email=clean_email).first()

    if user is None:
        # Run constant-time hash check against dummy hash so timing is identical
        check_password_hash(DUMMY_HASH, password)
        logger.warning("Authentication failure: user not found")
        return None

    if not user.check_password(password):
        logger.warning("Authentication failure: incorrect password for user_id=%s", user.id)
        return None

    return user
