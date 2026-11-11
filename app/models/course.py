from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.examination import Examination
    from app.models.user import User

COURSE_STATUSES = ("active", "inactive")


class Course(db.Model, TimestampMixin):
    """
    Academic course entity containing examinations.
    """

    __tablename__ = "courses"
    __table_args__ = (
        
        CheckConstraint(
            f"status IN {COURSE_STATUSES}",
            name="ck_courses_status_valid",
        ),
        Index("ix_courses_status", "status"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique academic course code (e.g., 'CS2003')
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    # Full course name
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status: 'active' | 'inactive'
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    # Foreign key to users.id (Administrator who created the course)
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -----------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    examinations: Mapped[list["Examination"]] = relationship(
        "Examination",
        back_populates="course",
        passive_deletes=False,
    )

    def __repr__(self) -> str:
        return f"<Course id={self.id} code={self.code!r} status={self.status!r}>"