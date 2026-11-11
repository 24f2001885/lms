
from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.user import User

PROFILE_STATUSES = ("active", "inactive")


class ExaminerProfile(db.Model, TimestampMixin):
    """
    Profile extension holding academic details for an examiner.
    """

    __tablename__ = "examiner_profiles"
    __table_args__ = (
        
        CheckConstraint(
            f"status IN {PROFILE_STATUSES}",
            name="ck_examiner_profiles_status_valid",
            
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to users.id with RESTRICT to prevent deleting users with history
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )

    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Internal profile status ('active' | 'inactive')
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="examiner_profile")

    def __repr__(self) -> str:
        return f"<ExaminerProfile id={self.id} user_id={self.user_id} dept={self.department!r}>"