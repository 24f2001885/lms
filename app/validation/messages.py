"""
Single catalogue of user-facing validation messages used by the server (WTForms,
services) and by the browser (JavaScript receives the same dict).
"""

MESSAGES = {
    "required": "This field is required.",
    "min_length": "Must be at least {min} characters.",
    "max_length": "Must be at most {max} characters.",
    "between_length": "Must be between {min} and {max} characters.",
    "min_value": "Must be at least {min}.",
    "max_value": "Must be at most {max}.",
    "between_value": "Must be between {min} and {max}.",
    "invalid_email": "Enter a valid email address.",
    "invalid_number": "Enter a number.",
    "too_many_decimals": "Use at most {places} decimal places.",
    "pattern_mismatch": "{title}",
    "unsafe_characters": "Contains characters that are not allowed.",
    "phone_chars": "Use digits, +, - and spaces only.",
    "password_too_short": "Must be at least {min} characters.",
    "password_too_long": "Must be at most {max} characters.",
    "password_no_letter": "Must contain a letter.",
    "password_no_digit": "Must contain a number.",
    "password_same_as_current": "Choose a password that is different from the current one.",
    "invalid_datetime": "Enter a valid date and time",
    "end_after_start": "End time must be after start time.",
    "passwords_mismatch": "Passwords do not match",
    "rule_after": "{label} must be after {other}.",
    "rule_not_before": "{label} must not be before {other}.",
    "rule_not_after": "{label} must not be after {other}.",
    "email_taken": "An account with this email already exists.",
    "course_code_taken": "A course with this code already exists.",
    "login_failed": "Invalid email or password.",
    "char_counter": "{count} of {max} characters",
}


def msg(key: str, **kwargs) -> str:
    """Format a validation message template by key."""
    if key not in MESSAGES:
        raise KeyError(f"Unknown validation message key: {key!r}")
    return MESSAGES[key].format(**kwargs)


def all_keys() -> tuple[str, ...]:
    """Return all registered message keys."""
    return tuple(MESSAGES.keys())
