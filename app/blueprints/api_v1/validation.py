"""
Schema validator for JSON request bodies producing field-level 422 errors,
sharing all numeric/length bounds with app.validation.limits.
"""

from datetime import UTC, datetime
from typing import Any

from app.models.examination import EXAM_TYPES
from app.validation import limits, msg


class ApiValidationError(Exception):
    """Raised when a JSON request payload fails schema validation."""

    def __init__(self, fields: dict[str, list[str]], message: str = "Some fields are invalid."):
        super().__init__(message)
        self.fields = fields
        self.message = message


def _has_unsafe_chars(text: str, multiline: bool = False) -> bool:
    for ch in text:
        code = ord(ch)
        if code < 32 or code == 127 or (0x80 <= code <= 0x9F):
            if multiline and ch in ("\n", "\r", "\t"):
                continue
            return True
    return False


def _parse_iso(text: str) -> datetime:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Timestamp must be an ISO 8601 string with a timezone.")
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError("Timestamp must include a timezone offset or Z.")
    return dt.astimezone(UTC).replace(tzinfo=None)


def validate(
    payload: dict[str, Any], schema: dict[str, dict[str, Any]], partial: bool = False
) -> dict[str, Any]:
    """Validate a JSON object against a schema dict and return cleaned values."""
    if not isinstance(payload, dict):
        raise ApiValidationError({"_schema": ["Payload must be a JSON object."]})

    errors: dict[str, list[str]] = {}
    cleaned: dict[str, Any] = {}

    for key in payload:
        if key not in schema:
            errors[key] = ["Unknown field."]

    for field, spec in schema.items():
        required = spec.get("required", False) and not partial
        nullable = spec.get("nullable", False)
        f_type = spec["type"]

        if field not in payload:
            if required:
                errors[field] = [msg("required")]
            continue

        val = payload[field]
        if val is None:
            if nullable:
                cleaned[field] = None
            elif required or not partial:
                errors[field] = [msg("required")]
            continue

        if f_type == "str":
            if not isinstance(val, str):
                errors[field] = ["Must be a string."]
                continue
            if spec.get("strip", True):
                val = val.strip()
            if not val:
                if required:
                    errors[field] = [msg("required")]
                elif nullable:
                    cleaned[field] = None
                else:
                    cleaned[field] = ""
                continue
            if _has_unsafe_chars(val, multiline=spec.get("multiline", False)):
                errors[field] = [msg("unsafe_characters")]
                continue
            mn = spec.get("min")
            mx = spec.get("max")
            if mn is not None and mx is not None and (len(val) < mn or len(val) > mx):
                errors[field] = [msg("between_length", min=mn, max=mx)]
                continue
            if mn is not None and len(val) < mn:
                errors[field] = [msg("min_length", min=mn)]
                continue
            if mx is not None and len(val) > mx:
                errors[field] = [msg("max_length", max=mx)]
                continue
            cleaned[field] = val

        elif f_type == "int":
            if isinstance(val, bool) or not isinstance(val, int):
                errors[field] = ["Must be a whole number."]
                continue
            mn = spec.get("min")
            mx = spec.get("max")
            if mn is not None and mx is not None and (val < mn or val > mx):
                errors[field] = [msg("between_value", min=mn, max=mx)]
                continue
            if mn is not None and val < mn:
                errors[field] = [msg("min_value", min=mn)]
                continue
            if mx is not None and val > mx:
                errors[field] = [msg("max_value", max=mx)]
                continue
            cleaned[field] = val

        elif f_type == "bool":
            if not isinstance(val, bool):
                errors[field] = ["Must be true or false."]
                continue
            cleaned[field] = val

        elif f_type == "enum":
            choices = spec["choices"]
            if not isinstance(val, str) or val not in choices:
                errors[field] = [f"Must be one of: {', '.join(choices)}."]
                continue
            cleaned[field] = val

        elif f_type == "datetime":
            if not isinstance(val, str):
                errors[field] = [
                    "Must be a valid ISO 8601 date and time with a zone, for example 2030-01-10T04:30:00Z."
                ]
                continue
            try:
                cleaned[field] = _parse_iso(val)
            except ValueError:
                errors[field] = [
                    "Must be a valid ISO 8601 date and time with a zone, for example 2030-01-10T04:30:00Z."
                ]

    if errors:
        raise ApiValidationError(errors)

    return cleaned


EXAMINATION_SCHEMA: dict[str, dict[str, Any]] = {
    "course_id": {"type": "int", "required": True, "min": 1},
    "name": {
        "type": "str",
        "required": True,
        "min": limits.EXAM_NAME_MIN,
        "max": limits.EXAM_NAME_MAX,
    },
    "description": {
        "type": "str",
        "required": False,
        "nullable": True,
        "max": limits.DESCRIPTION_MAX,
        "multiline": True,
    },
    "exam_type": {"type": "enum", "required": True, "choices": EXAM_TYPES},
    "duration_minutes": {
        "type": "int",
        "required": True,
        "min": limits.DURATION_MIN,
        "max": limits.DURATION_MAX,
    },
    "max_marks": {
        "type": "int",
        "required": True,
        "min": limits.MAX_MARKS_MIN,
        "max": limits.MAX_MARKS_MAX,
    },
    "slot_creation_start": {"type": "datetime", "required": True},
    "slot_creation_end": {"type": "datetime", "required": True},
    "booking_start": {"type": "datetime", "required": True},
    "booking_end": {"type": "datetime", "required": True},
    "cancellation_deadline": {"type": "datetime", "required": False, "nullable": True},
}

SLOT_SCHEMA: dict[str, dict[str, Any]] = {
    "examination_id": {"type": "int", "required": True, "min": 1},
    "start_at": {"type": "datetime", "required": True},
    "end_at": {"type": "datetime", "required": True},
    "max_capacity": {
        "type": "int",
        "required": True,
        "min": limits.CAPACITY_MIN,
        "max": limits.CAPACITY_MAX,
    },
}

SLOT_UPDATE_SCHEMA: dict[str, dict[str, Any]] = {
    "start_at": {"type": "datetime", "required": False},
    "end_at": {"type": "datetime", "required": False},
    "max_capacity": {
        "type": "int",
        "required": False,
        "min": limits.CAPACITY_MIN,
        "max": limits.CAPACITY_MAX,
    },
}

BOOKING_CREATE_SCHEMA: dict[str, dict[str, Any]] = {
    "slot_id": {"type": "int", "required": True, "min": 1},
}

CANCEL_SCHEMA: dict[str, dict[str, Any]] = {
    "reason": {
        "type": "str",
        "required": True,
        "min": limits.REASON_MIN,
        "max": limits.REASON_MAX,
        "multiline": True,
    },
}
