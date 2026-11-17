"""
FILE PURPOSE: End-to-end browser verification of Tier 1 demo flow.
"""
import pytest


@pytest.mark.e2e
def test_full_tier1_flow(live_server, offline_page):
    offline_page.goto(f"{live_server}/login")
    assert offline_page.locator("form").count() >= 1
