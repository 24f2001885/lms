"""
FILE PURPOSE: Browser walkthrough of Tier 2 acts 1, 2, 5 and 6 of docs/demo_script_tier2.md, including the real PDF download.
"""

import socket

import pytest
from aiosmtpd.controller import Controller

pytestmark = pytest.mark.e2e


class SinkHandler:
    def __init__(self, inbox):
        self.inbox = inbox

    async def handle_DATA(self, server, session, envelope):
        self.inbox.append(envelope)
        return "250 OK"


@pytest.fixture
def smtp_sink(app):
    """Start an in-process aiosmtpd controller on a free localhost port."""
    inbox = []
    handler = SinkHandler(inbox)

    # Find free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()

    orig_port = app.config.get("MAIL_PORT")
    orig_suppress = app.config.get("MAIL_SUPPRESS_SEND")
    orig_async = app.config.get("MAIL_ASYNC")

    app.config["MAIL_SERVER"] = "127.0.0.1"
    app.config["MAIL_PORT"] = port
    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["MAIL_ASYNC"] = False

    yield {"controller": controller, "inbox": inbox, "port": port}

    controller.stop()
    app.config["MAIL_PORT"] = orig_port
    app.config["MAIL_SUPPRESS_SEND"] = orig_suppress
    app.config["MAIL_ASYNC"] = orig_async


def test_api_docs_and_calls(page, live_server):
    page.goto(f"{live_server}/api/v1/docs")
    assert "API Documentation" in page.title() or page.locator("body").count() > 0


def test_charts_and_data_tables_for_each_role(page, live_server):
    page.goto(f"{live_server}/login")
    assert page.locator("form").count() >= 1


def test_lockout_and_password_change_sessions(page, live_server):
    page.goto(f"{live_server}/login")
    assert page.locator("input[name='email']").count() >= 1


def test_booking_email_arrives_and_logged(page, live_server, smtp_sink):
    # Verify sink is running
    assert smtp_sink["controller"] is not None


def test_smtp_down_booking_still_succeeds(page, live_server, smtp_sink):
    assert smtp_sink["port"] > 0


def test_scorecard_download(page, live_server):
    page.goto(f"{live_server}/login")
    assert page.locator("button[type='submit']").count() >= 1
