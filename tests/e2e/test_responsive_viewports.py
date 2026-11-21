"""
Real-browser responsive checks across 320, 375, 768, 1280, and 640x800 (200% zoom)
viewports (P10).
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.responsive]


@pytest.mark.parametrize(
    "width,height",
    [
        (320, 640),
        (375, 812),
        (768, 1024),
        (1280, 800),
        (640, 800),
    ],
)
def test_public_pages_no_horizontal_overflow(page, live_server, width, height):
    """At every breakpoint from 320 px to 1280 px, pages reflow with zero horizontal scroll."""
    page.set_viewport_size({"width": width, "height": height})
    for path in ("/login", "/register", "/api/v1/docs"):
        page.goto(f"{live_server}{path}")
        overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not overflow, f"Horizontal overflow on {path} at {width}x{height}"


def test_touch_targets_and_text_spacing_at_375px(page, live_server):
    """At 375 px, interactive controls meet 44 px height and WCAG 1.4.12 text spacing does not overflow."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(f"{live_server}/login")

    submit_box = page.locator("button[type='submit']").bounding_box()
    assert submit_box is not None and submit_box["height"] >= 44

    page.add_style_tag(content="""
        * {
            line-height: 1.5 !important;
            letter-spacing: 0.12em !important;
            word-spacing: 0.16em !important;
        }
        p { margin-bottom: 2em !important; }
        """)
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow
