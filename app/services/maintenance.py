"""
FILE PURPOSE: Housekeeping rules behind the weekly purge job (TDR section 11, "purge-soft-deleted").
"""
import logging
from datetime import datetime, timedelta

from app.extensions import db
from app.models import (
    Booking,
    Examination,
    ExaminationExaminer,
    ExaminationRubric,
    ExaminationSlot,
)
from app.services import audit_service, windows

logger = logging.getLogger(__name__)


def purge_soft_deleted(older_than_days: int = 90, now: datetime | None = None) -> int:
    if isinstance(older_than_days, bool) or not isinstance(older_than_days, int) or older_than_days <= 0:
        raise ValueError("older_than_days must be a positive integer.")

    now_time = now if now is not None else windows.now_utc()
    cutoff = now_time - timedelta(days=older_than_days)

    candidates = Examination.query.filter(
        Examination.is_deleted.is_(True),
        Examination.updated_at < cutoff,
    ).all()

    purged = 0
    for exam in candidates:
        booking_count = Booking.query.filter_by(examination_id=exam.id).count()
        if booking_count > 0:
            continue

        try:
            exam_id = exam.id
            exam_name = exam.name
            course_id = exam.course_id

            ExaminationRubric.query.filter_by(examination_id=exam_id).delete()
            ExaminationExaminer.query.filter_by(examination_id=exam_id).delete()
            ExaminationSlot.query.filter_by(examination_id=exam_id).delete()
            db.session.delete(exam)

            audit_service.log_action(
                actor_id=None,
                action=audit_service.SYSTEM_PURGE,
                entity_type="examination",
                entity_id=exam_id,
                details={"name": exam_name, "course_id": course_id},
            )
            db.session.commit()
            purged += 1
        except Exception:
            db.session.rollback()
            logger.exception("Failed to purge soft-deleted examination id=%s", exam.id)

    return purged
