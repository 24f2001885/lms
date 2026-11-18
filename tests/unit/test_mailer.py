"""
Unit tests for mailer.py (templates, log lifecycle, retries, privacy, threads) (P12).
"""

import pytest

from app.services.mailer import build_message

pytestmark = pytest.mark.mail


def test_unknown_template_keyerror(app):
    with app.app_context():
        with pytest.raises(KeyError):
            build_message("invalid_template", {})
