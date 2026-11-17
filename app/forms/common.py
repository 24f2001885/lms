"""
Shared forms used by every role (CSRF-only POST actions and list pagination helpers).
"""

from typing import Any

from flask_wtf import FlaskForm

from app.validation import limits


class ConfirmForm(FlaskForm):
    """CSRF-only form for state-changing POST actions that take no extra fields."""


class FilterForm(FlaskForm):
    """Base form for GET filter bars with CSRF disabled."""

    class Meta:
        csrf = False


def parse_page(args: dict[str, Any]) -> tuple[int, int]:
    """Parse and clamp (page, per_page) from request.args using limits constants."""
    try:
        page = int(args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(args.get("per_page", limits.DEFAULT_PAGE_SIZE))
        if per_page < 1:
            per_page = 1
        elif per_page > limits.MAX_PAGE_SIZE:
            per_page = limits.MAX_PAGE_SIZE
    except (ValueError, TypeError):
        per_page = limits.DEFAULT_PAGE_SIZE

    return page, per_page
