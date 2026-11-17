"""
FILE PURPOSE: GET /api/v1/stats/summary returns the six dashboard totals as JSON (admin only).
"""

from app.blueprints.api_v1 import api_bp
from app.blueprints.api_v1.common import api_roles, ok
from app.services import api_queries


@api_bp.route("/stats/summary", methods=["GET"])
@api_roles("admin")
def stats_summary():
    return ok(api_queries.summary())
