import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(db.Model):
    """
    Immutable audit trail record. Never updated or deleted.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Actor user account (nullable for automated system/cron jobs)
    actor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Dotted action identifier (e.g., 'booking.create', 'booking.cancel', 'slot.reschedule')
    action: Mapped[str] = mapped_column(String(60), nullable=False)

    # Target entity type and primary key
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Structured JSON details
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Client IP address
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Timestamp of event (created_at only; rows are immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # Relationship to acting User
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])

    def details_dict(self) -> dict[str, Any]:
        """Safely parse details JSON string to dict; returns {} on empty or error."""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except (ValueError, TypeError):
            return {}

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r} entity={self.entity_type}#{self.entity_id}>"