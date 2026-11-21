from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.examination import Examination
    from app.models.user import User


class ExaminationExaminer(db.Model):
    """
    Junction association linking an examination with an assigned examiner.
    """

    __tablename__ = "examination_examiners"
    __table_args__ = (
        UniqueConstraint("examination_id", "examiner_id", name="uq_exam_examiner_assignment"),
        Index("ix_exam_examiner_exam", "examination_id"),
        Index("ix_exam_examiner_examiner", "examiner_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to examinations.id
    examination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examinations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Foreign key to users.id (the assigned faculty examiner)
    examiner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Foreign key to users.id (the administrator who performed the assignment)
    assigned_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # -----------------------------------------------------------------
    # Relationships with Explicit Foreign Keys (Prevents Ambiguity Error)
    # -----------------------------------------------------------------
    examination: Mapped["Examination"] = relationship(
        "Examination",
        back_populates="examiner_links",
    )
    examiner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[examiner_id],
    )
    assigner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_by],
    )

    def __repr__(self) -> str:
        return f"<ExaminationExaminer exam_id={self.examination_id} examiner_id={self.examiner_id}>"
