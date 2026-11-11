"""
FILE PURPOSE: Public and shared account routes: root redirect, register, login, logout, change password, pending-approval and inactive notices (screens PUB-01 to PUB-05).
DEPENDS ON: app/blueprints/auth/__init__.py (auth_bp), app/forms/auth.py, app/security/*, app/models, app/extensions.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET "/" (endpoint index): anonymous -> redirect to auth.login; signed in -> redirect to post_login_redirect_url(user).
2. GET/POST "/register" (endpoint register): signed-in users are redirected to their dashboard. On valid POST create the User with the normalised email, hashed password and role from the form. Student: approval_status "approved". Examiner: approval_status "pending". In the SAME transaction create the matching profile row (StudentProfile, or ExaminerProfile with department and contact_phone). Hard guard in the view: if form.role.data not in ("student","examiner") abort(400) - the Admin can never be created through the UI. On success flash "Account created. Please log in." (examiner: "Account created. An administrator must approve your account before you can sign in to the dashboard.") and redirect to auth.login. Catch IntegrityError on the unique email (race) and show the duplicate-email form error.
3. GET/POST "/login" (endpoint login): signed-in users are redirected onward. On valid POST call verify_credentials; on failure flash "Invalid email or password." with category danger and re-render with status 200 (same message for unknown email and wrong password). On success call login_user_session and redirect to post_login_redirect_url(user); honour an optional ?next= only if is_safe_redirect_target() and the user is allowed to land there (when must_change_password is true ignore next).
4. POST "/logout" (endpoint logout): login_required, CSRF-protected, calls logout_user_session, flashes "You have been logged out." and redirects to auth.login. POST only, as in TDR 5.1 (the PDR appendix lists GET; the TDR wins because logout must not be triggerable by a link or image tag). Do not add a GET route.
5. GET/POST "/change-password" (endpoint change_password): login_required only (must be reachable while must_change_password is true, and by inactive users NOT). Verify current_password with check_password, set the new hash, set must_change_password False, commit, flash "Password updated.", then redirect to post_login_redirect_url. Wrong current password -> form error, no change.
6. GET "/pending-approval" (endpoint pending_approval): login_required; if user is not an examiner, or the examiner is already approved and active, redirect to their dashboard. Render auth/pending_approval.html with variant text for approval_status "rejected".
7. GET "/account-inactive" (endpoint account_inactive): login_required; if user.is_active is True redirect to the dashboard; otherwise render auth/inactive.html. Show a Logout button only.
8. All redirects use url_for; no hard-coded paths. Responses for authentication failures never reveal which part failed.
9. Write INFO audit-style log lines for register, login success and logout (ids only). The audit_logs table is NOT used in this phase.
DEBUGGING:
# print(f"[DEBUG] login attempt email_present={bool(form.email.data)} valid={form.validate_on_submit()} errors={form.errors}")
OFFLINE DOCKER TEST CASES:
- Student registers -> user row has role student, approval approved, a student_profiles row exists, password_hash is not the raw password; redirect to /login with the success flash.
- Examiner registers -> approval pending and an examiner_profiles row with department saved.
- POST /register with role=admin returns 400 (or form error) and creates no user.
- Login with a wrong password and with an unknown email returns identical 200 pages containing "Invalid email or password."
- Student login redirects to /student/dashboard; examiner (pending) to /pending-approval; seeded admin to /change-password first, then to /admin/dashboard after changing it.
- GET /logout returns 405; POST /logout (with CSRF disabled in tests) clears the session and redirects to /login.
- Login with ?next=https://evil.example ignores the next value.
"""
"""
app/blueprints/auth/routes.py - Core authentication routes for LMS (PUB-01 to PUB-05).

Handles user login, registration (students/examiners), POST-only logout,
forced password change, pending approval notice, and inactive account notice.
"""

