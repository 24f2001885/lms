"""
app/models/student_profile.py - Student profile details model for LMS.

Stores role-specific academic metadata for enrolled students (roll number,
academic program, contact phone) linked 1-to-1 to users.
"""

from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.user import User


class StudentProfile(db.Model, TimestampMixin):
    """
    Profile extension holding academic details for an enrolled student.
    """

    __tablename__ = "student_profiles"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to users.id with RESTRICT
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )

    # Optional roll number (unique when present; SQLite permits multiple NULLs)
    roll_number: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)

    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="student_profile")

    def __repr__(self) -> str:
        return f"<StudentProfile id={self.id} user_id={self.user_id} roll={self.roll_number!r}>"