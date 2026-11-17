"""
FILE PURPOSE: EXM-10 Examiner chart page.
Renders examiner charts view (4 declarative chart cards).
"""

from flask import render_template, request

from app.blueprints.examiner import examiner_bp
from app.security.decorators import approved_examiner_required

ALLOWED_DAYS = (7, 30, 90, 180)
DEFAULT_DAYS = 30


@examiner_bp.route("/charts", methods=["GET"])
@approved_examiner_required
def charts():
    raw_days = request.args.get("days", DEFAULT_DAYS)
    try:
        days = int(raw_days)
        if days not in ALLOWED_DAYS:
            days = DEFAULT_DAYS
    except (ValueError, TypeError):
        days = DEFAULT_DAYS

    return render_template("examiner/charts.html", days=days)
