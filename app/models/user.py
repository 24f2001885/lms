from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import TimestampMixin, db

if TYPE_CHECKING:
    from app.models.examiner_profile import ExaminerProfile
    from app.models.student_profile import StudentProfile

# Enumerated constant values (reused across forms and services)
ROLES = ("admin", "examiner", "student")
APPROVAL_STATUSES = ("pending", "approved", "rejected")


class User(db.Model, TimestampMixin):
    """
    User account representing an Administrator, Examiner, or Student.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"role IN {ROLES}",
            name="ck_users_role_valid",
        ),
        CheckConstraint(
            f"approval_status IN {APPROVAL_STATUSES}",
            name="ck_users_approval_status_valid",
        ),
        CheckConstraint(
            "email = lower(email)",
            name="ck_users_email_lowercase",
        ),
        Index("ix_users_role", "role"),
        Index("ix_users_full_name", "full_name"),
        {"sqlite_autoincrement": True},  # Must be at the end of the tuple
    )

    # Primary key short integer ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique lowercase email address
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Scrypt password hash (never raw plain-text)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # User's display name
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # System role: 'admin' | 'examiner' | 'student'
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Examiner approval status: 'pending' | 'approved' | 'rejected'
    # Students and seeded Admin default to 'approved'; registering examiners default to 'pending'
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="approved",
        server_default="approved",
    )

    # Account active flag: deactivation sets this to False (preserving audit history)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    # Security flag: forces password reset on first login for seeded Admin
    # TDR 4.1 update: users.must_change_password
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    # Timestamp of the most recent successful login session
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # -----------------------------------------------------------------
    # Relationships (Strict 1-to-1 with profile tables; no cascades)
    # -----------------------------------------------------------------
    examiner_profile: Mapped[Optional["ExaminerProfile"]] = relationship(
        "ExaminerProfile",
        back_populates="user",
        uselist=False,
        passive_deletes=False,
    )
    student_profile: Mapped[Optional["StudentProfile"]] = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        passive_deletes=False,
    )

    @property
    def name(self) -> str:
        return self.full_name

    # -----------------------------------------------------------------
    # Password & Convenience Helpers
    # -----------------------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        """Hash and store a raw password using Werkzeug's default scrypt algorithm."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, candidate_password: str) -> bool:
        """Verify candidate password against the stored scrypt cryptographic hash."""
        return check_password_hash(self.password_hash, candidate_password)

    @property
    def is_admin(self) -> bool:
        """Return True if user has the 'admin' role."""
        return self.role == "admin"

    @property
    def is_examiner(self) -> bool:
        """Return True if user has the 'examiner' role."""
        return self.role == "examiner"

    @property
    def is_student(self) -> bool:
        """Return True if user has the 'student' role."""
        return self.role == "student"

    def __repr__(self) -> str:
        # Never expose password_hash in string representations or logs
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
