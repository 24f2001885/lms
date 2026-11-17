"""
FILE PURPOSE: GET /api/v1/session returns current authenticated user and CSRF token for state-changing requests.
NOTE: Session cookie is the sole credential in Tier 2 (TDR 5.2); send csrf_token as X-CSRFToken header on POST/PUT/DELETE.
"""

from flask import g
from flask_wtf.csrf import generate_csrf

from app.blueprints.api_v1 import api_bp
from app.blueprints.api_v1.common import api_login_required, ok
from app.blueprints.api_v1.serializers import user_to_dict


@api_bp.route("/session", methods=["GET"])
@api_login_required
def get_session():
    return ok(
        {
            "user": user_to_dict(g.user),
            "csrf_token": generate_csrf(),
        }
    )
