"""
Unit tests for headers.py (policy string and registration) (P11).
"""

import pytest

from app.security.headers import add_csp_source, build_csp

pytestmark = pytest.mark.security


def test_build_csp_directives_exact():
    csp = build_csp()
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-eval" not in csp
    assert "unsafe-inline" in csp  # Only in style-src-attr


def test_add_csp_source_validation():
    with pytest.raises(ValueError):
        add_csp_source("script-src", "http://example.com")
    with pytest.raises(ValueError):
        add_csp_source("invalid-src", "https://example.com")

    add_csp_source("script-src", "https://trusted.com")
    csp = build_csp()
    assert "https://trusted.com" in csp
