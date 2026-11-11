from datetime import datetime, timezone
from typing import Generator
import pytest
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner
from sqlalchemy.orm import Session

from app import create_app
from app.extensions import db
from app.models import (
    Booking,
    Course,
    Evaluation,
    EvaluationScore,
    Examination,
    ExaminationExaminer,
    ExaminationRubric,
    ExaminationSlot,
    ExaminerProfile,
    StudentProfile,
    User,
)

# Fixed base anchor timestamp for repeatable window tests (UTC)
BASE_DATETIME = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app(tmp_path) -> Generator[Flask, None, None]:
    """
    Create a fresh Flask application configured with a temporary file-based
    SQLite database in tmp_path (required for WAL mode and multi-connection tests).
    """
    db_file = tmp_path / "test.db"
    test_db_uri = f"sqlite:///{db_file}"

    test_app = create_app("testing")
    test_app.config["SQLALCHEMY_DATABASE_URI"] = test_db_uri

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Provide Flask test client for issuing simulated HTTP requests."""
    return app.test_client()


@pytest.fixture
def runner(app: Flask) -> FlaskCliRunner:
    """Provide Flask CLI runner for testing terminal commands like init-db."""
    return app.test_cli_runner()


@pytest.fixture
def session(app: Flask) -> Session:
    """Provide active SQLAlchemy session for direct DB queries."""
    return db.session


# Test Data Factory Fixtures
_user_seq = 0


@pytest.fixture
def make_user():
    """Factory fixture generating User accounts with automatic matching profiles."""

    def _make(
        role: str = "student",
        email: str | None = None,
        password: str = "Passw0rd123!",
        approval_status: str | None = None,
        is_active: bool = True,
        full_name: str | None = None,
        must_change_password: bool = False,
    ) -> User:
        global _user_seq
        _user_seq += 1

        if email is None:
            email = f"{role}_{_user_seq}@test.local"
        if full_name is None:
            full_name = f"Test {role.capitalize()} {_user_seq}"
        if approval_status is None:
            approval_status = "pending" if role == "examiner" else "approved"

        user = User(
            email=email.strip().lower(),
            full_name=full_name,
            role=role,
            approval_status=approval_status,
            is_active=is_active,
            must_change_password=must_change_password,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Create matching profile row
        if role == "examiner":
            profile = ExaminerProfile(
                user_id=user.id,
                department="Computer Science",
                designation="Assistant Professor",
            )
            db.session.add(profile)
        elif role == "student":
            profile = StudentProfile(
                user_id=user.id,
                roll_number=f"ROLL{_user_seq:04d}",
                program="B.Tech Computer Science",
            )
            db.session.add(profile)

        db.session.commit()
        return user

    return _make


@pytest.fixture
def make_admin(make_user):
    """Factory wrapper for Administrator accounts."""
    return lambda **kw: make_user(role="admin", **kw)


@pytest.fixture
def make_examiner(make_user):
    """Factory wrapper for Examiner accounts."""
    return lambda approved=True, **kw: make_user(
        role="examiner",
        approval_status="approved" if approved else "pending",
        **kw,
    )


@pytest.fixture
def make_student(make_user):
    """Factory wrapper for Student accounts."""
    return lambda **kw: make_user(role="student", **kw)


@pytest.fixture
def make_course(make_admin):
    """Factory fixture generating Course instances."""

    def _make(code: str | None = None, name: str | None = None, created_by: int | None = None) -> Course:
        global _user_seq
        _user_seq += 1
        if created_by is None:
            admin = make_admin()
            created_by = admin.id

        course = Course(
            code=code or f"CS{_user_seq:04d}",
            name=name or f"Course {_user_seq}",
            created_by=created_by,
        )
        db.session.add(course)
        db.session.commit()
        return course

    return _make


@pytest.fixture
def make_examination(make_course):
    """Factory fixture generating Examination instances with valid default windows."""

    def _make(course: Course | None = None, **overrides) -> Examination:
        global _user_seq
        _user_seq += 1
        if course is None:
            course = make_course()

        # Windows anchored at 2030-01-01
        defaults = {
            "name": f"Exam {_user_seq}",
            "exam_type": "viva",
            "duration_minutes": 30,
            "max_marks": 100,
            "slot_creation_start": datetime(2030, 1, 1, 0, 0, 0),
            "slot_creation_end": datetime(2030, 1, 10, 0, 0, 0),
            "booking_start": datetime(2030, 1, 10, 0, 0, 0),
            "booking_end": datetime(2030, 1, 20, 0, 0, 0),
            "cancellation_deadline": datetime(2030, 1, 20, 0, 0, 0),
            "status": "draft",
            "is_deleted": False,
        }
        defaults.update(overrides)

        exam = Examination(course_id=course.id, **defaults)
        db.session.add(exam)
        db.session.commit()
        return exam

    return _make


@pytest.fixture
def make_rubric():
    """Factory fixture generating rubric criteria for an examination."""

    def _make(
        examination: Examination,
        name: str = "Presentation",
        weightage: float = 25.0,
        max_score: float = 25.0,
        position: int = 0,
    ) -> ExaminationRubric:
        rubric = ExaminationRubric(
            examination_id=examination.id,
            criterion_name=name,
            weightage=weightage,
            max_score=max_score,
            position=position,
        )
        db.session.add(rubric)
        db.session.commit()
        return rubric

    return _make


@pytest.fixture
def make_slot():
    """Factory fixture generating an examination slot."""

    def _make(
        examination: Examination,
        examiner: User,
        capacity: int = 5,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> ExaminationSlot:
        slot = ExaminationSlot(
            examination_id=examination.id,
            examiner_id=examiner.id,
            start_at=start_at or datetime(2030, 1, 15, 10, 0, 0),
            end_at=end_at or datetime(2030, 1, 15, 12, 0, 0),
            max_capacity=capacity,
            booked_count=0,
            status="available",
        )
        db.session.add(slot)
        db.session.commit()
        return slot

    return _make


@pytest.fixture
def make_booking():
    """Factory fixture generating a booking reservation."""

    def _make(student: User, slot: ExaminationSlot, status: str = "booked") -> Booking:
        booking = Booking(
            student_id=student.id,
            slot_id=slot.id,
            examination_id=slot.examination_id,
            status=status,
            booked_at=datetime(2030, 1, 11, 10, 0, 0),
        )
        db.session.add(booking)
        db.session.commit()
        return booking

    return _make