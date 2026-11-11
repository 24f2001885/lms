import logging 
from logging.handlers import RotatingFileHandler
from pathlib import Path 
from uuid import uuid4
from flask import Flask, g, request


class RequestContextFilter(logging.Filter):
    """Injects current request_id and user_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(g, "request_id", "-")
        user = getattr(g, "user", None)
        record.user_id = getattr(user, "id", "-") if user else "-"
        return True

def setup_logging(app: Flask) -> None:
    """Configure structured console and rotating file logging."""
    logger = logging.getLogger("lms")
    level_name = app.config.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(log_level)

    # Avoid adding duplicate handlers if called multiple times (e.g. in tests)
    if logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s "
        "user_id=%(user_id)s %(message)s"
    )
    context_filter = RequestContextFilter()

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    logger.addHandler(console_handler)

    # 2. Rotating File Handler (skipped in testing)
    if not app.config.get("TESTING", False):
        log_file = app.config.get("LOG_FILE", "logs/lms.log")
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,  # 1 MB per file
            backupCount=5,       # Keep up to 5 archive files
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        logger.addHandler(file_handler)

def register_request_logging(app: Flask) -> None:
    """Register before_request and after_request hooks for request tracing."""

    @app.before_request
    def _attach_request_id():
        # Generate a clean 12-character unique hex request identifier
        g.request_id = uuid4().hex[:12]

    @app.after_request
    def _log_response(response):
        # Attach header for browser and API client debugging
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id

        # Log request summary without leaking sensitive passwords or tokens
        logger = logging.getLogger("lms")
        logger.info("%s %s -> %s", request.method, request.path, response.status_code)
        return response