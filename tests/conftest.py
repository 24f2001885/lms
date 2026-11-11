"""
tests/conftest.py - Pytest fixtures and factories updated for Phase P3.

Adds make_assignment, make_evaluation, freeze_now (monkeypatching windows.now_utc),
and admin_client (pre-authenticated administrator test client).
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
    Examination,
    ExaminationExaminer,
    ExaminationRubric,
    ExaminationSlot,
    ExaminerProfile,
    StudentProfile,
    User,
)

BASE_DATETIME = datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def app(tmp_path) -> Generator[Flask, None, None]:
    """Create a fresh Flask application configured with a temporary file-based SQLite database."""
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
    """Provide Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app: Flask) -> FlaskCliRunner:
    """Provide Flask CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def session(app: Flask) -> Session:
    """Provide active SQLAlchemy session."""
    return db.session


@pytest.fixture
def login(client: FlaskClient):
    """Helper fixture to log in a user via POST /login."""

    def _login(email: str, password: str = "Passw0rd123!"):
        return client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )

    return _login


@pytest.fixture
def admin_client(client: FlaskClient, make_admin, login) -> FlaskClient:
    """Provide pre-authenticated Administrator test client."""
    admin = make_admin(email="admin_client@test.local", password="Passw0rd123!", must_change_password=False)
    login(admin.email, "Passw0rd123!")
    return client


@pytest.fixture
def freeze_now(monkeypatch):
    """
    Monkeypatch app.services.windows.now_utc to return a frozen or moving datetime.
    Works because all modules call windows.now_utc() through the module object.
    """
    current_frozen = {"dt": datetime(2030, 1, 1, 0, 0, 0)}

    def _get_now():
        return current_frozen["dt"]

    monkeypatch.setattr("app.services.windows.now_utc", _get_now)

    def _set_time(new_dt: datetime):
        current_frozen["dt"] = new_dt

    return _set_time


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
    return lambda **kw: make_user(role="admin", **kw)


@pytest.fixture
def make_examiner(make_user):
    return lambda approved=True, **kw: make_user(
        role="examiner",
        approval_status="approved" if approved else "pending",
        **kw,
    )


@pytest.fixture
def make_student(make_user):
    return lambda **kw: make_user(role="student", **kw)


@pytest.fixture
def make_course(make_admin):
    def _make(code: str | None = None, name: str | None = None, created_by: int | None = None) -> Course:
        global _user_seq
        _user_seq += 1
        created_by = created_by or make_admin().id

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
    def _make(course: Course | None = None, **overrides) -> Examination:
        global _user_seq
        _user_seq += 1
        if course is None:
            course = make_course()

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
        if "booking_start" not in overrides and defaults["booking_start"] < defaults["slot_creation_end"]:
            defaults["booking_start"] = defaults["slot_creation_end"]
            if "booking_end" not in overrides and defaults["booking_end"] <= defaults["booking_start"]:
                defaults["booking_end"] = defaults["booking_start"] + timedelta(days=10)
            if "cancellation_deadline" not in overrides and defaults["cancellation_deadline"] < defaults["booking_start"]:
                defaults["cancellation_deadline"] = defaults["booking_end"]
        if "slot_creation_end" not in overrides and defaults["slot_creation_end"] > defaults["booking_start"]:
            defaults["slot_creation_end"] = defaults["booking_start"]
            if "slot_creation_start" not in overrides and defaults["slot_creation_start"] >= defaults["slot_creation_end"]:
                defaults["slot_creation_start"] = defaults["slot_creation_end"] - timedelta(days=5)

        exam = Examination(course_id=course.id, **defaults)
        db.session.add(exam)
        db.session.commit()
        return exam

    return _make


@pytest.fixture
def make_rubric():
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
            weightage=Decimal(str(weightage)),
            max_score=Decimal(str(max_score)),
            position=position,
        )
        db.session.add(rubric)
        db.session.commit()
        return rubric

    return _make


@pytest.fixture
def make_slot():
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


@pytest.fixture
def make_assignment():
    """Factory fixture generating examiner assignments."""

    def _make(examination: Examination, examiner: User, assigned_by: User | None = None) -> ExaminationExaminer:
        assignment = ExaminationExaminer(
            examination_id=examination.id,
            examiner_id=examiner.id,
            assigned_by=assigned_by.id if assigned_by else examination.course.creator.id,
        )
        db.session.add(assignment)
        db.session.commit()
        return assignment

    return _make


@pytest.fixture
def make_evaluation():
    """Factory fixture generating evaluation records."""

    def _make(booking: Booking, examiner: User, status: str = "draft", total: float = 0.0) -> Evaluation:
        ev = Evaluation(
            booking_id=booking.id,
            examiner_id=examiner.id,
            status=status,
            total_marks=Decimal(str(total)),
        )
        db.session.add(ev)
        db.session.commit()
        return ev

    return _make