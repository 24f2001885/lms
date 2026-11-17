"""
app/blueprints/student/__init__.py - Student portal blueprint.
"""

from flask import Blueprint

student_bp = Blueprint("student", __name__, url_prefix="/student")

from app.blueprints.student import (  # noqa: E402, F401
    bookings,
    charts,
    dashboard,
    examinations,
    results,
)

# Endpoint aliases for template navigation consistency
student_bp.add_url_rule(
    "/examinations", endpoint="examinations", view_func=examinations.examinations_list
)
student_bp.add_url_rule("/bookings", endpoint="bookings", view_func=bookings.my_bookings_list)
student_bp.add_url_rule("/results", endpoint="results", view_func=results.results_list)
