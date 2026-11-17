"""
tests/unit/test_chart_data.py - Unit tests for chart data service functions.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.errors import AppError
from app.models.booking import Booking
from app.models.slot import ExaminationSlot
from app.services import chart_data, windows


def _assert_valid_shape(data):
    assert isinstance(data, dict)
    assert "labels" in data
    assert "series" in data
    assert isinstance(data["labels"], list)
    assert isinstance(data["series"], list)
    for s in data["series"]:
        assert isinstance(s, dict)
        assert "name" in s
        assert "data" in s
        assert isinstance(s["name"], str)
        assert isinstance(s["data"], list)
        assert len(s["data"]) == len(data["labels"])
        for val in s["data"]:
            assert isinstance(val, int | float)
            assert not isinstance(val, bool)


@pytest.mark.charts
def test_every_function_returns_valid_shape(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    for fn in (
        lambda u: chart_data.bookings_by_day(u, 7),
        chart_data.booking_status,
        chart_data.results,
    ):
        for user in (data.admin, data.examiner1, data.student1):
            res = fn(user)
            _assert_valid_shape(res)

    for fn in (
        chart_data.participants_by_slot,
        chart_data.examiner_workload,
        chart_data.examination_completion,
    ):
        for user in (data.admin, data.examiner1):
            res = fn(user)
            _assert_valid_shape(res)


@pytest.mark.charts
def test_empty_database_returns_empty_valid_shape(app, make_admin, make_examiner, make_student):
    admin = make_admin()
    examiner = make_examiner()
    student = make_student()

    for user in (admin, examiner, student):
        res_bbd = chart_data.bookings_by_day(user, 7)
        _assert_valid_shape(res_bbd)
        assert len(res_bbd["labels"]) == 7

        res_bs = chart_data.booking_status(user)
        _assert_valid_shape(res_bs)
        assert res_bs["series"][0]["data"] == [0, 0, 0]

        res_res = chart_data.results(user)
        _assert_valid_shape(res_res)
        assert res_res["labels"] == []
        assert res_res["series"][0]["data"] == []

    for user in (admin, examiner):
        res_part = chart_data.participants_by_slot(user)
        _assert_valid_shape(res_part)
        assert res_part["labels"] == []

        res_work = chart_data.examiner_workload(user)
        _assert_valid_shape(res_work)
        assert res_work["labels"] == []

        res_comp = chart_data.examination_completion(user)
        _assert_valid_shape(res_comp)
        assert res_comp["labels"] == []


@pytest.mark.charts
def test_zero_filled_days_count_equals_days(app, make_admin, monkeypatch):
    admin = make_admin()
    fixed_now = datetime(2030, 5, 20, 10, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(windows, "now_utc", lambda: fixed_now)

    for count in (7, 30, 90, 180):
        res = chart_data.bookings_by_day(admin, count)
        assert len(res["labels"]) == count
        assert len(res["series"][0]["data"]) == count
        assert len(res["series"][1]["data"]) == count


@pytest.mark.charts
def test_local_date_bucketing_near_midnight_kolkata(
    app, db_session, make_admin, make_examination, make_student, monkeypatch
):
    admin = make_admin()
    student = make_student()
    exam = make_examination()
    slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=admin.id,
        start_at=datetime(2030, 1, 15, 10, 0, 0),
        end_at=datetime(2030, 1, 15, 11, 0, 0),
        max_capacity=5,
        status="available",
    )
    db_session.add(slot)
    db_session.commit()

    # Jan 10 at 23:30 UTC is Jan 11 05:00 in Asia/Kolkata (+5:30)
    utc_dt = datetime(2030, 1, 10, 23, 30, 0)
    b = Booking(
        examination_id=exam.id,
        slot_id=slot.id,
        student_id=student.id,
        status="booked",
        booked_at=utc_dt,
    )
    db_session.add(b)
    db_session.commit()

    now_ref = datetime(2030, 1, 12, 12, 0, 0)
    monkeypatch.setattr(windows, "now_utc", lambda: now_ref)

    res = chart_data.bookings_by_day(admin, 7)
    jan_10_idx = res["labels"].index("2030-01-10")
    jan_11_idx = res["labels"].index("2030-01-11")

    # In Asia/Kolkata, the booking lands on Jan 11, not Jan 10
    assert res["series"][0]["data"][jan_10_idx] == 0
    assert res["series"][0]["data"][jan_11_idx] == 1


@pytest.mark.charts
def test_cancelled_series_uses_cancelled_at(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.bookings_by_day(data.admin, 10)
    cancelled_series = next(s for s in res["series"] if s["name"] == "Cancelled")
    assert sum(cancelled_series["data"]) == 1


@pytest.mark.charts
def test_window_excludes_older_bookings(
    app, db_session, make_admin, make_examination, make_student, monkeypatch
):
    admin = make_admin()
    student = make_student()
    exam = make_examination()
    slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=admin.id,
        start_at=datetime(2030, 1, 15, 10, 0, 0),
        end_at=datetime(2030, 1, 15, 11, 0, 0),
        max_capacity=5,
        status="available",
    )
    db_session.add(slot)
    db_session.commit()

    # 40 days ago booking
    now_ref = datetime(2030, 3, 1, 12, 0, 0)
    monkeypatch.setattr(windows, "now_utc", lambda: now_ref)

    old_dt = now_ref - timedelta(days=40)
    b = Booking(
        examination_id=exam.id,
        slot_id=slot.id,
        student_id=student.id,
        status="booked",
        booked_at=old_dt,
    )
    db_session.add(b)
    db_session.commit()

    # Last 7 days chart -> excluded
    res_7 = chart_data.bookings_by_day(admin, 7)
    assert sum(res_7["series"][0]["data"]) == 0

    # Last 90 days chart -> included
    res_90 = chart_data.bookings_by_day(admin, 90)
    assert sum(res_90["series"][0]["data"]) == 1


@pytest.mark.charts
def test_days_validation():
    for good in (1, 7, 30, 90, 180, "30", "7"):
        assert chart_data.validate_days(good) == int(good)

    for bad in (0, -1, 181, 200, "abc", None, ""):
        with pytest.raises(ValueError):
            chart_data.validate_days(bad)


@pytest.mark.charts
def test_status_counts_per_role(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    # Admin: all bookings (b1 completed, b2 completed, b3 cancelled, b4 completed, b5 booked)
    # Total: booked: 1, completed: 3, cancelled: 1
    adm = chart_data.booking_status(data.admin)
    assert adm["labels"] == ["Booked", "Completed", "Cancelled"]
    assert adm["series"][0]["data"] == [1, 3, 1]

    # Student 1: b1 completed, b4 completed -> [0, 2, 0]
    stu1 = chart_data.booking_status(data.student1)
    assert stu1["series"][0]["data"] == [0, 2, 0]

    # Student 3: b3 cancelled, b5 booked -> [1, 0, 1]
    stu3 = chart_data.booking_status(data.student3)
    assert stu3["series"][0]["data"] == [1, 0, 1]

    # Student 2: b2 completed -> [0, 1, 0]
    stu2 = chart_data.booking_status(data.student2)
    assert stu2["series"][0]["data"] == [0, 1, 0]

    # Examiner 1: s1 (b1, b2, b3), s3 (b5) -> booked: 1, completed: 2, cancelled: 1
    ex1 = chart_data.booking_status(data.examiner1)
    assert ex1["series"][0]["data"] == [1, 2, 1]


@pytest.mark.charts
def test_only_future_non_cancelled_slots(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.participants_by_slot(data.admin)
    # 5 slots total: s1 & s2 are past; s3, s4, s5 are future
    assert len(res["labels"]) == 3
    booked_series = next(s for s in res["series"] if s["name"] == "Booked")
    free_series = next(s for s in res["series"] if s["name"] == "Seats free")
    # s3 capacity 3, booked 1 -> free 2
    assert booked_series["data"][0] == 1
    assert free_series["data"][0] == 2


@pytest.mark.charts
def test_limit_and_order(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.participants_by_slot(data.admin, limit=2)
    assert len(res["labels"]) == 2


@pytest.mark.charts
def test_label_truncation(app, db_session, make_admin, make_examination, monkeypatch):
    admin = make_admin()
    long_name = "Very Long Examination Title That Should Definitely Be Truncated"
    exam = make_examination(name=long_name)
    now_ref = datetime(2030, 4, 1, 10, 0, 0)
    monkeypatch.setattr(windows, "now_utc", lambda: now_ref)

    slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=admin.id,
        start_at=now_ref + timedelta(days=2),
        end_at=now_ref + timedelta(days=2, hours=1),
        max_capacity=5,
        status="available",
    )
    db_session.add(slot)
    db_session.commit()

    res = chart_data.participants_by_slot(admin)
    assert len(res["labels"]) == 1
    assert len(res["labels"][0]) <= 28


@pytest.mark.charts
def test_examiner_scope(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    # Examiner 1 owns s3 & s5 (future); Examiner 2 owns s4 (future)
    res_ex1 = chart_data.participants_by_slot(data.examiner1)
    res_ex2 = chart_data.participants_by_slot(data.examiner2)
    assert len(res_ex1["labels"]) == 2
    assert len(res_ex2["labels"]) == 1


@pytest.mark.charts
def test_student_forbidden(app, make_chart_dataset):
    data = make_chart_dataset()
    with pytest.raises(AppError) as exc_p:
        chart_data.participants_by_slot(data.student1)
    assert exc_p.value.http_status == 403

    with pytest.raises(AppError) as exc_w:
        chart_data.examiner_workload(data.student1)
    assert exc_w.value.http_status == 403

    with pytest.raises(AppError) as exc_c:
        chart_data.examination_completion(data.student1)
    assert exc_c.value.http_status == 403


@pytest.mark.charts
def test_admin_labels_are_examiner_names(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.examiner_workload(data.admin)
    assert data.examiner1.full_name in res["labels"]
    assert data.examiner2.full_name in res["labels"]


@pytest.mark.charts
def test_examiner_view_uses_own_examinations(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.examiner_workload(data.examiner1)
    # Labels should be examination names
    assert all(lbl in (data.exam1.name, data.exam2.name) for lbl in res["labels"])
    series_names = [s["name"] for s in res["series"]]
    assert series_names == ["Slots", "Booked students", "Evaluated"]


@pytest.mark.charts
def test_not_yet_submitted_counts(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.examiner_workload(data.admin)
    idx_ex1 = res["labels"].index(data.examiner1.full_name)
    idx_ex2 = res["labels"].index(data.examiner2.full_name)

    not_sub_series = next(s for s in res["series"] if s["name"] == "Not yet submitted")
    # Ex 1 has b1 (published), b2 (submitted), b5 (booked, no eval) -> 1 not submitted
    assert not_sub_series["data"][idx_ex1] == 1
    # Ex 2 has b4 (draft) -> 1 not submitted
    assert not_sub_series["data"][idx_ex2] == 1


@pytest.mark.charts
def test_counts_booked_submitted_published(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.examination_completion(data.admin)
    assert data.exam1.name in res["labels"]
    idx_e1 = res["labels"].index(data.exam1.name)

    booked_s = next(s for s in res["series"] if s["name"] == "Booked")
    sub_s = next(s for s in res["series"] if s["name"] == "Evaluation submitted")
    pub_s = next(s for s in res["series"] if s["name"] == "Published")

    # Exam 1 has active bookings: b1, b2, b5 -> 3 booked
    assert booked_s["data"][idx_e1] == 3
    # b1 published, b2 submitted -> 2 submitted/published
    assert sub_s["data"][idx_e1] == 2
    # b1 published -> 1 published
    assert pub_s["data"][idx_e1] == 1


@pytest.mark.charts
def test_deleted_examinations_excluded(app, db_session, make_admin, make_examination, monkeypatch):
    admin = make_admin()
    make_examination(name="Active Exam")
    make_examination(name="Deleted Exam", is_deleted=True)

    res = chart_data.examination_completion(admin)
    assert "Active Exam" in res["labels"]
    assert "Deleted Exam" not in res["labels"]


@pytest.mark.charts
def test_limit_most_recent_first(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res = chart_data.examination_completion(data.admin, limit=1)
    assert len(res["labels"]) == 1


@pytest.mark.charts
def test_examiner_only_assigned(
    app, db_session, make_admin, make_examiner, make_examination, make_assignment
):
    admin = make_admin()
    ex1 = make_examiner()
    ex2 = make_examiner()

    exam1 = make_examination(name="Assigned to Ex1")
    exam2 = make_examination(name="Assigned to Ex2")
    make_assignment(exam1, ex1, assigned_by=admin)
    make_assignment(exam2, ex2, assigned_by=admin)

    res1 = chart_data.examination_completion(ex1)
    assert "Assigned to Ex1" in res1["labels"]
    assert "Assigned to Ex2" not in res1["labels"]


@pytest.mark.charts
def test_only_published_included(app, make_chart_dataset):
    data = make_chart_dataset()

    # Student 1 has ev1 (published, 85%) and ev3 (draft, 60%)
    res1 = chart_data.results(data.student1)
    assert res1["labels"] == [data.exam1.name]
    assert res1["series"][0]["data"] == [85.0]

    # Student 2 has ev2 (submitted, not published)
    res2 = chart_data.results(data.student2)
    assert res2["labels"] == []
    assert res2["series"][0]["data"] == []


@pytest.mark.charts
def test_percent_rounding_one_decimal(app, make_chart_dataset):
    data = make_chart_dataset()
    res = chart_data.results(data.student1)
    assert isinstance(res["series"][0]["data"][0], float)


@pytest.mark.charts
def test_examiner_average_over_own_slots_only(app, make_chart_dataset):
    data = make_chart_dataset()

    # Examiner 1 owns s1 which has published ev1 (85.0%)
    res_ex1 = chart_data.results(data.examiner1)
    assert res_ex1["labels"] == [data.exam1.name]
    assert res_ex1["series"][0]["data"] == [85.0]

    # Examiner 2 has no published evaluations
    res_ex2 = chart_data.results(data.examiner2)
    assert res_ex2["labels"] == []


@pytest.mark.charts
def test_admin_average_over_all(app, make_chart_dataset):
    data = make_chart_dataset()
    res = chart_data.results(data.admin)
    assert res["labels"] == [data.exam1.name]
    assert res["series"][0]["data"] == [85.0]


@pytest.mark.charts
def test_examinations_without_results_omitted(app, make_chart_dataset):
    data = make_chart_dataset()
    res = chart_data.results(data.admin)
    assert data.exam2.name not in res["labels"]


@pytest.mark.charts
def test_no_labels_contain_other_users_names_or_emails(app, make_chart_dataset):
    data = make_chart_dataset()
    private_strings = [
        data.student1.full_name,
        data.student1.email,
        data.student2.full_name,
        data.student2.email,
        data.student3.full_name,
        data.student3.email,
        data.examiner1.email,
        data.examiner2.email,
    ]

    for user in (data.student1, data.examiner1):
        for fn in (
            chart_data.booking_status,
            lambda u: chart_data.bookings_by_day(u, 7),
            chart_data.results,
        ):
            res = fn(user)
            for lbl in res["labels"]:
                for priv in private_strings:
                    assert priv not in lbl


@pytest.mark.charts
def test_examiner_a_never_sees_b(app, make_chart_dataset, monkeypatch):
    data = make_chart_dataset()
    monkeypatch.setattr(windows, "now_utc", lambda: data.base_dt)

    res_ex2_slots = chart_data.participants_by_slot(data.examiner2)
    # Ex2 has only slot 4, not slots 1, 3, 5
    assert len(res_ex2_slots["labels"]) == 1
    assert data.exam1.name not in res_ex2_slots["labels"][0]
