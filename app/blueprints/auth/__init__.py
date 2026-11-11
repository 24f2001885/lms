"""
FILE PURPOSE: Defines the "auth" blueprint (no url_prefix) and imports its route modules.
DEPENDS ON: app/blueprints/auth/routes.py, app/blueprints/auth/profile.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Create auth_bp = Blueprint("auth", __name__, template_folder omitted because templates live in app/templates/auth).
2. At the bottom import the route modules (routes, profile) so their decorators register on auth_bp; add "# noqa: E402,F401" comments for ruff.
3. No logic besides the blueprint object and the imports.
DEBUGGING:
# print(f"[DEBUG] auth_bp endpoints: {[r.endpoint for r in current_app.url_map.iter_rules() if r.endpoint.startswith('auth.')]}")
OFFLINE DOCKER TEST CASES:
- app.url_map contains the endpoints auth.index, auth.login, auth.register, auth.logout, auth.change_password, auth.pending_approval, auth.account_inactive, auth.profile.

app/blueprints/auth/__init__.py - Authentication and public identity blueprint.
"""

from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

# Import routes after creating auth_bp to register views without circular dependencies
from app.blueprints.auth import profile, routes  # noqa: E402, F401