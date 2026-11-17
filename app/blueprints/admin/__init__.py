"""
app/blueprints/admin/__init__.py - Administrator blueprint initialization for LMS.
"""

from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Import all route modules so their views register on admin_bp
from app.blueprints.admin import (  # noqa: E402, F401
    booking_actions,
    bookings,
    courses,
    dashboard,
    evaluations,
    examinations,
    examiners,
    history,
    rubrics,
    search,
    slots,
    students,
)