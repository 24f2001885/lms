"""
Public entry point of the validation package: exposes limits, messages,
validators, and the client configuration.
"""

from app.validation import limits, messages, validators
from app.validation.limits import LIMITS
from app.validation.messages import MESSAGES, all_keys, msg
from app.validation.validators import (
    CourseCodeChars,
    DateTimeLocal,
    DecimalPlaces,
    EndAfterStart,
    ExaminationWindows,
    MatchesField,
    PhoneChars,
    RollNumber,
    SafeText,
    ScoreRange,
    StrongPassword,
    ValidEmail,
    describe,
    html_attrs,
    lower_strip_filter,
    strip_filter,
    upper_strip_filter,
)


def client_config() -> dict:
    """Return the JSON-safe validation dictionary injected into templates."""
    return {
        "limits": LIMITS,
        "messages": MESSAGES,
        "rules": ["match", "after", "not-before", "not-after"],
    }


__all__ = [
    "LIMITS",
    "MESSAGES",
    "CourseCodeChars",
    "DateTimeLocal",
    "DecimalPlaces",
    "EndAfterStart",
    "ExaminationWindows",
    "MatchesField",
    "PhoneChars",
    "RollNumber",
    "SafeText",
    "ScoreRange",
    "StrongPassword",
    "ValidEmail",
    "all_keys",
    "client_config",
    "describe",
    "html_attrs",
    "limits",
    "lower_strip_filter",
    "messages",
    "msg",
    "strip_filter",
    "upper_strip_filter",
    "validators",
]
