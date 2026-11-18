"""
Builds, logs, sends, and retries transactional emails (TDR 8.1). Sending
happens AFTER the business commit in a background thread and never rolls back
the action that caused it.
"""

import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app, render_template_string
from flask_mail import Message

from app.extensions import db, mail
from app.models.booking import Booking
from app.models.email_log import EmailLog
from app.models.evaluation import Evaluation
from app.models.slot import ExaminationSlot
from app.models.user import User
from app.services import hooks, windows
from app.services.audit_service import log_action

logger = logging.getLogger("emp.mailer")

SYSTEM_EMAIL_RETRY = "system.email_retry"
SYSTEM_EMAIL_PURGE = "system.email_purge"

EMAIL_TEMPLATES = {
    "booking_confirmed": {
        "subject": "Booking Confirmed: {{ examination_name }}",
        "file": "emails/booking_confirmed.txt",
    },
    "booking_cancelled": {
        "subject": "Booking Cancelled: {{ examination_name }}",
        "file": "emails/booking_cancelled.txt",
    },
    "booking_rescheduled": {
        "subject": "Booking Rescheduled: {{ examination_name }}",
        "file": "emails/booking_rescheduled.txt",
    },
    "examiner_approved": {
        "subject": "Examiner Account Approved",
        "file": "emails/examiner_approved.txt",
    },
    "result_published": {
        "subject": "Result Published: {{ examination_name }}",
        "file": "emails/result_published.txt",
    },
}


def build_message(template: str, context: dict[str, Any]) -> tuple[str, str]:
    if template not in EMAIL_TEMPLATES:
        raise KeyError(f"Unknown email template: {template}")
    spec = EMAIL_TEMPLATES[template]

    # Safe render of subject (no newlines)
    raw_subj = render_template_string(spec["subject"], **context)
    subj = " ".join(raw_subj.split())[:150]

    with current_app.open_resource(f"templates/{spec['file']}") as f:
        body_tmpl = f.read().decode("utf-8")

    context["institution"] = current_app.config.get(
        "INSTITUTION_NAME", "Examination Management Portal"
    )
    body = render_template_string(body_tmpl, **context)

    # Footer append
    with current_app.open_resource("templates/emails/_footer.txt") as f:
        footer_tmpl = f.read().decode("utf-8")
        footer = render_template_string(footer_tmpl, **context)

    return subj, f"{body}\n\n{footer}"


def queue_email(
    template: str, to_email: str, context: dict[str, Any], related: tuple[str, int | None]
) -> int | None:
    if (
        not to_email
        or "\n" in to_email
        or "\r" in to_email
        or "," in to_email
        or to_email.count("@") != 1
    ):
        logger.warning("Invalid recipient email address skipped.")
        return None

    subj, body = build_message(template, context)

    log = EmailLog(
        to_email=to_email,
        template=template,
        status="queued",
        subject=subj,
        body_text=body,
        related_entity_type=related[0],
        related_entity_id=related[1],
    )
    db.session.add(log)
    db.session.commit()

    dispatch(log.id)
    return log.id


def dispatch(log_id: int) -> None:
    if current_app.config.get("MAIL_ASYNC", True):
        app_obj = current_app._get_current_object()
        t = threading.Thread(target=_send_with_context, args=(app_obj, log_id))
        t.daemon = True
        t.start()
    else:
        attempt_send(log_id)


def _send_with_context(app_obj, log_id: int) -> None:
    with app_obj.app_context():
        try:
            attempt_send(log_id)
        finally:
            db.session.remove()


def attempt_send(log_id: int) -> str:
    log = db.session.get(EmailLog, log_id)
    if not log:
        return "failed"
    if log.status == "sent":
        return "sent"

    log.attempts += 1
    log.last_attempt_at = windows.now_utc()
    db.session.commit()

    msg = Message(
        subject=log.subject,
        recipients=[log.to_email],
        body=log.body_text,
        sender=current_app.config.get("MAIL_DEFAULT_SENDER", "emp@example.edu"),
    )

    try:
        if current_app.config.get("MAIL_SUPPRESS_SEND", False):
            log.status = "sent"
            log.sent_at = windows.now_utc()
            log.error_message = "suppressed (MAIL_SUPPRESS_SEND)"
        else:
            mail.send(msg)
            log.status = "sent"
            log.sent_at = windows.now_utc()
    except Exception as e:
        log.status = "failed"
        raw_err = f"{type(e).__name__}: {str(e)}"
        # Scrape potential credentials from error text if present
        mail_pw = current_app.config.get("MAIL_PASSWORD")
        if mail_pw:
            raw_err = raw_err.replace(mail_pw, "***")
        log.error_message = " ".join(raw_err.split())[:300]
        logger.warning(f"Email {log.template} failed (attempt {log.attempts})")

    db.session.commit()
    return log.status


def retry_failed(
    max_attempts: int | None = None, limit: int = 100, now: float | None = None
) -> dict[str, int]:
    if max_attempts is None:
        max_attempts = current_app.config.get("MAIL_MAX_ATTEMPTS", 3)

    if now is not None:
        now_dt = datetime.fromtimestamp(now, tz=UTC).replace(tzinfo=None)
    else:
        now_dt = windows.now_utc().replace(tzinfo=None)

    stale_queued_cutoff = now_dt - timedelta(minutes=15)

    candidates = (
        EmailLog.query.filter(
            db.or_(
                db.and_(EmailLog.status == "failed", EmailLog.attempts < max_attempts),
                db.and_(EmailLog.status == "queued", EmailLog.created_at < stale_queued_cutoff),
            )
        )
        .order_by(EmailLog.created_at)
        .limit(limit)
        .all()
    )

    results = {"considered": len(candidates), "sent": 0, "still_failed": 0}
    for c in candidates:
        if attempt_send(c.id) == "sent":
            results["sent"] += 1
        else:
            results["still_failed"] += 1

    if results["considered"] > 0:
        log_action(None, SYSTEM_EMAIL_RETRY, "system", None, results)
        db.session.commit()

    return results


