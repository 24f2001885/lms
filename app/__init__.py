import os

from flask import Flask, Response

from app.commands import register_cli
from app.config import get_config
from app.extensions import init_extensions
from app.logging_config import register_request_logging, setup_logging


def create_app(config_name: str | None = None) -> Flask:
    """
    Construct, configure, and return the LMS Flask application instance.

    Args:
        config_name: Optional environment name ('development', 'testing', 'production').
                     Defaults to FLASK_ENV or 'development'.

    Returns:
        Configured Flask application instance.
    """
    flask_app = Flask(__name__, instance_relative_config=True)

    # 1. Load environment configuration from config object
    config_class = get_config(config_name)
    flask_app.config.from_object(config_class)
    os.makedirs(flask_app.instance_path, exist_ok=True)

    # 2. Configure structured logging & unique X-Request-ID tracing
    setup_logging(flask_app)
    register_request_logging(flask_app)

    # 3. Initialize database extensions and attach SQLite pragmas (WAL, FK, timeout)
    init_extensions(flask_app)

    # 4. Import models package to register all 12 table schemas on db.metadata
    # (Imported inside the factory to prevent circular import loops)
    import app.models  # noqa: F401

    # 5. Register custom Flask CLI commands (flask init-db)
    register_cli(flask_app)

    # -----------------------------------------------------------------
    # Baseline Placeholder Route for Milestone P0
    # Replaced by authentication and role-based redirects in Phase P2.
    # -----------------------------------------------------------------
    @flask_app.route("/", methods=["GET"])
    def index() -> Response:
        html_content = (
            "<!doctype html>"
            "<html lang='en'>"
            "<head><meta charset='utf-8'><title>LMS - Portal</title></head>"
            "<body>"
            "<h1>Examination Management Portal (LMS)</h1>"
            "<p>Placeholder page - Milestone P0. Features arrive in P1 to P6.</p>"
            "</body>"
            "</html>"
        )
        return Response(html_content, status=200, mimetype="text/html")

    return flask_app
