"""
Consistency tests for limits, messages, and client_config (P9).
"""

import json
import pathlib
import re

import pytest
from wtforms.validators import Length, NumberRange

from app.blueprints.api_v1.validation import CANCEL_SCHEMA, EXAMINATION_SCHEMA, SLOT_SCHEMA
from app.forms.auth import RegisterForm
from app.forms.booking_actions import ReasonForm
from app.forms.course import CourseForm
from app.forms.slot import SlotForm
from app.validation import LIMITS, MESSAGES, all_keys, client_config, limits, msg

pytestmark = pytest.mark.validation


def test_every_min_below_max():
    """Every *_MIN constant in limits.py is strictly less than its matching *_MAX."""
    pairs = [
        (limits.NAME_MIN, limits.NAME_MAX),
        (limits.PASSWORD_MIN, limits.PASSWORD_MAX),
        (limits.COURSE_CODE_MIN, limits.COURSE_CODE_MAX),
        (limits.COURSE_NAME_MIN, limits.COURSE_NAME_MAX),
        (limits.EXAM_NAME_MIN, limits.EXAM_NAME_MAX),
        (limits.DURATION_MIN, limits.DURATION_MAX),
        (limits.MAX_MARKS_MIN, limits.MAX_MARKS_MAX),
        (limits.CRITERION_MIN, limits.CRITERION_MAX),
        (limits.WEIGHTAGE_MIN, limits.WEIGHTAGE_MAX),
        (limits.CAPACITY_MIN, limits.CAPACITY_MAX),
        (limits.REASON_MIN, limits.REASON_MAX),
        (limits.DEFAULT_PAGE_SIZE, limits.MAX_PAGE_SIZE),
    ]
    for mn, mx in pairs:
        assert mn < mx


def test_limits_dict_contains_all_constants():
    """Every UPPER_SNAKE_CASE constant in limits.py is present in LIMITS in lower_snake_case."""
    for name in dir(limits):
        if name.isupper() and name != "LIMITS":
            assert name.lower() in LIMITS
            assert LIMITS[name.lower()] == getattr(limits, name)


def test_regex_strings_compile_and_are_browser_safe():
    """Regex patterns compile in Python and contain no lookbehind or named groups."""
    for pat in (limits.COURSE_CODE_PATTERN, limits.PHONE_PATTERN, limits.ROLL_PATTERN):
        compiled = re.compile(pat)
        assert compiled is not None
        assert "(?<" not in pat
        assert "(?P<" not in pat


def test_password_max_at_least_64():
    """PASSWORD_MAX is at least 64 characters (set to 128 in P9)."""
    assert limits.PASSWORD_MAX >= 64
    assert limits.PASSWORD_MAX == 128


def test_compatibility_texts_exact():
    """The six compatibility strings keep their exact character-for-character wording."""
    assert msg("passwords_mismatch") == "Passwords do not match"
    assert msg("email_taken") == "An account with this email already exists."
    assert msg("invalid_datetime") == "Enter a valid date and time"
    assert msg("end_after_start") == "End time must be after start time."
    assert msg("course_code_taken") == "A course with this code already exists."
    assert msg("login_failed") == "Invalid email or password."


def test_msg_formats_placeholders():
    """msg() formats templates with placeholders cleanly."""
    assert msg("between_length", min=2, max=120) == "Must be between 2 and 120 characters."
    assert msg("between_value", min=1, max=500) == "Must be between 1 and 500."
    assert msg("char_counter", count=15, max=200) == "15 of 200 characters"


def test_unknown_key_raises():
    """msg() raises KeyError for an unknown message key."""
    with pytest.raises(KeyError):
        msg("non_existent_key_xyz")


def test_no_message_has_markup_or_trailing_space():
    """No message template contains HTML tags or trailing whitespace."""
    for k in all_keys():
        text = MESSAGES[k]
        assert text == text.strip()
        assert "<" not in text and ">" not in text


def test_js_message_keys_exist():
    """Every msgs.<key> referenced in app/static/js/validation.js exists in MESSAGES."""
    js_path = pathlib.Path("app/static/js/validation.js")
    if not js_path.exists():
        pytest.skip("validation.js not in current working directory")
    js_text = js_path.read_text(encoding="utf-8")
    referenced = set(re.findall(r"msgs\.([a-z0-9_]+)", js_text))
    assert referenced, "Expected message key lookups in validation.js"
    for key in referenced:
        assert key in MESSAGES, f"JS message key {key!r} missing from MESSAGES"


def test_client_config_json_safe_and_small():
    """client_config() serializes cleanly to JSON and is under 8 KB."""
    cfg = client_config()
    encoded = json.dumps(cfg)
    assert len(encoded.encode("utf-8")) < 8192
    assert set(cfg.keys()) == {"limits", "messages", "rules"}


def test_client_config_has_no_secrets():
    """client_config() contains no secret-looking keys or values."""
    encoded = json.dumps(client_config()).lower()
    for forbidden in ("secret_key", "razorpay", "scrypt:", "pbkdf2:", "admin_initial_password"):
        assert forbidden not in encoded


def test_forms_use_limits(app):
    """WTForms Length and NumberRange validators match LIMITS constants."""
    with app.test_request_context():
        reg = RegisterForm()
        len_v = next(v for v in reg.full_name.validators if isinstance(v, Length))
        assert (len_v.min, len_v.max) == (limits.NAME_MIN, limits.NAME_MAX)

        cf = CourseForm()
        code_v = next(v for v in cf.code.validators if isinstance(v, Length))
        assert (code_v.min, code_v.max) == (limits.COURSE_CODE_MIN, limits.COURSE_CODE_MAX)

        sf = SlotForm()
        cap_v = next(v for v in sf.max_capacity.validators if isinstance(v, NumberRange))
        assert (cap_v.min, cap_v.max) == (limits.CAPACITY_MIN, limits.CAPACITY_MAX)

        rf = ReasonForm()
        rsn_v = next(v for v in rf.reason.validators if isinstance(v, Length))
        assert (rsn_v.min, rsn_v.max) == (limits.REASON_MIN, limits.REASON_MAX)


def test_api_schemas_use_same_limits():
    """EXAMINATION_SCHEMA, SLOT_SCHEMA, and CANCEL_SCHEMA match LIMITS."""
    assert EXAMINATION_SCHEMA["name"]["min"] == limits.EXAM_NAME_MIN
    assert EXAMINATION_SCHEMA["name"]["max"] == limits.EXAM_NAME_MAX
    assert EXAMINATION_SCHEMA["description"]["max"] == limits.DESCRIPTION_MAX
    assert EXAMINATION_SCHEMA["duration_minutes"]["min"] == limits.DURATION_MIN
    assert EXAMINATION_SCHEMA["duration_minutes"]["max"] == limits.DURATION_MAX
    assert EXAMINATION_SCHEMA["max_marks"]["min"] == limits.MAX_MARKS_MIN
    assert EXAMINATION_SCHEMA["max_marks"]["max"] == limits.MAX_MARKS_MAX
    assert SLOT_SCHEMA["max_capacity"]["min"] == limits.CAPACITY_MIN
    assert SLOT_SCHEMA["max_capacity"]["max"] == limits.CAPACITY_MAX
    assert CANCEL_SCHEMA["reason"]["min"] == limits.REASON_MIN
    assert CANCEL_SCHEMA["reason"]["max"] == limits.REASON_MAX
