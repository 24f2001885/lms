"""
tests/unit/test_smoke_app.py - Smoke test suite updated for Phase P2.

In P2, root / redirects anonymous users to /login (HTTP 302).
"""

from app import create_app


def test_root_returns_placeholder_page():
    """Verify that GET / redirects anonymous users to /login."""
    app = create_app("testing")
    client = app.test_client()

    response = client.get("/")

    # In Phase P2, root redirects anonymous visitors to /login
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_factory_returns_independent_apps():
    """Verify that create_app() produces independent instances with valid secret keys."""
    app1 = create_app("testing")
    app2 = create_app("testing")

    assert app1 is not app2
    assert app1.config["SECRET_KEY"] is not None
    assert len(app1.config["SECRET_KEY"]) > 0


def test_unknown_route_is_404():
    """Verify that an undefined URL path returns HTTP 404 Not Found."""
    app = create_app("testing")
    client = app.test_client()

    response = client.get("/does-not-exist-at-all")

    assert response.status_code == 404
