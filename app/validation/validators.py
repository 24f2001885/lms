"""
Reusable server-side WTForms validators and html_attrs helper so browser HTML5
attributes and server rules come from a single definition.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import current_app, has_app_context
from wtforms.validators import (
    DataRequired,
    Email,
    InputRequired,
    Length,
    NumberRange,
    Regexp,
    ValidationError,
)

from app.services import windows
from app.validation import limits
from app.validation.messages import msg


def strip_filter(value: Any) -> Any:
    """Trim leading and trailing whitespace on string inputs."""
    if isinstance(value, str):
        return value.strip()
    return value


def upper_strip_filter(value: Any) -> Any:
    """Trim and uppercase code/roll inputs."""
    if isinstance(value, str):
        return value.strip().upper()
    return value


def lower_strip_filter(value: Any) -> Any:
    """Trim and lowercase email inputs."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


class SafeText:
    """Rejects ASCII/Unicode control characters (allows newline/tab only when multiline=True)."""

    def __init__(self, multiline: bool = False, message: str | None = None):
        self.multiline = multiline
        self.message = message or msg("unsafe_characters")

    def __call__(self, form: Any, field: Any) -> None:
        data = field.data
        if not data or not isinstance(data, str):
            return
        for ch in data:
            code = ord(ch)
            if code < 32 or code == 127 or (0x80 <= code <= 0x9F):
                if self.multiline and ch in ("\n", "\r", "\t"):
                    continue
                raise ValidationError(self.message)


class PhoneChars:
    """Validates phone strings against PHONE_PATTERN."""

    def __init__(self, message: str | None = None):
        self.pattern = re.compile(limits.PHONE_PATTERN)
        self.message = message or msg("phone_chars")

    def __call__(self, form: Any, field: Any) -> None:
        data = field.data
        if not data:
            return
        if not isinstance(data, str) or not self.pattern.match(data):
            raise ValidationError(self.message)


class RollNumber:
    """Validates student roll numbers against ROLL_PATTERN."""

    def __init__(self, message: str | None = None):
        self.pattern = re.compile(limits.ROLL_PATTERN)
        self.message = message or msg("pattern_mismatch", title=limits.ROLL_TITLE)

    def __call__(self, form: Any, field: Any) -> None:
        data = field.data
        if not data:
            return
        if not isinstance(data, str) or not self.pattern.match(data):
            raise ValidationError(self.message)


class ValidEmail(Email):
    """Validate email syntax, allowing .test and .local domains during testing."""

    def __init__(self, message: str | None = None):
        super().__init__(message=message or msg("invalid_email"))

    def __call__(self, form: Any, field: Any) -> None:
        value = (field.data or "").strip()
        is_testing = has_app_context() and bool(current_app.config.get("TESTING", False))
        if is_testing and "@" in value:
            local, domain = value.rsplit("@", 1)
            if domain.lower().endswith(".local"):
                value = f"{local}@{domain[:-6]}.com"
            elif domain.lower().endswith(".test"):
                value = f"{local}@{domain[:-5]}.com"
        try:
            import email_validator

            email_validator.validate_email(
                value,
                check_deliverability=False,
                test_environment=is_testing,
            )
        except Exception as exc:
            raise ValidationError(self.message) from exc


class CourseCodeChars:
    """Validates course codes against COURSE_CODE_PATTERN."""

    def __init__(self, message: str | None = None):
        self.pattern = re.compile(limits.COURSE_CODE_PATTERN)
        self.message = message or msg("pattern_mismatch", title=limits.COURSE_CODE_TITLE)

    def __call__(self, form: Any, field: Any) -> None:
        data = field.data
        if not data:
            return
        if not isinstance(data, str) or not self.pattern.match(data):
            raise ValidationError(self.message)


class StrongPassword:
    """Enforces min/max password length, at least one letter, and at least one digit."""

    def __init__(self, min_len: int = limits.PASSWORD_MIN, max_len: int = limits.PASSWORD_MAX):
        self.min_len = min_len
        self.max_len = max_len

    def __call__(self, form: Any, field: Any) -> None:
        data = field.data
        if data is None or data == "":
            return
        if not isinstance(data, str):
            raise ValidationError(msg("password_too_short", min=self.min_len))
        if len(data) < self.min_len:
            raise ValidationError(msg("password_too_short", min=self.min_len))
        if len(data) > self.max_len:
            raise ValidationError(msg("password_too_long", max=self.max_len))
        if not any(ch.isalpha() for ch in data):
            raise ValidationError(msg("password_no_letter"))
        if not any(ch.isdigit() for ch in data):
            raise ValidationError(msg("password_no_digit"))


