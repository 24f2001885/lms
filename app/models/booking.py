from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.evaluation import Evaluation
    from app.models.examination import Examination
    from app.models.slot import ExaminationSlot
    from app.models.user import User

BOOKING_STATUSES = ("booked", "cancelled", "completed")


class Booking(db.Model, TimestampMixin):
    """
    Student booking reservation in an examination slot.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        
        CheckConstraint(
            f"status IN {BOOKING_STATUSES}",
            name="ck_bookings_status_valid",
        ),
        # Partial unique index: at most one ACTIVE booking per student per examination.
        # Cancelled bookings are excluded so re-booking is permitted.
        Index(
            "uq_bookings_active_student_exam",
            "student_id",
            "examination_id",
            unique=True,
            sqlite_where=text("status IN ('booked', 'completed')"),
        ),
        Index("ix_bookings_slot_id", "slot_id"),
        Index("ix_bookings_student_id", "student_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Student user account
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Chosen slot
    slot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examination_slots.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Denormalized examination ID to support the partial unique index
    examination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examinations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Status: 'booked' | 'cancelled' | 'completed'
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="booked",
        server_default="booked",
    )

    # Explicit booked timestamp set by service using now_utc()
    booked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Cancellation audit tracking
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Rescheduling audit tracking
    rescheduled_from_slot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("examination_slots.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # -----------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    slot: Mapped["ExaminationSlot"] = relationship("ExaminationSlot", foreign_keys=[slot_id], back_populates="bookings")
    examination: Mapped["Examination"] = relationship("Examination", foreign_keys=[examination_id])
    canceller: Mapped[Optional["User"]] = relationship("User", foreign_keys=[cancelled_by])
    rescheduled_from: Mapped[Optional["ExaminationSlot"]] = relationship("ExaminationSlot", foreign_keys=[rescheduled_from_slot_id])
    evaluation: Mapped[Optional["Evaluation"]] = relationship(
        "Evaluation",
        back_populates="booking",
        uselist=False,
        passive_deletes=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Booking id={self.id} student_id={self.student_id} slot_id={self.slot_id} "
            f"exam_id={self.examination_id} status={self.status!r}>"
        )