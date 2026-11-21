"""
FILE PURPOSE: Table "examination_slots": a bookable time slot created by an examiner, with capacity.
DEPENDS ON: app/models/examination.py, app/models/user.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Class ExaminationSlot(db.Model, TimestampMixin), __tablename__ = "examination_slots". Columns: id PK; examination_id FK examinations.id not null; examiner_id FK users.id not null; start_at DATETIME not null; end_at DATETIME not null; max_capacity INTEGER not null; booked_count INTEGER not null default 0; status TEXT not null default "available".
2. Constant SLOT_STATUSES = ("available","full","cancelled","completed"). CheckConstraints: status_valid; time_order (end_at > start_at); capacity_positive (max_capacity > 0); booked_count_in_range (booked_count >= 0 AND booked_count <= max_capacity). This last constraint is the DATABASE-LEVEL guard against overbooking (invariant 1 in TDR 3.1).
3. Indexes ix_slots_examination_id and ix_slots_examiner_id. Relationships: examination, examiner (User), bookings (one-to-many, no cascade).
4. Read-only property seats_left = max_capacity - booked_count (never negative). No other logic; booking/cancel logic belongs to booking_engine in P5/P6.
5. Comment: "no two slots of the same examiner may overlap" is a P4 service rule.
DEBUGGING:
# print(f"[DEBUG] Slot {self.id} {self.start_at}->{self.end_at} {self.booked_count}/{self.max_capacity} {self.status}")
OFFLINE DOCKER TEST CASES:
- booked_count 6 with max_capacity 5 raises IntegrityError; booked_count -1 raises IntegrityError.
- end_at equal to start_at raises IntegrityError; max_capacity 0 raises IntegrityError.
- status "open" raises IntegrityError.
- seats_left is 3 for capacity 5 and booked_count 2.

app/models/slot.py - Examination slot model for LMS.

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
