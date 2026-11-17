"""
app/blueprints/admin/__init__.py - Administrator blueprint initialization for LMS.
"""

from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Import all route modules so their views register on admin_bp
from app.blueprints.admin import (  # noqa: E402, F401
    booking_actions,
    bookings,
    charts,
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

# Endpoint aliases for template navigation consistency
admin_bp.add_url_rule("/courses", endpoint="courses_list", view_func=courses.courses)
admin_bp.add_url_rule(
    "/examinations", endpoint="examinations_list", view_func=examinations.examinations
)
admin_bp.add_url_rule("/examiners", endpoint="examiners_list", view_func=examiners.examiners)
admin_bp.add_url_rule("/students", endpoint="students_list", view_func=students.students)
admin_bp.add_url_rule("/slots", endpoint="slots_list", view_func=slots.slots)
admin_bp.add_url_rule("/bookings", endpoint="bookings_list", view_func=bookings.bookings)
