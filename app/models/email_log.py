"""
Table "email_logs" (Tier 2): one row per email that the system tried to send,
so failures are visible and can be retried (TDR 4.2 and v2.1 additions).
"""

from sqlalchemy import CheckConstraint

from app.extensions import db

EMAIL_STATUSES = ("queued", "sent", "failed")


class EmailLog(db.Model):
    __tablename__ = "email_logs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'sent', 'failed')", name="status_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.Text, nullable=False)
    template = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    related_entity_type = db.Column(db.Text, nullable=True)
    related_entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())
    sent_at = db.Column(db.DateTime, nullable=True)

    # TDR 4.2 updates for retry logic:
    subject = db.Column(db.Text, nullable=False)
    body_text = db.Column(db.Text, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_attempt_at = db.Column(db.DateTime, nullable=True)

    def is_terminal_failure(self, max_attempts: int) -> bool:
        return self.status == "failed" and self.attempts >= max_attempts
