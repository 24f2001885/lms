"""
app/__init__.py - Application Factory for LMS (Milestone P2: Authentication & RBAC).

Initializes configuration, structured logging, database extensions, CSRF protection,
request authentication hooks, template context processors, error handlers, and blueprints.
"""

import os

from flask import Flask

from app.commands import register_cli
from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import csrf, init_extensions
from app.logging_config import register_request_logging, setup_logging
from app.security.auth_helpers import get_current_user, load_current_user, role_dashboard_url


def create_app(config_name: str | None = None) -> Flask:
    """
    Construct, configure, and return the LMS Flask application instance.
    """
    flask_app = Flask(__name__, instance_relative_config=True)

    # 1. Load configuration
    config_class = get_config(config_name)
    flask_app.config.from_object(config_class)
    os.makedirs(flask_app.instance_path, exist_ok=True)

    # 2. Structured logging & request tracing
    setup_logging(flask_app)
    register_request_logging(flask_app)

    # 3. Database extensions and SQLite pragmas
    init_extensions(flask_app)

    # 4. Global CSRF protection
    csrf.init_app(flask_app)

    # 5. Model metadata registration
    import app.models  # noqa: F401

    # 6. CLI registration (flask init-db)
    register_cli(flask_app)

    # 7. Register error handlers (403, 404, 500, AppError, CSRFError)
    register_error_handlers(flask_app)

    # 8. Request authentication hook (sets g.user from session)
    @flask_app.before_request
    def _authenticate_request():
        load_current_user()

    # 9. Context processor injecting current_user and helpers into all Jinja2 templates
    @flask_app.context_processor
    def inject_template_globals():
        return {
            "current_user": get_current_user(),
            "role_dashboard_url": role_dashboard_url,
        }

    # 10. Register application blueprints
    from app.blueprints.admin import admin_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.examiner import examiner_bp
    from app.blueprints.student import student_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(examiner_bp)
    flask_app.register_blueprint(student_bp)

    return flask_app
