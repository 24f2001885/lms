"""
FILE PURPOSE: Shared profile view/edit for any signed-in role (screen PUB-06, route /profile).
DEPENDS ON: app/blueprints/auth/__init__.py (auth_bp), app/forms/profile.py, app/models.
PROMPT FOR LLM IMPLEMENTATION:
1. GET/POST "/profile" (endpoint profile): role-aware via the decorator login_required plus the inactive and must-change-password checks from role_required(("admin","examiner","student")) - reuse role_required with all three roles.
2. GET: pre-fill ProfileForm from the user and the matching profile row (examiner_profiles or student_profiles; admin has none). Render auth/profile.html with the list of visible fields from fields_for_role.
3. POST: validate, then copy ONLY the whitelisted fields for that role onto the user/profile rows (never role, approval_status, is_active, email, password). If a student has no profile row (legacy data), create it. Commit once, flash "Profile updated." and redirect back to auth.profile (post/redirect/get).
4. Show read-only account facts on the page: email, role, approval status (text), member since date.
DEBUGGING:
# print(f"[DEBUG] profile update user={user.id} fields={sorted(changed)}")
OFFLINE DOCKER TEST CASES:
- Student updates phone, program and roll_number -> persisted in student_profiles; full_name persisted on users.
- Examiner updates department and designation -> persisted in examiner_profiles.
- Admin sees only the full name field.
- POST containing role=admin leaves the user's role unchanged.
- Anonymous GET /profile redirects to /login.
"""
"""
app/blueprints/auth/profile.py - Shared profile management view for all roles (PUB-06).
"""

import logging
from flask import flash, redirect, render_template, url_for

from app.blueprints.auth import auth_bp
from app.extensions import db
from app.forms.profile import ProfileForm
from app.models.student_profile import StudentProfile
from app.security.auth_helpers import get_current_user
from app.security.decorators import role_required

logger = logging.getLogger("lms")


@auth_bp.route("/profile", methods=["GET", "POST"])
@role_required("admin", "examiner", "student")
def profile():
    """View and update profile information for the authenticated user."""
    user = get_current_user()
    visible_fields = ProfileForm.fields_for_role(user.role)
    form = ProfileForm()

    if form.validate_on_submit():
        # Whitelisted field updates based on user role
        user.full_name = form.full_name.data.strip()

        if user.role == "examiner" and user.examiner_profile:
            user.examiner_profile.contact_phone = form.contact_phone.data.strip() if form.contact_phone.data else None
            user.examiner_profile.department = form.department.data.strip() if form.department.data else None
            user.examiner_profile.designation = form.designation.data.strip() if form.designation.data else None

        elif user.role == "student":
            if not user.student_profile:
                user.student_profile = StudentProfile(user_id=user.id)
                db.session.add(user.student_profile)

            user.student_profile.contact_phone = form.contact_phone.data.strip() if form.contact_phone.data else None
            user.student_profile.roll_number = form.roll_number.data.strip().upper() if form.roll_number.data else None
            user.student_profile.program = form.program.data.strip() if form.program.data else None

        db.session.commit()
        logger.info("Profile updated: user_id=%s role=%s", user.id, user.role)
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    # Pre-populate form on GET request
    if form.full_name.data is None:
        form.full_name.data = user.full_name

        if user.role == "examiner" and user.examiner_profile:
            form.contact_phone.data = user.examiner_profile.contact_phone
            form.department.data = user.examiner_profile.department
            form.designation.data = user.examiner_profile.designation

        elif user.role == "student" and user.student_profile:
            form.contact_phone.data = user.student_profile.contact_phone
            form.roll_number.data = user.student_profile.roll_number
            form.program.data = user.student_profile.program

    return render_template("auth/profile.html", form=form, visible_fields=visible_fields)