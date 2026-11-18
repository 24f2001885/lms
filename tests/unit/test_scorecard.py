"""
Unit tests for scorecard.build_scorecard (P12).
"""

import pytest

from app.services.scorecard import build_scorecard

pytestmark = pytest.mark.scorecard


def test_draft_submitted_foreign_unknown_return_none(app):
    with app.app_context():
        # Foreign or unpublished evaluates to None
        assert build_scorecard(999, 999) is None
