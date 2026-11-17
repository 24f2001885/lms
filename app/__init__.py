import os
from decimal import Decimal

from flask import Flask

from app.commands import register_cli
from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import csrf, init_extensions
from app.logging_config import register_request_logging, setup_logging
from app.security.auth_helpers import get_current_user, load_current_user, role_dashboard_url
from app.services.windows import format_local


def create_app(config_name: str | None = None, test_config: dict | None = None) -> Flask:
    """Construct, configure, and return the LMS Flask application instance."""
    flask_app = Flask(__name__, instance_relative_config=True)

    # 1. Load configuration
    config_class = get_config(config_name)
    flask_app.config.from_object(config_class)
    if test_config:
        flask_app.config.update(test_config)
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

    # 7. Register error handlers
    register_error_handlers(flask_app)

    # 8. Request authentication hook
    @flask_app.before_request
    def _authenticate_request():
        load_current_user()

    # 9. Context processor injecting current_user, helpers and validation_config into templates
    @flask_app.context_processor
    def inject_template_globals():
        from app.validation import client_config

        return {
            "current_user": get_current_user(),
            "role_dashboard_url": role_dashboard_url,
            "validation_config": client_config(),
        }

    # 10. Custom Jinja Template Filters (P3 Update)
    @flask_app.template_filter("localdt")
    def localdt_filter(dt, fmt="%d %b %Y, %H:%M"):
        """Format naive UTC datetime as local timezone string."""
        return format_local(dt, fmt=fmt)

    @flask_app.template_filter("money_marks")
    def money_marks_filter(val):
        """Format marks/numbers stripping trailing decimal zeroes."""
        if val is None:
            return ""
        try:
            d = Decimal(str(val))
            return f"{d.normalize():f}"
        except Exception:
            return str(val)

    # 11. Register application blueprints
    from app.blueprints.admin import admin_bp
    from app.blueprints.api_v1 import api_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.examiner import examiner_bp
    from app.blueprints.student import student_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(examiner_bp)
    flask_app.register_blueprint(student_bp)
    flask_app.register_blueprint(api_bp, url_prefix="/api/v1")

    flask_app.json.sort_keys = False

    return flask_app
