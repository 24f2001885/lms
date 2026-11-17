"""
FILE PURPOSE: ADM-19 Admin chart page.
Renders the admin charts dashboard with 5 declarative chart cards.
"""

from flask import render_template, request

from app.blueprints.admin import admin_bp
from app.security.decorators import admin_required

ALLOWED_DAYS = (7, 30, 90, 180)
DEFAULT_DAYS = 30


@admin_bp.route("/charts", methods=["GET"])
@admin_required
def charts():
    raw_days = request.args.get("days", DEFAULT_DAYS)
    try:
        days = int(raw_days)
        if days not in ALLOWED_DAYS:
            days = DEFAULT_DAYS
    except (ValueError, TypeError):
        days = DEFAULT_DAYS

    return render_template("admin/charts.html", days=days)