import logging
from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.blueprints.auth import auth_bp
from app.extensions import db
from app.forms.auth import ChangePasswordForm, LoginForm, RegisterForm
from app.models.examiner_profile import ExaminerProfile
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.security.auth_helpers import (
    get_current_user,
    is_safe_redirect_target,
    login_user_session,
    logout_user_session,
    post_login_redirect_url,
    verify_credentials,
)
from app.security.decorators import login_required

logger = logging.getLogger("lms")


@auth_bp.route("/", methods=["GET"])
def index():
    """Root URL router: Redirect authenticated users to their dashboard, else to login."""
    user = get_current_user()
    if user:
        return redirect(post_login_redirect_url(user))
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration for Students and Examiners (PUB-02)."""
    user = get_current_user()
    if user:
        return redirect(post_login_redirect_url(user))

    form = RegisterForm()
    if form.validate_on_submit():
        role = form.role.data
        if role not in ("student", "examiner"):
            abort(400)

        # Student accounts are automatically approved; examiners register as pending
        approval_status = "approved" if role == "student" else "pending"

        new_user = User(
            email=form.email.data.strip().lower(),
            full_name=form.full_name.data.strip(),
            role=role,
            approval_status=approval_status,
            is_active=True,
            must_change_password=False,
        )
        new_user.set_password(form.password.data)

        try:
            db.session.add(new_user)
            db.session.flush()

            # Create matching role profile in the same transaction
            if role == "examiner":
                profile = ExaminerProfile(
                    user_id=new_user.id,
                    department=form.department.data.strip() if form.department.data else None,
                    contact_phone=form.contact_phone.data.strip() if form.contact_phone.data else None,
                )
                db.session.add(profile)
            elif role == "student":
                profile = StudentProfile(
                    user_id=new_user.id,
                )
                db.session.add(profile)

            db.session.commit()
            logger.info("New %s registered: user_id=%s email=%s", role, new_user.id, new_user.email)

            if role == "examiner":
                flash(
                    "Account created. An administrator must approve your account before you can access the dashboard.",
                    "info",
                )
            else:
                flash("Account created successfully. Please log in.", "success")

            return redirect(url_for("auth.login"))

        except IntegrityError:
            db.session.rollback()
            form.email.errors.append("An account with this email already exists.")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login endpoint (PUB-01)."""
    user = get_current_user()
    if user:
        return redirect(post_login_redirect_url(user))

    form = LoginForm()
    if form.validate_on_submit():
        user = verify_credentials(form.email.data, form.password.data)
        if user:
            login_user_session(user)

            # Check for next parameter (safe relative redirect only)
            next_url = request.args.get("next")
            if next_url and is_safe_redirect_target(next_url) and not user.must_change_password:
                return redirect(next_url)

            return redirect(post_login_redirect_url(user))

        # Constant-time failure message (never reveals whether email or password was wrong)
        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """POST-only logout endpoint with CSRF protection."""
    logout_user_session()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password view for first-login reset or voluntary change (PUB-05)."""
    user = get_current_user()
    if not user.is_active:
        return redirect(url_for("auth.account_inactive"))

    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not user.check_password(form.current_password.data):
            form.current_password.errors.append("Incorrect current password.")
        else:
            user.set_password(form.new_password.data)
            user.must_change_password = False
            db.session.commit()
            logger.info("Password updated: user_id=%s", user.id)
            flash("Your password has been updated.", "success")
            return redirect(post_login_redirect_url(user))

    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/pending-approval", methods=["GET"])
@login_required
def pending_approval():
    """Notice page for unapproved or rejected examiners (PUB-03)."""
    user = get_current_user()
    if user.role != "examiner" or (user.approval_status == "approved" and user.is_active):
        return redirect(post_login_redirect_url(user))

    return render_template("auth/pending_approval.html")


@auth_bp.route("/account-inactive", methods=["GET"])
@login_required
def account_inactive():
    """Notice page for deactivated accounts (PUB-04)."""
    user = get_current_user()
    if user.is_active:
        return redirect(post_login_redirect_url(user))

    return render_template("auth/inactive.html")