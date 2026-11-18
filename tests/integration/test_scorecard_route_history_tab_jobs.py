"""
HTTP tests for the scorecard route, the Admin email history tab and the two jobs (P12).
"""

import pytest

from app.commands import init_db_command, jobs_group
from app.models.audit_log import AuditLog
from app.models.email_log import EmailLog
from app.services.audit_service import SCORECARD_DOWNLOAD

# --- Scorecard Route Tests ---


@pytest.mark.scorecard
def test_download_published_headers_and_body(client, make_published_result, login):
    student, exam, booking, evaluation = make_published_result()
    login(student.email)

    resp = client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert resp.data.startswith(b"%PDF-")


@pytest.mark.scorecard
def test_content_disposition_filename_and_filename_star(client, make_published_result, login):
    student, exam, booking, evaluation = make_published_result()
    login(student.email)

    resp = client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp.status_code == 200
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment;" in cd
    assert 'filename="' in cd
    assert "filename*=" in cd


@pytest.mark.scorecard
def test_cache_control_private_no_store(client, make_published_result, login):
    student, exam, booking, evaluation = make_published_result()
    login(student.email)

    resp = client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp.status_code == 200
    cc = resp.headers.get("Cache-Control", "")
    assert "no-store" in cc


@pytest.mark.scorecard
def test_foreign_unpublished_unknown_404_identical(
    client, make_published_result, make_student, login
):
    student, exam, booking, evaluation = make_published_result()
    other_student = make_student()
    login(other_student.email)

    # 1. Foreign booking (belongs to student, requested by other_student)
    resp_foreign = client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp_foreign.status_code == 404

    # 2. Unknown booking
    resp_unknown = client.get("/student/bookings/999999/scorecard.pdf")
    assert resp_unknown.status_code == 404


@pytest.mark.scorecard
def test_examiner_admin_403_anonymous_redirect(
    app, make_published_result, examiner_client, admin_client
):
    student, exam, booking, evaluation = make_published_result()

    # 1. Anonymous -> 302 to login
    anon_client = app.test_client()
    resp_anon = anon_client.get(
        f"/student/bookings/{booking.id}/scorecard.pdf", follow_redirects=False
    )
    assert resp_anon.status_code == 302
    assert resp_anon.headers["Location"].endswith("/login")

    # 2. Examiner -> 403
    ex_client, ex_user = examiner_client
    resp_ex = ex_client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp_ex.status_code == 403

    # 3. Admin -> 403
    resp_adm = admin_client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp_adm.status_code == 403


