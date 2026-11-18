import os
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _normalize_db_uri(raw_uri: str | None) -> str:
    if not raw_uri:
        default_path = (PROJECT_ROOT / "instance" / "lms.db").resolve()
        return f"sqlite:///{default_path}"
    if raw_uri.startswith("sqlite:///") and not raw_uri.startswith("sqlite:////"):
        rel_path = raw_uri.replace("sqlite:///", "", 1)
        abs_path = (PROJECT_ROOT / rel_path).resolve()
        return f"sqlite:///{abs_path}"
    return raw_uri


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_db_uri(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")

    # admin pre seeded cli
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.edu").strip().lower()
    ADMIN_FULL_NAME = os.environ.get("ADMIN_FULL_NAME", "System Admin").strip()
    ADMIN_INITIAL_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD", "Passwoord321!")

    # coockie
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # session lifetime
    PERMANENT_SESSION_LIFETIME_MINUTES = int(
        os.environ.get("PERMANENT_SESSION_LIFETIME_MINUTES", "30")
    )
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=PERMANENT_SESSION_LIFETIME_MINUTES)
    SESSION_ABSOLUTE_LIFETIME_MINUTES = int(
        os.environ.get("SESSION_ABSOLUTE_LIFETIME_MINUTES", "480")
    )
    SESSION_PROTECTION = os.environ.get("SESSION_PROTECTION", "strong").lower()
    SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "session")

    # rate limiting and security headers (P11)
    LOGIN_RATE_LIMIT_FAILURES = int(os.environ.get("LOGIN_RATE_LIMIT_FAILURES", "5"))
    LOGIN_RATE_LIMIT_WINDOW_MINUTES = int(os.environ.get("LOGIN_RATE_LIMIT_WINDOW_MINUTES", "15"))
    LOGIN_RATE_LIMIT_IP_FAILURES = int(os.environ.get("LOGIN_RATE_LIMIT_IP_FAILURES", "20"))
    SECURITY_HEADERS_ENABLED = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
    CSP_REPORT_ONLY = os.environ.get("CSP_REPORT_ONLY", "false").lower() == "true"
    WTF_CSRF_TIME_LIMIT = None

    # Email and Scorecard settings (P12)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")  # noqa: S105
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "emp@example.edu")
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"
    MAIL_ASYNC = os.environ.get("MAIL_ASYNC", "true").lower() == "true"
    MAIL_MAX_ATTEMPTS = int(os.environ.get("MAIL_MAX_ATTEMPTS", "3"))
    EMAIL_LOG_RETENTION_DAYS = int(os.environ.get("EMAIL_LOG_RETENTION_DAYS", "90"))
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")
    INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "Examination Management Portal")
    SCORECARD_DETERMINISTIC = os.environ.get("SCORECARD_DETERMINISTIC", "false").lower() == "true"

    # logs
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    LOG_FILE = os.environ.get("LOG_FILE", "logs/lms.log")

    # pagination and validation
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    MIN_PASSWORD_LENGTH = 8


class DevConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    MAIL_SUPPRESS_SEND = True


class TestConfig(BaseConfig):
    DEBUG = False
    TESTING = True

    WTF_CSRF_ENABLED = False

    SECRET_KEY = "test-offline-secret-key-12345"  # noqa: S105
    SECURITY_HEADERS_ENABLED = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_NAME = "session"

    LOGIN_RATE_LIMIT_FAILURES = 5
    LOGIN_RATE_LIMIT_WINDOW_MINUTES = 15
    LOGIN_RATE_LIMIT_IP_FAILURES = 20
    SESSION_ABSOLUTE_LIFETIME_MINUTES = 480

    MAIL_SUPPRESS_SEND = True
    MAIL_ASYNC = False
    SCORECARD_DETERMINISTIC = True

    # Test Administrator defaults
    ADMIN_EMAIL = "admin@test.local"
    ADMIN_FULL_NAME = "Test Admin"
    ADMIN_INITIAL_PASSWORD = "Admin#TestPass123"  # noqa: S105

    # SQLite test database (overridden dynamically by pytest fixtures in conftest.py)
    SQLALCHEMY_DATABASE_URI = (
        _normalize_db_uri(os.environ.get("DATABASE_URL"))
        if os.environ.get("DATABASE_URL")
        else "sqlite:///:memory:"
    )


class ProdConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_NAME = "__Host-emp-session"
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"

    def __init__(self):
        if not self.SECRET_KEY or self.SECRET_KEY == "dev-only-change-me":  # noqa: S105
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: SECRET_KEY must be set to a secure, "
                "random string in production environments."
            )
        if self.SESSION_PROTECTION not in ("strong", "basic"):
            raise ValueError(
                f"Invalid SESSION_PROTECTION: {self.SESSION_PROTECTION}. Must be 'strong' or 'basic'."
            )
        if not self.MAIL_SUPPRESS_SEND and not self.MAIL_SERVER:
            raise ValueError(
                "MAIL_SERVER must not be empty when MAIL_SUPPRESS_SEND is false in production."
            )


CONFIG_MAP: dict[str, type[BaseConfig]] = {
    "development": DevConfig,
    "testing": TestConfig,
    "production": ProdConfig,
}


def get_config(config_name: str | None = None) -> type[BaseConfig]:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development").lower()

    return CONFIG_MAP.get(config_name.lower(), DevConfig)
