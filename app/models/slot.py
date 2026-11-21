"""
app/models/slot.py - Examination slot model for LMS.

Table "examination_slots": a bookable time slot created by an examiner, with capacity.
Defines the 'examination_slots' table representing bookable time windows
created by faculty examiners with capacity limits and active booking tracking.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.examination import Examination
    from app.models.user import User

SLOT_STATUSES = ("available", "full", "cancelled", "completed")


class ExaminationSlot(db.Model, TimestampMixin):
    """
    Time slot created by an examiner for student booking.
    """

    __tablename__ = "examination_slots"
    __table_args__ = (
        CheckConstraint(
            f"status IN {SLOT_STATUSES}",
            name="ck_examination_slots_status_valid",
        ),
        CheckConstraint("end_at > start_at", name="ck_examination_slots_time_order"),
        CheckConstraint("max_capacity > 0", name="ck_examination_slots_capacity_positive"),
        CheckConstraint(
            "booked_count >= 0 AND booked_count <= max_capacity",
            name="ck_examination_slots_booked_count_in_range",
        ),
        Index("ix_slots_examination_id", "examination_id"),
        Index("ix_slots_examiner_id", "examiner_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Examination parent
    examination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examinations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Assigned examiner who conducts evaluations in this slot
    examiner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Maximum allowed bookings for this slot
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Currently active bookings count (strictly <= max_capacity)
    booked_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Status: 'available' | 'full' | 'cancelled' | 'completed'
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="available",
        server_default="available",
    )

    # -----------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------
    examination: Mapped["Examination"] = relationship("Examination", back_populates="slots")
    examiner: Mapped["User"] = relationship("User", foreign_keys=[examiner_id])
    bookings: Mapped[list["Booking"]] = relationship(
        "Booking",
        back_populates="slot",
        foreign_keys="Booking.slot_id",
        passive_deletes=False,
    )

    @property
    def seats_left(self) -> int:
        """Return remaining bookable seats; never negative."""
        return max(0, self.max_capacity - self.booked_count)

    def __repr__(self) -> str:
        return (
            f"<ExaminationSlot id={self.id} exam_id={self.examination_id} "
            f"capacity={self.booked_count}/{self.max_capacity} status={self.status!r}>"
        )