class MatchesField:
    """Checks that field value equals another field on the same form."""

    def __init__(self, other_name: str, message: str | None = None):
        self.other_name = other_name
        self.message = message or msg("passwords_mismatch")

    def __call__(self, form: Any, field: Any) -> None:
        if field.data is None or field.data == "":
            return
        other = form._fields.get(self.other_name)
        if other is None or field.data != other.data:
            raise ValidationError(self.message)


class DateTimeLocal:
    """Parses HTML datetime-local strings via windows.from_local_input."""

    def __init__(self, message: str | None = None):
        self.message = message or msg("invalid_datetime")

    def __call__(self, form: Any, field: Any) -> None:
        data = field.data
        if data is None or data == "":
            return
        if not isinstance(data, str):
            raise ValidationError(self.message)
        try:
            windows.from_local_input(data)
        except (ValueError, TypeError) as exc:
            raise ValidationError(self.message) from exc


class EndAfterStart:
    """Ensures an end datetime-local field is strictly after a start field."""

    def __init__(self, start_field: str = "start_at", message: str | None = None):
        self.start_field = start_field
        self.message = message or msg("end_after_start")

    def __call__(self, form: Any, field: Any) -> None:
        if not field.data:
            return
        other = form._fields.get(self.start_field)
        if other is None or not other.data:
            return
        try:
            start_dt = windows.from_local_input(other.data)
            end_dt = windows.from_local_input(field.data)
        except (ValueError, TypeError):
            return
        if end_dt <= start_dt:
            raise ValidationError(self.message)


class DecimalPlaces:
    """Checks that a numeric/Decimal input has at most `places` decimal places."""

    def __init__(self, places: int = limits.DECIMAL_PLACES, message: str | None = None):
        self.places = places
        self.message = message or msg("too_many_decimals", places=places)

    def __call__(self, form: Any, field: Any) -> None:
        val = field.data
        if val is None or val == "":
            return
        raw_list = getattr(field, "raw_data", None)
        if raw_list and isinstance(raw_list[0], str) and raw_list[0].strip():
            raw_str = raw_list[0].strip()
            try:
                dec = Decimal(raw_str)
            except InvalidOperation as exc:
                raise ValidationError(msg("invalid_number")) from exc
        elif isinstance(val, Decimal):
            dec = val
        else:
            try:
                dec = Decimal(str(val))
            except InvalidOperation as exc:
                raise ValidationError(msg("invalid_number")) from exc
        exp = dec.normalize().as_tuple().exponent if dec != 0 else 0
        actual_exp = dec.as_tuple().exponent
        if (
            isinstance(actual_exp, int)
            and -actual_exp > self.places
            and isinstance(exp, int)
            and -exp > self.places
        ):
            raise ValidationError(self.message)
        if isinstance(actual_exp, int) and -actual_exp > self.places:
            raise ValidationError(self.message)


class ScoreRange:
    """Ensures 0 <= score <= max_score with a message naming the criterion maximum."""

    def __init__(self, max_score: Decimal | float | int, criterion_name: str | None = None):
        self.max_score = Decimal(str(max_score))
        self.criterion_name = criterion_name

    def __call__(self, form: Any, field: Any) -> None:
        val = field.data
        if val is None or val == "":
            return
        try:
            dec = Decimal(str(val))
        except InvalidOperation as exc:
            raise ValidationError(msg("invalid_number")) from exc
        if dec < Decimal("0") or dec > self.max_score:
            max_disp = (
                f"{self.max_score.normalize():f}"
                if self.max_score == self.max_score.to_integral()
                else f"{self.max_score:.2f}"
            )
            if self.criterion_name:
                raise ValidationError(
                    f"Score for {self.criterion_name} must be between 0 and {max_disp}."
                )
            raise ValidationError(msg("between_value", min=0, max=max_disp))


