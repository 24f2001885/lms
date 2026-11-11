"""
app/forms/common.py - Shared forms and filter pagination helpers for LMS.
"""

from typing import Any

from flask_wtf import FlaskForm


class ConfirmForm(FlaskForm):
    """
    Empty form carrying a CSRF token. Used for state-changing POST actions
    (approve, delete, toggle) that do not require text inputs.
    """
    pass


class FilterForm(FlaskForm):
    """Base form for GET filter bars with CSRF protection disabled."""

    class Meta:
        csrf = False


def parse_page(args: dict[str, Any]) -> tuple[int, int]:
    """
    Safely parse page and per_page from request query arguments.
    Defaults to page=1, per_page=20 (clamped between 1 and 100).
    """
    try:
        page = int(args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(args.get("per_page", 20))
        if per_page < 1:
            per_page = 20
        elif per_page > 100:
            per_page = 100
    except (ValueError, TypeError):
        per_page = 20

    return page, per_page