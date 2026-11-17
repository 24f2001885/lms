"""
Keyboard-only navigation and focus indicator tests in a real browser (P10).
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.a11y]


def test_skip_link_first_and_moves_focus_to_main(page, live_server):
    """First Tab focuses the skip link and Enter moves focus to <main id='main-content'>."""
    page.goto(f"{live_server}/login")
    page.keyboard.press("Tab")
    active_cls = page.evaluate("() => document.activeElement.className")
    assert "skip-link" in active_cls

    page.keyboard.press("Enter")
    active_id = page.evaluate("() => document.activeElement.id")
    assert active_id == "main-content"


def test_focus_indicator_visible_on_controls(page, live_server):
    """Focused controls display a visible outline of at least 2 px."""
    page.goto(f"{live_server}/login")
    page.locator("#email").focus()
    outline_width = page.evaluate(
        "() => parseFloat(window.getComputedStyle(document.activeElement).outlineWidth)"
    )
    assert outline_width >= 2.0
