from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.examination_examiner import ExaminationExaminer
    from app.models.rubric import ExaminationRubric
    from app.models.slot import ExaminationSlot

EXAM_TYPES = ("viva", "practical", "project_demo", "assessment")
EXAM_STATUSES = ("draft", "slot_creation", "booking_open", "closed", "completed")


class Examination(db.Model, TimestampMixin):
    """
    Examination offering with defined timeline windows and capacity rules.
    """

    __tablename__ = "examinations"
    __table_args__ = (
        CheckConstraint(
            f"exam_type IN {EXAM_TYPES}",
            name="ck_examinations_exam_type_valid",
        ),
        CheckConstraint(
            f"status IN {EXAM_STATUSES}",
            name="ck_examinations_status_valid",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_examinations_duration_positive"),
        CheckConstraint("max_marks > 0", name="ck_examinations_max_marks_positive"),
        CheckConstraint(
            "slot_creation_start < slot_creation_end",
            name="ck_examinations_creation_window_order",
        ),
        CheckConstraint(
            "booking_start < booking_end",
            name="ck_examinations_booking_window_order",
        ),
        CheckConstraint(
            "slot_creation_end <= booking_start",
            name="ck_examinations_windows_do_not_overlap",
        ),
        Index("ix_examinations_course_id", "course_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Academic course parent
    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Examination type: 'viva' | 'practical' | 'project_demo' | 'assessment'
    exam_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Evaluation duration per student in minutes
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Maximum achievable marks
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)

    # Window 1: Slot Creation Period (when examiners create slots)
    slot_creation_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    slot_creation_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Window 2: Student Booking Period (when students discover and reserve slots)
    booking_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    booking_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Deadline before which students can cancel their booked slot
    cancellation_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Admin Master Switches (override schedule dates manually)
    slot_creation_open: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    booking_open: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    # Overall lifecycle status
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    # Soft deletion flag to preserve historic evaluation and booking records
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    # -----------------------------------------------------------------
    # Auto-default hook for cancellation_deadline
    # -----------------------------------------------------------------
    @validates("cancellation_deadline")
    def _validate_cancellation_deadline(self, key, value):
        """If cancellation_deadline is omitted, default it to booking_end."""
        if value is None and hasattr(self, "booking_end") and self.booking_end is not None:
            return self.booking_end
        return value

    # -----------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------
    course: Mapped["Course"] = relationship("Course", back_populates="examinations")
    rubrics: Mapped[list["ExaminationRubric"]] = relationship(
        "ExaminationRubric",
        back_populates="examination",
        order_by="ExaminationRubric.position",
        passive_deletes=False,
    )
    slots: Mapped[list["ExaminationSlot"]] = relationship(
        "ExaminationSlot",
        back_populates="examination",
        passive_deletes=False,
    )
    examiner_links: Mapped[list["ExaminationExaminer"]] = relationship(
        "ExaminationExaminer",
        back_populates="examination",
        passive_deletes=False,
    )

    def __repr__(self) -> str:
        return f"<Examination id={self.id} name={self.name!r} status={self.status!r}>"