class ExaminationWindows:
    """
    Validates the four examination window ordering rules with the exact P3 messages:
    1. Slot creation end must be after Slot creation start.
    2. Booking end must be after Booking start.
    3. Slot creation end must not be after Booking start.
    4. Cancellation deadline must not be before Booking start.
    """

    def __call__(self, form: Any, field: Any = None) -> bool:
        ok = True
        parsed: dict[str, Any] = {}
        for fname in (
            "slot_creation_start",
            "slot_creation_end",
            "booking_start",
            "booking_end",
            "cancellation_deadline",
        ):
            f_obj = form._fields.get(fname)
            if f_obj and f_obj.data:
                try:
                    parsed[fname] = windows.from_local_input(f_obj.data)
                except (ValueError, TypeError):
                    parsed[fname] = None

        sc_start = parsed.get("slot_creation_start")
        sc_end = parsed.get("slot_creation_end")
        bk_start = parsed.get("booking_start")
        bk_end = parsed.get("booking_end")
        cancel_dl = parsed.get("cancellation_deadline")

        def _add_err(field_obj: Any, err_msg: str) -> None:
            if not hasattr(field_obj, "errors") or field_obj.errors is None:
                field_obj.errors = [err_msg]
            elif isinstance(field_obj.errors, list):
                if err_msg not in field_obj.errors:
                    field_obj.errors.append(err_msg)
            else:
                field_obj.errors = list(field_obj.errors)
                if err_msg not in field_obj.errors:
                    field_obj.errors.append(err_msg)

        if sc_start and sc_end and sc_end <= sc_start:
            err = msg(
                "rule_after",
                label=form.slot_creation_end.label.text,
                other=form.slot_creation_start.label.text,
            )
            _add_err(form.slot_creation_end, err)
            ok = False

        if bk_start and bk_end and bk_end <= bk_start:
            err = msg(
                "rule_after",
                label=form.booking_end.label.text,
                other=form.booking_start.label.text,
            )
            _add_err(form.booking_end, err)
            ok = False

        if sc_end and bk_start and sc_end > bk_start:
            err = msg(
                "rule_not_after",
                label=form.slot_creation_end.label.text,
                other=form.booking_start.label.text,
            )
            _add_err(form.slot_creation_end, err)
            ok = False

        if cancel_dl and bk_start and cancel_dl < bk_start:
            err = msg(
                "rule_not_before",
                label=form.cancellation_deadline.label.text,
                other=form.booking_start.label.text,
            )
            _add_err(form.cancellation_deadline, err)
            ok = False

        return ok


def html_attrs(
    *,
    min_len: int | None = None,
    max_len: int | None = None,
    minimum: int | float | str | Decimal | None = None,
    maximum: int | float | str | Decimal | None = None,
    step: int | float | str | None = None,
    pattern: str | None = None,
    title: str | None = None,
    inputmode: str | None = None,
    autocomplete: str | None = None,
    rule: str | None = None,
    strength_target: str | None = None,
    field_type: str | None = None,
) -> dict[str, str]:
    """Build render_kw attributes for WTForms fields from limits.py constants."""
    attrs: dict[str, str] = {}
    if min_len is not None:
        attrs["minlength"] = str(min_len)
    if max_len is not None:
        attrs["maxlength"] = str(max_len)
    if minimum is not None:
        attrs["min"] = str(minimum)
    if maximum is not None:
        attrs["max"] = str(maximum)
    if step is not None:
        attrs["step"] = str(step)
    if pattern is not None:
        # Strip ^ and $ for HTML5 pattern attribute if desired, or keep anchored
        attrs["pattern"] = str(pattern)
    if title is not None:
        attrs["title"] = str(title)
    if inputmode is not None:
        attrs["inputmode"] = str(inputmode)
    if autocomplete is not None:
        attrs["autocomplete"] = str(autocomplete)
    if rule is not None:
        attrs["data-rule"] = str(rule)
    if strength_target is not None:
        attrs["data-strength-target"] = str(strength_target)
    if field_type is not None:
        attrs["type"] = str(field_type)
    return attrs


def describe(field: Any) -> dict[str, Any]:
    """
    Introspects a bound WTForms field and returns its effective constraints
    (validators + render_kw) so tests can verify parity between server validators
    and HTML5 attributes.
    """
    render_kw = dict(getattr(field, "render_kw", None) or {})
    info: dict[str, Any] = {
        "name": field.name,
        "required": False,
        "minlength": None,
        "maxlength": None,
        "min": None,
        "max": None,
        "step": render_kw.get("step"),
        "pattern": None,
        "title": render_kw.get("title"),
        "rule": render_kw.get("data-rule"),
        "autocomplete": render_kw.get("autocomplete"),
        "inputmode": render_kw.get("inputmode"),
        "render_kw": render_kw,
    }
    for v in getattr(field, "validators", []):
        if isinstance(v, DataRequired | InputRequired):
            info["required"] = True
        elif isinstance(v, Length):
            if v.min is not None and v.min >= 0:
                info["minlength"] = str(v.min)
            if v.max is not None and v.max >= 0:
                info["maxlength"] = str(v.max)
        elif isinstance(v, StrongPassword):
            info["minlength"] = str(v.min_len)
            info["maxlength"] = str(v.max_len)
        elif isinstance(v, NumberRange):
            if v.min is not None:
                info["min"] = str(v.min)
            if v.max is not None:
                info["max"] = str(v.max)
        elif isinstance(v, ScoreRange):
            info["min"] = "0"
            max_s = v.max_score
            info["max"] = f"{max_s.normalize():f}" if max_s == max_s.to_integral() else str(max_s)
        elif isinstance(v, PhoneChars | RollNumber | CourseCodeChars):
            info["pattern"] = v.pattern.pattern
        elif isinstance(v, Regexp):
            info["pattern"] = v.regex.pattern
    return info
