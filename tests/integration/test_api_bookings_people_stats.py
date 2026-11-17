"""
FILE PURPOSE: Integration tests for bookings, examiners, students, stats, and session endpoints.
"""

from datetime import timedelta

import pytest


@pytest.mark.api
def test_student_book_and_cancel_and_admin_stats(api, make_open_booking_setup, freeze_now):
    exam, slot, examiner, _ = make_open_booking_setup(student_count=0, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    st1 = api("student")
    st2 = api("student")
    admin = api("admin")

    # Book seat
    res_b = st1.post("/api/v1/bookings", data={"slot_id": slot.id})
    assert res_b.status_code == 201
    bk = res_b.get_json()
    assert set(bk.keys()) == {"id", "slot_id", "examination_id", "status", "booked_at"}

    # Duplicate booking -> 409 duplicate_booking
    res_dup = st1.post("/api/v1/bookings", data={"slot_id": slot.id})
    assert res_dup.status_code == 409
    assert res_dup.get_json()["error"]["code"] == "duplicate_booking"

    # Full slot -> 409 slot_full
    res_full = st2.post("/api/v1/bookings", data={"slot_id": slot.id})
    assert res_full.status_code == 409
    assert res_full.get_json()["error"]["code"] == "slot_full"

    # Admin stats summary matches 6 integer keys
    res_stats = admin.get("/api/v1/stats/summary")
    assert res_stats.status_code == 200
    stats = res_stats.get_json()
    assert set(stats.keys()) == {
        "courses",
        "examinations",
        "examiners",
        "students",
        "slots",
        "bookings",
    }
    assert stats["bookings"] >= 1

    # Student cancels own booking -> 200 cancelled
    res_del = st1.delete(f"/api/v1/bookings/{bk['id']}")
    assert res_del.status_code == 200
    assert res_del.get_json() == {"id": bk["id"], "status": "cancelled"}
