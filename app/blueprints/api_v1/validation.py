"""
FILE PURPOSE: Lightweight schema validator for JSON request payloads (mass-assignment safe, 422 field errors).
"""

from datetime import UTC, datetime
from typing import Any

from app.models.examination import EXAM_TYPES


class ApiValidationError(Exception):
    def __init__(self, fields: dict[str, list[str]]):
        super().__init__("Validation failed")
        self.fields = fields


def _parse_iso_utc(text: str) -> datetime:
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError("No timezone")
    return dt.astimezone(UTC).replace(tzinfo=None)


def validate(
    payload: dict[str, Any],
    schema: dict[str, dict[str, Any]],
    partial: bool = False,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ApiValidationError({"_schema": ["Payload must be a JSON object."]})

    errors: dict[str, list[str]] = {}
    cleaned: dict[str, Any] = {}

    # Reject unknown fields (mass-assignment protection)
    for key in payload:
        if key not in schema:
            errors[key] = ["Unknown field."]

    for field, spec in schema.items():
        required = spec.get("required", False) and not partial
        nullable = spec.get("nullable", False)
        ftype = spec["type"]

        if field not in payload:
            if required:
                errors[field] = ["This field is required."]
            continue

        val = payload[field]
        if val is None:
            if nullable:
                cleaned[field] = None
            else:
                errors[field] = ["This field is required." if required else "Cannot be null."]
            continue

        if ftype == "str":
            if not isinstance(val, str):
                errors[field] = ["Must be a text string."]
                continue
            if spec.get("strip", True):
                val = val.strip()
            min_len = spec.get("min")
            max_len = spec.get("max")
            if required and len(val) == 0:
                errors[field] = ["This field is required."]
                continue
            if min_len is not None and len(val) < min_len:
                errors[field] = [f"Must be at least {min_len} characters."]
                continue
            if max_len is not None and len(val) > max_len:
                errors[field] = [f"Must be at most {max_len} characters."]
                continue
            cleaned[field] = val

        elif ftype == "int":
            if isinstance(val, bool) or not isinstance(val, int):
                errors[field] = ["Must be a whole number."]
                continue
            min_val = spec.get("min")
            max_val = spec.get("max")
            if min_val is not None and val < min_val:
                errors[field] = [f"Must be at least {min_val}."]
                continue
            if max_val is not None and val > max_val:
                errors[field] = [f"Must be at most {max_val}."]
                continue
            cleaned[field] = val

        elif ftype == "bool":
            if not isinstance(val, bool):
                errors[field] = ["Must be true or false."]
                continue
            cleaned[field] = val

        elif ftype == "enum":
            choices = spec.get("choices", ())
            if not isinstance(val, str) or val not in choices:
                joined = ", ".join(str(c) for c in choices)
                errors[field] = [f"Must be one of: {joined}."]
                continue
            cleaned[field] = val

        elif ftype == "datetime":
            if not isinstance(val, str):
                errors[field] = [
                    "Must be a valid ISO 8601 date and time with a zone, for example 2030-01-10T04:30:00Z."
                ]
                continue
            try:
                cleaned[field] = _parse_iso_utc(val)
            except ValueError:
                errors[field] = [
                    "Must be a valid ISO 8601 date and time with a zone, for example 2030-01-10T04:30:00Z."
                ]
                continue

    if errors:
        raise ApiValidationError(errors)

    return cleaned


EXAMINATION_SCHEMA: dict[str, dict[str, Any]] = {
    "course_id": {"type": "int", "required": True, "min": 1},
    "name": {"type": "str", "required": True, "min": 2, "max": 150},
    "description": {"type": "str", "required": False, "nullable": True, "max": 2000},
    "exam_type": {"type": "enum", "required": True, "choices": EXAM_TYPES},
    "duration_minutes": {"type": "int", "required": True, "min": 1, "max": 1440},
    "max_marks": {"type": "int", "required": True, "min": 1, "max": 1000},
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
    "max_capacity": {"type": "int", "required": True, "min": 1, "max": 500},
}

SLOT_UPDATE_SCHEMA: dict[str, dict[str, Any]] = {
    "start_at": {"type": "datetime", "required": False},
    "end_at": {"type": "datetime", "required": False},
    "max_capacity": {"type": "int", "required": False, "min": 1, "max": 500},
}

BOOKING_CREATE_SCHEMA: dict[str, dict[str, Any]] = {
    "slot_id": {"type": "int", "required": True, "min": 1},
}

CANCEL_SCHEMA: dict[str, dict[str, Any]] = {
    "reason": {"type": "str", "required": False, "nullable": True, "min": 3, "max": 200},
}
