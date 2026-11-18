"""
FILE PURPOSE: End-to-end proof that real actions produce the right emails and that failures never block them (acceptance of P12).
DEPENDS ON: tests/conftest.py (api and HTTP clients, sync_mail, mail_outbox, smtp_failure, factories).
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.models.booking import Booking
from app.models.email_log import EmailLog
from app.models.evaluation import Evaluation, EvaluationScore
from app.models.slot import ExaminationSlot
from app.services import admin_service, booking_engine, evaluation_service, hooks, mailer, windows

pytestmark = pytest.mark.mail


def test_booking_creates_confirmation_email_and_log_html(
    sync_mail, mail_outbox, student_client, make_open_booking_setup, freeze_now
):
    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    res = client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    assert res.status_code == 200

    log = EmailLog.query.filter_by(to_email=student.email, template="booking_confirmed").first()
    assert log is not None
    assert log.status == "sent"
    assert exam.name in log.subject
    assert len(mail_outbox) == 1
    assert mail_outbox[0].recipients == [student.email]


def test_booking_creates_confirmation_email_and_log_api(
    sync_mail, mail_outbox, api, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, _ = make_open_booking_setup(student_count=0, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    st = api("student")
    res = st.post("/api/v1/bookings", data={"slot_id": slot.id})
    assert res.status_code == 201

    log = EmailLog.query.filter_by(template="booking_confirmed").first()
    assert log is not None
    assert log.status == "sent"
    assert len(mail_outbox) == 1


def test_student_cancel_email(
    sync_mail, mail_outbox, student_client, make_open_booking_setup, freeze_now
):
    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    booking = Booking.query.filter_by(student_id=student.id, status="booked").first()
    assert booking is not None

    res_cancel = client.post(f"/student/bookings/{booking.id}/cancel", follow_redirects=True)
    assert res_cancel.status_code == 200

    log = EmailLog.query.filter_by(to_email=student.email, template="booking_cancelled").first()
    assert log is not None
    assert log.status == "sent"
    assert "Cancelled" in log.subject


def test_admin_cancel_email_has_no_reason(
    sync_mail, mail_outbox, make_ready_examination, make_booking_with_slot, make_admin
):
    exam, examiner = make_ready_examination()
    booking, slot = make_booking_with_slot(exam, examiner)
    admin = make_admin()

    secret_reason = "CONFIDENTIAL_ADMIN_INTERNAL_NOTE_123"
    booking_engine.admin_cancel_booking(booking.id, actor_id=admin.id, reason=secret_reason)

    log = EmailLog.query.filter_by(
        to_email=booking.student.email, template="booking_cancelled"
    ).first()
    assert log is not None
    assert log.status == "sent"
    assert secret_reason not in log.body_text


def test_slot_cancel_emails_every_student_once(
    sync_mail, mail_outbox, make_ready_examination, make_student, db_session
):
    exam, examiner = make_ready_examination()
    st1 = make_student(email="slotstu1@test.local")
    st2 = make_student(email="slotstu2@test.local")

    slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=exam.booking_end + timedelta(days=1),
        end_at=exam.booking_end + timedelta(days=1, hours=1),
        max_capacity=5,
        booked_count=2,
        status="available",
    )
    db_session.add(slot)
    db_session.flush()

    b1 = Booking(
        slot_id=slot.id,
        student_id=st1.id,
        examination_id=exam.id,
        status="booked",
        booked_at=exam.booking_start + timedelta(hours=1),
    )
    b2 = Booking(
        slot_id=slot.id,
        student_id=st2.id,
        examination_id=exam.id,
        status="booked",
        booked_at=exam.booking_start + timedelta(hours=1),
    )
    db_session.add_all([b1, b2])
    db_session.commit()

    booking_engine.cancel_slot(slot.id, actor_id=examiner.id, reason="Illness")

    logs1 = EmailLog.query.filter_by(to_email=st1.email, template="booking_cancelled").all()
    logs2 = EmailLog.query.filter_by(to_email=st2.email, template="booking_cancelled").all()
    assert len(logs1) == 1
    assert len(logs2) == 1


def test_reschedule_email_new_slot(
    sync_mail, mail_outbox, make_ready_examination, make_booking_with_slot, make_admin, db_session
):
    exam, examiner = make_ready_examination()
    booking, slot1 = make_booking_with_slot(exam, examiner)
    admin = make_admin()

    slot2 = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        start_at=exam.booking_end + timedelta(days=2),
        end_at=exam.booking_end + timedelta(days=2, hours=1),
        max_capacity=5,
        booked_count=0,
        status="available",
    )
    db_session.add(slot2)
    db_session.commit()

    booking_engine.reschedule_booking(booking.id, slot2.id, actor_id=admin.id)

    log = EmailLog.query.filter_by(
        to_email=booking.student.email, template="booking_rescheduled"
    ).first()
    assert log is not None
    assert log.status == "sent"
    assert "Rescheduled" in log.subject


def test_examiner_approval_email(sync_mail, mail_outbox, make_examiner, make_admin):
    admin = make_admin()
    examiner = make_examiner(approved=False)

    admin_service.approve_examiner(actor_id=admin.id, user_id=examiner.id)

    log = EmailLog.query.filter_by(to_email=examiner.email, template="examiner_approved").first()
    assert log is not None
    assert log.status == "sent"
    assert "Approved" in log.subject


def test_publish_by_examiner_email_no_marks(
    sync_mail, mail_outbox, make_ready_examination, make_booking_with_slot, db_session
):
    exam, examiner = make_ready_examination()
    booking, slot = make_booking_with_slot(exam, examiner)

    eval_obj = Evaluation(
        booking_id=booking.id,
        examiner_id=examiner.id,
        status="submitted",
        total_marks=Decimal("85.00"),
        submitted_at=windows.now_utc(),
        remarks="Good presentation",
    )
    db_session.add(eval_obj)
    db_session.flush()

    for r in exam.rubrics:
        sc = EvaluationScore(
            evaluation=eval_obj,
            rubric_id=r.id,
            score=Decimal("40.00"),
            comment="Fine",
        )
        db_session.add(sc)
    db_session.commit()

    evaluation_service.publish_evaluation(examiner.id, eval_obj.id)

    log = EmailLog.query.filter_by(
        to_email=booking.student.email, template="result_published"
    ).first()
    assert log is not None
    assert log.status == "sent"
    # Never contains marks or scores
    assert "85" not in log.body_text
    assert "40" not in log.body_text
    assert "/student/results" in log.body_text


def test_publish_by_admin_email(
    sync_mail, mail_outbox, make_ready_examination, make_booking_with_slot, make_admin, db_session
):
    exam, examiner = make_ready_examination()
    booking, slot = make_booking_with_slot(exam, examiner)
    admin = make_admin()

    eval_obj = Evaluation(
        booking_id=booking.id,
        examiner_id=examiner.id,
        status="submitted",
        total_marks=Decimal("90.00"),
        submitted_at=windows.now_utc(),
    )
    db_session.add(eval_obj)
    db_session.flush()
    for r in exam.rubrics:
        sc = EvaluationScore(
            evaluation=eval_obj,
            rubric_id=r.id,
            score=Decimal("45.00"),
            comment="Great",
        )
        db_session.add(sc)
    db_session.commit()

    evaluation_service.admin_publish(admin.id, eval_obj.id)

    log = EmailLog.query.filter_by(
        to_email=booking.student.email, template="result_published"
    ).first()
    assert log is not None
    assert log.status == "sent"


def test_smtp_failure_booking_still_succeeds_and_log_failed(
    sync_mail, smtp_failure, student_client, make_open_booking_setup, freeze_now
):
    smtp_failure()
    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    res = client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    assert res.status_code == 200

    booking = Booking.query.filter_by(student_id=student.id, status="booked").first()
    assert booking is not None

    log = EmailLog.query.filter_by(to_email=student.email, template="booking_confirmed").first()
    assert log is not None
    assert log.status == "failed"
    assert log.attempts == 1
    assert "ConnectionRefusedError" in log.error_message


def test_smtp_failure_cancel_and_publish_still_succeed(
    sync_mail, smtp_failure, make_ready_examination, make_booking_with_slot, db_session
):
    smtp_failure()
    exam, examiner = make_ready_examination()
    booking, slot = make_booking_with_slot(exam, examiner)

    # Cancel booking
    booking_engine.cancel_booking(booking.student_id, booking.id)
    assert booking.status == "cancelled"
    log_cancel = EmailLog.query.filter_by(
        to_email=booking.student.email, template="booking_cancelled"
    ).first()
    assert log_cancel is not None
    assert log_cancel.status == "failed"

    # New booking & evaluation publish
    b2, s2 = make_booking_with_slot(exam, examiner)
    eval_obj = Evaluation(
        booking_id=b2.id,
        examiner_id=examiner.id,
        status="submitted",
        total_marks=Decimal("80.00"),
        submitted_at=windows.now_utc(),
    )
    db_session.add(eval_obj)
    db_session.flush()
    for r in exam.rubrics:
        sc = EvaluationScore(
            evaluation=eval_obj,
            rubric_id=r.id,
            score=Decimal("40.00"),
            comment="Fine",
        )
        db_session.add(sc)
    db_session.commit()

    evaluation_service.publish_evaluation(examiner.id, eval_obj.id)
    assert eval_obj.status == "published"
    log_pub = EmailLog.query.filter_by(
        to_email=b2.student.email, template="result_published"
    ).first()
    assert log_pub is not None
    assert log_pub.status == "failed"


def test_mail_suppressed_mode_logs_sent_with_note(
    app, student_client, make_open_booking_setup, freeze_now
):
    app.config["MAIL_SUPPRESS_SEND"] = True
    app.config["MAIL_ASYNC"] = False

    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    res = client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    assert res.status_code == 200

    log = EmailLog.query.filter_by(to_email=student.email, template="booking_confirmed").first()
    assert log is not None
    assert log.status == "sent"
    assert "suppressed (MAIL_SUPPRESS_SEND)" in (log.error_message or "")


def test_mail_disabled_by_clearing_handlers_changes_nothing(
    student_client, make_open_booking_setup, freeze_now
):
    hooks.clear_events()
    try:
        client, student = student_client
        exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
        freeze_now(exam.booking_start + timedelta(hours=1))

        res = client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
        assert res.status_code == 200

        booking = Booking.query.filter_by(student_id=student.id, status="booked").first()
        assert booking is not None

        assert EmailLog.query.count() == 0
    finally:
        mailer.register_event_handlers()


def test_exactly_one_email_per_event(
    sync_mail, student_client, make_open_booking_setup, freeze_now
):
    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    freeze_now(exam.booking_start + timedelta(hours=1))

    # First booking POST
    client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    # Second duplicate booking POST
    client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)

    logs = EmailLog.query.filter_by(to_email=student.email, template="booking_confirmed").all()
    assert len(logs) == 1


def test_inactive_student_gets_no_email(
    sync_mail, make_ready_examination, make_booking_with_slot, db_session
):
    exam, examiner = make_ready_examination()
    booking, slot = make_booking_with_slot(exam, examiner)
    booking.student.is_active = False
    db_session.commit()

    count_before = EmailLog.query.count()
    mailer.on_booking_created(booking.id, booking.student.id)
    assert EmailLog.query.count() == count_before


def test_email_row_not_created_when_business_action_fails_full_slot(
    sync_mail, api, make_open_booking_setup, freeze_now
):
    exam, slot, examiner, _ = make_open_booking_setup(student_count=0, capacity=1)
    freeze_now(exam.booking_start + timedelta(hours=1))

    st1 = api("student")
    st2 = api("student")

    res1 = st1.post("/api/v1/bookings", data={"slot_id": slot.id})
    assert res1.status_code == 201

    res2 = st2.post("/api/v1/bookings", data={"slot_id": slot.id})
    assert res2.status_code == 409

    # Only 1 confirmation email from the successful booking
    assert EmailLog.query.filter_by(template="booking_confirmed").count() == 1


def test_email_row_not_created_when_business_action_fails_closed_window(
    sync_mail, student_client, make_open_booking_setup, freeze_now
):
    client, student = student_client
    exam, slot, examiner, students = make_open_booking_setup(student_count=1, capacity=5)
    # Freeze time before booking start
    freeze_now(exam.booking_start - timedelta(days=2))

    client.post(f"/student/slots/{slot.id}/book", follow_redirects=True)
    assert EmailLog.query.count() == 0
