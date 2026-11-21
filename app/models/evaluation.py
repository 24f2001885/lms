from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.rubric import ExaminationRubric
    from app.models.user import User

EVALUATION_STATUSES = ("draft", "submitted", "published")


class Evaluation(db.Model, TimestampMixin):
    """
    Evaluation submitted by an examiner for a student's booked examination slot.
    """

    __tablename__ = "evaluations"
    __table_args__ = (
        CheckConstraint(
            f"status IN {EVALUATION_STATUSES}",
            name="ck_evaluations_status_valid",
        ),
        CheckConstraint("total_marks >= 0", name="ck_evaluations_total_marks_non_negative"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Exactly one evaluation per booking
    booking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )

    # Examiner who actually conducted this evaluation
    examiner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Calculated total score (sum of criteria scores)
    total_marks: Mapped[float] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: 'draft' (private) | 'submitted' (locked) | 'published' (visible to student)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # -----------------------------------------------------------------
    # Relationships
    # Note: Evaluation.scores is the ONLY cascade="all, delete-orphan" in the system
    # -----------------------------------------------------------------
    booking: Mapped["Booking"] = relationship("Booking", back_populates="evaluation")
    examiner: Mapped["User"] = relationship("User", foreign_keys=[examiner_id])
    scores: Mapped[list["EvaluationScore"]] = relationship(
        "EvaluationScore",
        back_populates="evaluation",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )

    def __repr__(self) -> str:
        return f"<Evaluation id={self.id} booking_id={self.booking_id} status={self.status!r} total={self.total_marks}>"


class EvaluationScore(db.Model):
    """
    Individual rubric criterion score within an evaluation.
    """

    __tablename__ = "evaluation_scores"
    __table_args__ = (
        CheckConstraint("score >= 0", name="ck_evaluation_scores_score_non_negative"),
        UniqueConstraint("evaluation_id", "rubric_id", name="uq_evaluation_rubric_score"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    evaluation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )

    rubric_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examination_rubrics.id", ondelete="RESTRICT"),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationship back to Evaluation
    evaluation: Mapped["Evaluation"] = relationship("Evaluation", back_populates="scores")
    rubric: Mapped["ExaminationRubric"] = relationship("ExaminationRubric")

    def __repr__(self) -> str:
        return f"<EvaluationScore id={self.id} eval_id={self.evaluation_id} rubric_id={self.rubric_id} score={self.score}>"
