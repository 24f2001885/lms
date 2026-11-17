"""
app/blueprints/student/__init__.py - Student portal blueprint.
"""

from flask import Blueprint

student_bp = Blueprint("student", __name__, url_prefix="/student")

from app.blueprints.student import bookings, dashboard, examinations, results  # noqa: E402,F401
