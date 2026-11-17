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

    #admin pre seeded cli  
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.edu").strip().lower()
    ADMIN_FULL_NAME = os.environ.get("ADMIN_FULL_NAME", "System Admin").strip()
    ADMIN_INITIAL_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD", "Passwoord321!")

    #coockie
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # session lifetime
    PERMANENT_SESSION_LIFETIME_MINUTES = int(
        os.environ.get("PERMANENT_SESSION_LIFETIME_MINUTES", "30")
    )
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=PERMANENT_SESSION_LIFETIME_MINUTES)

    #logs
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    LOG_FILE = os.environ.get("LOG_FILE", "logs/lms.log")

    #pagination and validation 
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    MIN_PASSWORD_LENGTH = 8

class DevConfig(BaseConfig):
    DEBUG = True 
    TESTING = False

class TestConfig(BaseConfig):
    DEBUG = False 
    TESTING = True 

    WTF_CSRF_ENABLED = False 

    SECRET_KEY = "test-offline-secret-key-12345"

    # Test Administrator defaults
    ADMIN_EMAIL = "admin@test.local"
    ADMIN_FULL_NAME = "Test Admin"
    ADMIN_INITIAL_PASSWORD = "Admin#TestPass123"

    # SQLite test database (overridden dynamically by pytest fixtures in conftest.py)
    SQLALCHEMY_DATABASE_URI = _normalize_db_uri(os.environ.get("DATABASE_URL")) if os.environ.get("DATABASE_URL") else "sqlite:///:memory:"

class ProdConfig(BaseConfig):
    DEBUG = False
    TESTING = False

    def __init__(self):
        if not self.SECRET_KEY or self.SECRET_KEY == "dev-only-change-me":
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: SECRET_KEY must be set to a secure, "
                "random string in production environments."
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