"""
FILE PURPOSE: Fixtures for browser E2E tests using Werkzeug server + Playwright (offline-enforced).
"""

import threading

import pytest
from werkzeug.serving import make_server

from app.extensions import db


@pytest.fixture
def live_server(app):
    with app.app_context():
        db.create_all()

    server = make_server("127.0.0.1", 0, app)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _e2e_session_config(app):
    """Ensure objects created in E2E tests do not expire on commit, avoiding SQLite lock deadlocks."""
    with app.app_context():
        db.session.remove()
        db.session.configure(expire_on_commit=False)
        yield
        db.session.remove()
        db.session.configure(expire_on_commit=True)


@pytest.fixture
def offline_page(live_server):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            def _block_external(route):
                url = route.request.url
                if not url.startswith("http://127.0.0.1") and not url.startswith("data:"):
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", _block_external)
            yield page
            context.close()
            browser.close()
    except Exception as exc:
        pytest.skip(
            f"Playwright chromium browser unavailable ({exc}); run: playwright install chromium"
        )
