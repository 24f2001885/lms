"""
Unit tests for every custom validator and html_attrs in app.validation.validators (P9).
"""

from decimal import Decimal

import pytest
from werkzeug.datastructures import MultiDict
from wtforms import DecimalField, IntegerField, PasswordField, StringField
from wtforms import Form as _WTForm
from wtforms.validators import DataRequired, NumberRange, Optional

from app.validation import (
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
    describe,
    html_attrs,
    limits,
    msg,
)


class Form(_WTForm):
    def __init__(self, *args, **kwargs):
        if "data" in kwargs and not args and "formdata" not in kwargs:
            super().__init__(MultiDict(kwargs.pop("data")), **kwargs)
        else:
            super().__init__(*args, **kwargs)


pytestmark = pytest.mark.validation


def test_rejects_control_chars():
    class F(Form):
        txt = StringField("Text", [SafeText(multiline=False)])

    for bad in ("hello\x00world", "line1\nline2", "tab\there", "bell\x07"):
        f = F(data={"txt": bad})
        assert not f.validate()
        assert msg("unsafe_characters") in f.txt.errors


def test_multiline_allows_newlines():
    class F(Form):
        txt = StringField("Text", [SafeText(multiline=True)])

    f = F(data={"txt": "Line 1\nLine 2\r\n\tIndented"})
    assert f.validate()

    f_bad = F(data={"txt": "Line 1\x00Null"})
    assert not f_bad.validate()


def test_unicode_letters_allowed():
    class F(Form):
        txt = StringField("Text", [SafeText(multiline=False)])

    f = F(data={"txt": "Abhishek Pathak — Café Zürich"})
    assert f.validate()


@pytest.mark.parametrize(
    "pwd,expected_key",
    [
        ("Short1", "password_too_short"),
        ("a" * 129 + "1", "password_too_long"),
        ("1234567890", "password_no_letter"),
        ("abcdefghij", "password_no_digit"),
        ("Passw0rdOK", None),
        ("A" * 127 + "1", None),
    ],
)
def test_strong_password_each_message(pwd, expected_key):
    class F(Form):
        password = PasswordField("Password", [StrongPassword()])

    f = F(data={"password": pwd})
    if expected_key is None:
        assert f.validate()
    else:
        assert not f.validate()
        expected = msg(expected_key, min=limits.PASSWORD_MIN, max=limits.PASSWORD_MAX)
        assert f.password.errors == [expected]


def test_matches_field_exact_message_text():
    class F(Form):
        password = PasswordField("Password")
        confirm = PasswordField("Confirm", [MatchesField("password")])

    f_bad = F(data={"password": "Passw0rd1", "confirm": "Passw0rd2"})
    assert not f_bad.validate()
    assert f_bad.confirm.errors == ["Passwords do not match"]

    f_ok = F(data={"password": "Passw0rd1", "confirm": "Passw0rd1"})
    assert f_ok.validate()


def test_datetime_local_valid_invalid(app):
    class F(Form):
        dt = StringField("Start", [DateTimeLocal()])

    with app.app_context():
        assert F(data={"dt": "2030-01-10T10:00"}).validate()
        f_bad = F(data={"dt": "2030-13-40T25:61"})
        assert not f_bad.validate()
        assert f_bad.dt.errors == ["Enter a valid date and time"]


def test_end_after_start_equal_and_reversed(app):
    class F(Form):
        start_at = StringField("Start", [DateTimeLocal()])
        end_at = StringField("End", [DateTimeLocal(), EndAfterStart("start_at")])

    with app.app_context():
        f_eq = F(data={"start_at": "2030-01-10T10:00", "end_at": "2030-01-10T10:00"})
        assert not f_eq.validate()
        assert "End time must be after start time." in f_eq.end_at.errors

        f_rev = F(data={"start_at": "2030-01-10T11:00", "end_at": "2030-01-10T10:00"})
        assert not f_rev.validate()

        f_ok = F(data={"start_at": "2030-01-10T10:00", "end_at": "2030-01-10T11:00"})
        assert f_ok.validate()