def purge_old(days: int | None = None, now: float | None = None) -> int:
    if days is None:
        days = current_app.config.get("EMAIL_LOG_RETENTION_DAYS", 90)
    if days <= 0:
        raise ValueError("Days must be positive")

    max_attempts = current_app.config.get("MAIL_MAX_ATTEMPTS", 3)
    if now is not None:
        now_dt = datetime.fromtimestamp(now, tz=UTC).replace(tzinfo=None)
    else:
        now_dt = windows.now_utc().replace(tzinfo=None)

    cutoff = now_dt - timedelta(days=days)

    query = EmailLog.query.filter(
        EmailLog.created_at < cutoff,
        db.or_(
            EmailLog.status == "sent",
            db.and_(EmailLog.status == "failed", EmailLog.attempts >= max_attempts),
        ),
    )
    count = query.delete(synchronize_session=False)
    if count > 0:
        log_action(None, SYSTEM_EMAIL_PURGE, "system", None, {"purged_count": count, "days": days})
    db.session.commit()
    return count


# --- Event Handlers ---


def _build_context(booking: Booking) -> dict:
    tz = current_app.config.get("APP_TIMEZONE", "UTC")
    start_loc = windows.format_local(windows.to_local(booking.slot.start_at))
    end_loc = windows.format_local(windows.to_local(booking.slot.end_at))
    cancel_loc = windows.format_local(windows.to_local(booking.examination.cancellation_deadline))
    base_url = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:5000")

    return {
        "student_name": booking.student.full_name,
        "examination_name": booking.examination.name,
        "course_code": booking.examination.course.code,
        "slot_start": start_loc,
        "slot_end": end_loc,
        "cancel_deadline": cancel_loc,
        "examiner_name": booking.slot.examiner.full_name,
        "booking_id": booking.id,
        "tz": tz,
        "link": f"{base_url}/student/bookings",
    }


def on_booking_created(booking_id: int, student_id: int) -> None:
    booking = db.session.get(Booking, booking_id)
    if not booking or not booking.student.is_active or not booking.student.email:
        return
    ctx = _build_context(booking)
    queue_email("booking_confirmed", booking.student.email, ctx, ("booking", booking.id))


def on_booking_cancelled(booking_id: int, student_id: int, by: str) -> None:
    booking = db.session.get(Booking, booking_id)
    if not booking or not booking.student.is_active or not booking.student.email:
        return
    ctx = _build_context(booking)
    ctx["by"] = by
    queue_email("booking_cancelled", booking.student.email, ctx, ("booking", booking.id))


def on_booking_rescheduled(
    booking_id: int, student_id: int, from_slot_id: int, to_slot_id: int
) -> None:
    booking = db.session.get(Booking, booking_id)
    if not booking or not booking.student.is_active or not booking.student.email:
        return

    old_slot = db.session.get(ExaminationSlot, from_slot_id)
    if not old_slot:
        return

    ctx = _build_context(booking)
    ctx["old_start"] = windows.format_local(windows.to_local(old_slot.start_at))
    ctx["new_start"] = ctx.pop("slot_start")
    ctx["new_end"] = ctx.pop("slot_end")

    queue_email("booking_rescheduled", booking.student.email, ctx, ("booking", booking.id))


def on_examiner_approved(examiner_id: int) -> None:
    examiner = db.session.get(User, examiner_id)
    if not examiner or not examiner.is_active or not examiner.email:
        return
    base_url = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:5000")
    ctx = {
        "examiner_name": examiner.full_name,
        "link": f"{base_url}/login",
    }
    queue_email("examiner_approved", examiner.email, ctx, ("user", examiner.id))


def on_evaluation_published(evaluation_id: int, booking_id: int, student_id: int) -> None:
    evaluation = db.session.get(Evaluation, evaluation_id)
    if (
        not evaluation
        or not evaluation.booking.student.is_active
        or not evaluation.booking.student.email
    ):
        return

    booking = evaluation.booking
    base_url = current_app.config.get("APP_BASE_URL", "http://127.0.0.1:5000")
    exam_loc = windows.format_local(windows.to_local(booking.slot.start_at), fmt="%d %b %Y")

    ctx = {
        "student_name": booking.student.full_name,
        "examination_name": booking.examination.name,
        "exam_date": exam_loc,
        "link": f"{base_url}/student/results/{booking.id}",
    }
    queue_email("result_published", booking.student.email, ctx, ("booking", booking.id))


def register_event_handlers() -> None:
    hooks.register_event(hooks.EVENT_BOOKING_CREATED, on_booking_created)
    hooks.register_event(hooks.EVENT_BOOKING_CANCELLED, on_booking_cancelled)
    hooks.register_event(hooks.EVENT_BOOKING_RESCHEDULED, on_booking_rescheduled)
    hooks.register_event(hooks.EVENT_EXAMINER_APPROVED, on_examiner_approved)
    hooks.register_event(hooks.EVENT_EVALUATION_PUBLISHED, on_evaluation_published)
