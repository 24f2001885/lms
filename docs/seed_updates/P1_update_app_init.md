<!--
FILE PURPOSE: Update prompt for app/__init__.py (already implemented in P0 as a placeholder app). Do not regenerate it from scratch.
HOW TO USE: give your LLM this prompt plus the CURRENT app/__init__.py and ask for the full updated file.
PROMPT FOR LLM IMPLEMENTATION:
1. Change create_app(config_name=None) so it loads config with get_config(config_name) from app/config.py (app.config.from_object). Keep instance_relative_config=True and keep creating the instance folder.
2. Call setup_logging(app) and register_request_logging(app) from app/logging_config.py, then init_extensions(app) from app/extensions.py (db and the SQLite pragma hook only; do NOT call csrf.init_app yet).
3. Import the app.models package inside the factory (import app.models) purely so every table is registered on db.metadata; do not import any model name into the module namespace.
4. Call register_cli(app) from app/cli.py so "flask --app app init-db" works.
5. Keep the P0 placeholder route "/" and its text exactly as is (P2 replaces it). Do not register any blueprint.
6. The P0 tests in tests/unit/test_smoke_app.py must still pass unchanged.
7. create_app must never touch the database at import time or on startup (tables are created only by init-db).
DEBUGGING:
# print(f"[DEBUG] create_app: config={app.config['ENV'] if 'ENV' in app.config else type(cfg).__name__} db={app.config['SQLALCHEMY_DATABASE_URI']}")
OFFLINE DOCKER TEST CASES:
- pytest tests/unit/test_smoke_app.py still passes (3 tests).
- flask --app app init-db works after this change on a clean checkout.
- create_app("testing") and create_app("development") use different config classes.
-->
