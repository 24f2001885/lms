"""
FILE PURPOSE: STU-11 Student chart page.
Renders student progress charts view (3 declarative chart cards).
"""

from flask import render_template, request

from app.blueprints.student import student_bp
from app.security.decorators import student_required

ALLOWED_DAYS = (7, 30, 90, 180)
DEFAULT_DAYS = 30


@student_bp.route("/charts", methods=["GET"])
@student_required
def charts():
    raw_days = request.args.get("days", DEFAULT_DAYS)
    try:
        days = int(raw_days)
        if days not in ALLOWED_DAYS:
            days = DEFAULT_DAYS
    except (ValueError, TypeError):
        days = DEFAULT_DAYS

    return render_template("student/charts.html", days=days)
