from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.examination import Examination


class ExaminationRubric(db.Model):
    """
    Evaluation rubric criterion linked to an examination.
    Note: As specified in TDR Section 4.1, rubrics do not require TimestampMixin.
    """

    __tablename__ = "examination_rubrics"
    __table_args__ = (
        CheckConstraint(
            "weightage >= 0 AND weightage <= 100",
            name="ck_examination_rubrics_weightage_range",
        ),
        CheckConstraint("max_score > 0", name="ck_examination_rubrics_max_score_positive"),
        UniqueConstraint("examination_id", "criterion_name", name="uq_rubrics_exam_criterion"),
        Index("ix_rubrics_examination_id", "examination_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Examination parent
    examination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("examinations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Criterion title (e.g., 'System Architecture & Design')
    criterion_name: Mapped[str] = mapped_column(String(120), nullable=False)

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Percentage weightage (0.00 to 100.00)
    weightage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # Maximum score achievable for this criterion
    max_score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)

    # Display sorting position
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Relationship back to Examination
    examination: Mapped["Examination"] = relationship("Examination", back_populates="rubrics")

    @property
    def name(self) -> str:
        return self.criterion_name

    def __repr__(self) -> str:
        return f"<ExaminationRubric id={self.id} exam_id={self.examination_id} name={self.criterion_name!r}>"