@pytest.mark.scorecard
def test_audit_row_written(client, make_published_result, login):
    student, exam, booking, evaluation = make_published_result()
    login(student.email)

    resp = client.get(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp.status_code == 200

    log = AuditLog.query.filter_by(
        action=SCORECARD_DOWNLOAD,
        entity_type="booking",
        entity_id=booking.id,
    ).first()
    assert log is not None
    assert log.actor_id == student.id


@pytest.mark.scorecard
def test_link_visible_only_when_published(client, make_published_result, login):
    student, exam, booking, evaluation = make_published_result()
    login(student.email)

    # In published result detail: link is present
    resp_res = client.get(f"/student/results/{booking.id}")
    assert resp_res.status_code == 200
    assert f"/student/bookings/{booking.id}/scorecard.pdf" in resp_res.get_data(as_text=True)

    # In booking detail: link is present when published
    resp_bk = client.get(f"/student/bookings/{booking.id}")
    assert resp_bk.status_code == 200
    assert f"/student/bookings/{booking.id}/scorecard.pdf" in resp_bk.get_data(as_text=True)


@pytest.mark.scorecard
def test_get_only_405(client, make_published_result, login):
    student, exam, booking, evaluation = make_published_result()
    login(student.email)

    resp_post = client.post(f"/student/bookings/{booking.id}/scorecard.pdf")
    assert resp_post.status_code == 405


# --- History Tab Tests ---


@pytest.mark.mail
def test_emails_tab_lists_rows_with_badges(admin_client, db_session):
    log1 = EmailLog(
        to_email="stu1@test.local",
        template="booking_confirmed",
        status="sent",
        subject="Booking Confirmed",
        body_text="Dear Student, your booking is confirmed.",
        attempts=1,
    )
    log2 = EmailLog(
        to_email="stu2@test.local",
        template="booking_cancelled",
        status="failed",
        subject="Booking Cancelled",
        body_text="Dear Student, your booking was cancelled.",
        attempts=3,
        error_message="SMTP server down",
    )
    db_session.add_all([log1, log2])
    db_session.commit()

    resp = admin_client.get("/admin/history?tab=emails")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "stu1@test.local" in html
    assert "stu2@test.local" in html
    assert "booking_confirmed" in html
    assert "booking_cancelled" in html
    assert "badge bg-success" in html  # Sent badge
    assert "badge bg-danger" in html  # Failed badge


@pytest.mark.mail
def test_filters_status_and_template(admin_client, db_session):
    log1 = EmailLog(
        to_email="stu10@test.local",
        template="booking_confirmed",
        status="sent",
        subject="Booking Confirmed",
        body_text="Confirmed",
    )
    log2 = EmailLog(
        to_email="stu20@test.local",
        template="examiner_approved",
        status="failed",
        subject="Examiner Approved",
        body_text="Approved",
    )
    db_session.add_all([log1, log2])
    db_session.commit()

    # Filter status=sent
    resp_sent = admin_client.get("/admin/history?tab=emails&status=sent")
    html_sent = resp_sent.get_data(as_text=True)
    assert "stu10@test.local" in html_sent
    assert "stu20@test.local" not in html_sent

    # Filter template=examiner_approved
    resp_tmpl = admin_client.get("/admin/history?tab=emails&template=examiner_approved")
    html_tmpl = resp_tmpl.get_data(as_text=True)
    assert "stu20@test.local" in html_tmpl
    assert "stu10@test.local" not in html_tmpl


@pytest.mark.mail
def test_body_never_shown(admin_client, db_session):
    secret_body = "SUPER_SECRET_EMAIL_BODY_CONTENT_12345"
    log = EmailLog(
        to_email="privacy@test.local",
        template="booking_confirmed",
        status="sent",
        subject="Test Privacy",
        body_text=secret_body,
    )
    db_session.add(log)
    db_session.commit()

    resp = admin_client.get("/admin/history?tab=emails")
    assert resp.status_code == 200
    assert secret_body not in resp.get_data(as_text=True)


@pytest.mark.mail
def test_five_tabs_present(admin_client):
    resp = admin_client.get("/admin/history")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    for tab in ("examinations", "bookings", "evaluations", "audit", "emails"):
        assert f"tab={tab}" in html


@pytest.mark.mail
def test_non_admin_403(app, student_client, examiner_client):
    st_client, _ = student_client
    resp_st = st_client.get("/admin/history?tab=emails")
    assert resp_st.status_code == 403

    ex_client, _ = examiner_client
    resp_ex = ex_client.get("/admin/history?tab=emails")
    assert resp_ex.status_code == 403


# --- Jobs CLI Tests ---


@pytest.mark.mail
def test_jobs_retry_failed_emails_output_and_exit_code(runner, db_session):
    log = EmailLog(
        to_email="retry@test.local",
        template="booking_confirmed",
        status="failed",
        subject="Booking Confirmed",
        body_text="Body",
        attempts=1,
    )
    db_session.add(log)
    db_session.commit()

    result = runner.invoke(jobs_group, ["retry-failed-emails"])
    assert result.exit_code == 0
    assert "Retry summary:" in result.output


@pytest.mark.mail
def test_jobs_retry_respects_max_attempts_option(runner, db_session):
    log = EmailLog(
        to_email="terminal@test.local",
        template="booking_confirmed",
        status="failed",
        subject="Booking Confirmed",
        body_text="Body",
        attempts=2,
    )
    db_session.add(log)
    db_session.commit()

    # With max-attempts=2, this row is terminal and will NOT be considered
    result = runner.invoke(jobs_group, ["retry-failed-emails", "--max-attempts", "2"])
    assert result.exit_code == 0
    assert "0 considered" in result.output


@pytest.mark.mail
def test_jobs_purge_email_logs_days_option(runner, db_session):
    log = EmailLog(
        to_email="purge@test.local",
        template="booking_confirmed",
        status="sent",
        subject="Booking Confirmed",
        body_text="Body",
        attempts=1,
    )
    db_session.add(log)
    db_session.commit()

    result = runner.invoke(jobs_group, ["purge-email-logs", "--days", "30"])
    assert result.exit_code == 0
    assert "Purged" in result.output


@pytest.mark.mail
def test_jobs_exit_zero_when_nothing_to_do(runner):
    res_retry = runner.invoke(jobs_group, ["retry-failed-emails"])
    assert res_retry.exit_code == 0

    res_purge = runner.invoke(jobs_group, ["purge-email-logs"])
    assert res_purge.exit_code == 0


@pytest.mark.mail
def test_init_db_reports_tier_counts_12_and_1(runner):
    result = runner.invoke(init_db_command)
    assert result.exit_code == 0
    assert "Tier 1 tables: 12, Tier 2 tables: 1" in result.output
