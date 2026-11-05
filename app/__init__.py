import os
from typing import Optional
from flask import Flask, Response


# Create and return Flask app instance in optional config env (dev, test, production)
def create_app(config_name: Optional[str] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    os.makedirs(app.instance_path, exist_ok=True)
    @app.route("/", methods=["GET"])
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

    return app