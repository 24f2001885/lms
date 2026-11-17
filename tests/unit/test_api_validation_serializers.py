"""
FILE PURPOSE: Unit tests for JSON validator, helpers, and role-scoped serializers.
"""

import json
import re
from datetime import datetime

import pytest

from app.blueprints.api_v1.common import (
    iso,
    page_args,
    parse_iso,
    translate_app_error,
)
from app.blueprints.api_v1.serializers import (
    FORBIDDEN_KEYS,
    booking_to_dict,
    examination_to_dict,
    examiner_to_dict,
    slot_to_dict,
    student_to_dict,
    user_to_dict,
)
from app.blueprints.api_v1.validation import (
    BOOKING_CREATE_SCHEMA,
    CANCEL_SCHEMA,
    EXAMINATION_SCHEMA,
    SLOT_SCHEMA,
    ApiValidationError,
    validate,
)
from app.errors import ERROR_HTTP_STATUS, AppError


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def test_required_fields_all_reported_at_once():
    with pytest.raises(ApiValidationError) as exc:
        validate({}, SLOT_SCHEMA)
    assert set(exc.value.fields.keys()) == {"examination_id", "start_at", "end_at", "max_capacity"}
    for msgs in exc.value.fields.values():
        assert msgs == ["This field is required."]


def test_unknown_field_rejected():
    with pytest.raises(ApiValidationError) as exc:
        validate({"slot_id": 1, "role": "admin"}, BOOKING_CREATE_SCHEMA)
    assert exc.value.fields["role"] == ["Unknown field."]


def test_partial_ignores_required():
    cleaned = validate({"name": "  Updated Exam  "}, EXAMINATION_SCHEMA, partial=True)
    assert cleaned == {"name": "Updated Exam"}


def test_int_rejects_bool_string_float():
    for bad in ("5", True, False, 5.5):
        with pytest.raises(ApiValidationError) as exc:
            validate({"slot_id": bad}, BOOKING_CREATE_SCHEMA)
        assert exc.value.fields["slot_id"] == ["Must be a whole number."]

    assert validate({"slot_id": 5}, BOOKING_CREATE_SCHEMA) == {"slot_id": 5}


def test_str_strip_and_length_bounds():
    with pytest.raises(ApiValidationError):
        validate({"name": "A"}, EXAMINATION_SCHEMA, partial=True)
    with pytest.raises(ApiValidationError):
        validate({"name": "X" * 151}, EXAMINATION_SCHEMA, partial=True)
    assert validate({"name": "  Valid Name  "}, EXAMINATION_SCHEMA, partial=True) == {
        "name": "Valid Name"
    }


def test_enum_choices_message():
    with pytest.raises(ApiValidationError) as exc:
        validate({"exam_type": "oral"}, EXAMINATION_SCHEMA, partial=True)
    assert "Must be one of:" in exc.value.fields["exam_type"][0]


def test_datetime_requires_zone():
    with pytest.raises(ApiValidationError) as exc:
        validate({"start_at": "2030-01-10T10:00:00"}, SLOT_SCHEMA, partial=True)
    assert "ISO 8601" in exc.value.fields["start_at"][0]


def test_datetime_converted_to_naive_utc():
    cleaned = validate({"start_at": "2030-01-10T10:00:00+05:30"}, SLOT_SCHEMA, partial=True)
    assert cleaned["start_at"] == datetime(2030, 1, 10, 4, 30)
    assert cleaned["start_at"].tzinfo is None


def test_cancel_schema_reason_length():
    with pytest.raises(ApiValidationError):
        validate({"reason": "no"}, CANCEL_SCHEMA)
    with pytest.raises(ApiValidationError):
        validate({"reason": "x" * 201}, CANCEL_SCHEMA)
    assert validate({"reason": "Valid reason"}, CANCEL_SCHEMA) == {"reason": "Valid reason"}


def test_iso_and_parse_iso_helpers():
    dt = datetime(2030, 1, 10, 4, 30)
    assert iso(dt) == "2030-01-10T04:30:00Z"
    assert iso(None) is None
    assert parse_iso("2030-01-10T10:00:00+05:30") == dt
    with pytest.raises(ValueError):
        parse_iso("2030-01-10T10:00:00")


def test_page_args_defaults_clamp_and_errors(app):
    with app.app_context():
        assert page_args({}) == (1, 20)
        assert page_args({"per_page": "500"}) == (1, 100)
        with pytest.raises(ApiValidationError):
            page_args({"page": "abc"})
        with pytest.raises(ApiValidationError):
            page_args({"page": "0"})


def test_translate_app_error_status_map(app):
    with app.app_context():
        for code, expected_status in ERROR_HTTP_STATUS.items():
            resp, status = translate_app_error(AppError(code, "Test message"))
            assert status == expected_status
            payload = resp.get_json()
            assert payload["error"]["code"] == code
            assert payload["error"]["message"] == "Test message"


def test_serializers_role_scoping_and_safety(
    app, db_session, admin, student, make_open_booking_setup
):
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=3)
    from datetime import timedelta

    from app.services import booking_engine

    booking = booking_engine.book_slot(
        students[0].id, slot.id, now=exam.booking_start + timedelta(hours=1)
    )

    # Examination serializer
    st_exam = examination_to_dict(exam, student)
    adm_exam = examination_to_dict(exam, admin)
    assert "is_deleted" not in st_exam
    assert "is_deleted" in adm_exam

    # Slot serializer
    st_slot = slot_to_dict(slot, student)
    ex_slot = slot_to_dict(slot, examiner)
    assert "examiner_id" not in st_slot
    assert ex_slot["examiner_id"] == examiner.id

    # Booking serializer
    st_bk = booking_to_dict(booking, student)
    ex_bk = booking_to_dict(booking, examiner)
    adm_bk = booking_to_dict(booking, admin)
    assert "student_id" not in st_bk
    assert "student_name" in ex_bk and "rescheduled_from_slot_id" not in ex_bk
    assert "rescheduled_from_slot_id" in adm_bk

    all_outputs = [
        st_exam,
        adm_exam,
        st_slot,
        ex_slot,
        st_bk,
        ex_bk,
        adm_bk,
        examiner_to_dict(examiner),
        student_to_dict(student),
        user_to_dict(admin),
    ]
    for out in all_outputs:
        assert not (set(_walk_keys(out)) & FORBIDDEN_KEYS)
        # Ensure pure JSON-serializable primitives
        json.dumps(out)

    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", st_exam["booking_start"])