def test_examination_windows_four_messages_unchanged(app):
    class F(Form):
        slot_creation_start = StringField("Slot creation start")
        slot_creation_end = StringField("Slot creation end")
        booking_start = StringField("Booking start")
        booking_end = StringField("Booking end")
        cancellation_deadline = StringField("Cancellation deadline")

    with app.app_context():
        # 1. Creation end <= creation start
        f1 = F(
            data={
                "slot_creation_start": "2030-01-05T10:00",
                "slot_creation_end": "2030-01-05T10:00",
                "booking_start": "2030-01-10T10:00",
                "booking_end": "2030-01-15T10:00",
                "cancellation_deadline": "2030-01-15T10:00",
            }
        )
        assert not ExaminationWindows()(f1)
        assert "Slot creation end must be after Slot creation start." in f1.slot_creation_end.errors

        # 2. Booking end <= booking start
        f2 = F(
            data={
                "slot_creation_start": "2030-01-01T10:00",
                "slot_creation_end": "2030-01-05T10:00",
                "booking_start": "2030-01-10T10:00",
                "booking_end": "2030-01-09T10:00",
                "cancellation_deadline": "2030-01-10T10:00",
            }
        )
        assert not ExaminationWindows()(f2)
        assert "Booking end must be after Booking start." in f2.booking_end.errors

        # 3. Creation end > booking start
        f3 = F(
            data={
                "slot_creation_start": "2030-01-01T10:00",
                "slot_creation_end": "2030-01-11T10:00",
                "booking_start": "2030-01-10T10:00",
                "booking_end": "2030-01-15T10:00",
                "cancellation_deadline": "2030-01-15T10:00",
            }
        )
        assert not ExaminationWindows()(f3)
        assert "Slot creation end must not be after Booking start." in f3.slot_creation_end.errors

        # 4. Cancellation deadline < booking start
        f4 = F(
            data={
                "slot_creation_start": "2030-01-01T10:00",
                "slot_creation_end": "2030-01-05T10:00",
                "booking_start": "2030-01-10T10:00",
                "booking_end": "2030-01-15T10:00",
                "cancellation_deadline": "2030-01-09T10:00",
            }
        )
        assert not ExaminationWindows()(f4)
        assert (
            "Cancellation deadline must not be before Booking start."
            in f4.cancellation_deadline.errors
        )


def test_decimal_places_boundaries():
    class F(Form):
        val = DecimalField("Val", [DecimalPlaces(2)])

    assert F(data={"val": Decimal("12")}).validate()
    assert F(data={"val": Decimal("12.5")}).validate()
    assert F(data={"val": Decimal("12.55")}).validate()
    f_bad = F(data={"val": Decimal("12.555")})
    assert not f_bad.validate()
    assert msg("too_many_decimals", places=2) in f_bad.val.errors


def test_score_range_boundaries_and_message_names_max():
    class F(Form):
        score = DecimalField("Score", [ScoreRange(Decimal("40"), criterion_name="Concept")])

    assert F(data={"score": Decimal("0")}).validate()
    assert F(data={"score": Decimal("40")}).validate()
    f_low = F(data={"score": Decimal("-0.01")})
    assert not f_low.validate()
    f_high = F(data={"score": Decimal("40.01")})
    assert not f_high.validate()
    assert "40" in f_high.score.errors[0]
    assert "Concept" in f_high.score.errors[0]


def test_capacity_range_via_numberrange():
    class F(Form):
        cap = IntegerField(
            "Capacity",
            [
                NumberRange(
                    min=limits.CAPACITY_MIN,
                    max=limits.CAPACITY_MAX,
                    message=msg("between_value", min=limits.CAPACITY_MIN, max=limits.CAPACITY_MAX),
                )
            ],
        )

    assert not F(data={"cap": 0}).validate()
    assert F(data={"cap": 1}).validate()
    assert F(data={"cap": 500}).validate()
    assert not F(data={"cap": 501}).validate()


def test_phone_chars():
    class F(Form):
        phone = StringField("Phone", [Optional(), PhoneChars()])

    assert F(data={"phone": "+91 98765-43210"}).validate()
    f_bad = F(data={"phone": "98765abc"})
    assert not f_bad.validate()
    assert f_bad.phone.errors == [msg("phone_chars")]


def test_roll_number_pattern():
    class F(Form):
        roll = StringField("Roll", [Optional(), RollNumber()])

    assert F(data={"roll": "CS-2026/042"}).validate()
    assert not F(data={"roll": "CS 2026!"}).validate()


def test_course_code_pattern():
    class F(Form):
        code = StringField("Code", [CourseCodeChars()])

    assert F(data={"code": "CS_101-A"}).validate()
    assert not F(data={"code": "CS 101"}).validate()


def test_html_attrs_omits_none():
    attrs = html_attrs(min_len=2, max_len=120, minimum=None)
    assert attrs == {"minlength": "2", "maxlength": "120"}


def test_describe_matches_render_kw():
    class F(Form):
        name = StringField(
            "Name",
            validators=[DataRequired(), PhoneChars()],
            render_kw=html_attrs(min_len=2, max_len=20, pattern=limits.PHONE_PATTERN),
        )

    f = F()
    d = describe(f.name)
    assert d["required"] is True
    assert d["pattern"] == limits.PHONE_PATTERN
    assert d["render_kw"]["minlength"] == "2"
    assert d["render_kw"]["maxlength"] == "20"
