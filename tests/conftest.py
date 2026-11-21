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

    test_app = create_app("testing", test_config={"SQLALCHEMY_DATABASE_URI": test_db_uri})

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
def db_session(session: Session) -> Session:
    """Alias for session fixture."""
    return session


@pytest.fixture
def admin(make_admin) -> User:
    """Provide a default administrator user."""
    return make_admin()


@pytest.fixture
def examiner(make_examiner) -> User:
    """Provide a default approved examiner user."""
    return make_examiner()


@pytest.fixture
def student(make_student) -> User:
    """Provide a default student user."""
    return make_student()


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
    admin = make_admin(
        email="admin_client@test.local", password="Passw0rd123!", must_change_password=False
    )
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
    def _make(
        code: str | None = None, name: str | None = None, created_by: int | None = None
    ) -> Course:
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
        if (
            "booking_start" not in overrides
            and defaults["booking_start"] < defaults["slot_creation_end"]
        ):
            defaults["booking_start"] = defaults["slot_creation_end"]
            if (
                "booking_end" not in overrides
                and defaults["booking_end"] <= defaults["booking_start"]
            ):
                defaults["booking_end"] = defaults["booking_start"] + timedelta(days=10)
            if (
                "cancellation_deadline" not in overrides
                and defaults["cancellation_deadline"] < defaults["booking_start"]
            ):
                defaults["cancellation_deadline"] = defaults["booking_end"]
        if (
            "slot_creation_end" not in overrides
            and defaults["slot_creation_end"] > defaults["booking_start"]
        ):
            defaults["slot_creation_end"] = defaults["booking_start"]
            if (
                "slot_creation_start" not in overrides
                and defaults["slot_creation_start"] >= defaults["slot_creation_end"]
            ):
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

    def _make(
        examination: Examination, examiner: User, assigned_by: User | None = None
    ) -> ExaminationExaminer:
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

    def _make(
        booking: Booking, examiner: User, status: str = "draft", total: float = 0.0
    ) -> Evaluation:
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


@pytest.fixture
def examiner_client(client, examiner, db_session):
    """Creates an approved active examiner and logs in via POST /login."""
    examiner.approval_status = "approved"
    examiner.is_active = True
    examiner.must_change_password = False
    db_session.commit()

    client.post(
        "/login",
        data={
            "email": examiner.email,
            "password": "Passw0rd123!",
        },
        follow_redirects=True,
    )
    return client, examiner


@pytest.fixture
def make_ready_examination(
    make_examiner,
    make_admin,
    make_course,
    make_examination,
    make_rubric,
    make_assignment,
):
    """Factory to create an examination ready for slot creation and booking."""

    def _factory(examiner=None, now=None):
        from app.services import windows

        if not examiner:
            examiner = User.query.filter_by(role="examiner").first() or make_examiner()

        admin_user = User.query.filter_by(role="admin").first() or make_admin()
        course = make_course(created_by=admin_user.id)

        current_time = now if now else windows.now_utc()
        exam = make_examination(
            course=course,
            name="Final Viva",
            exam_type="viva",
            duration_minutes=30,
            max_marks=100,
            status="slot_creation",
            slot_creation_open=True,
            slot_creation_start=current_time - timedelta(days=1),
            slot_creation_end=current_time + timedelta(days=2),
            booking_start=current_time + timedelta(days=3),
            booking_end=current_time + timedelta(days=8),
            cancellation_deadline=current_time + timedelta(days=8),
        )

        make_rubric(exam, name="Technical Depth", weightage=60, max_score=60.0, position=1)
        make_rubric(exam, name="Communication", weightage=40, max_score=40.0, position=2)
        make_assignment(exam, examiner, assigned_by=admin_user)

        return exam, examiner

    return _factory


@pytest.fixture
def make_booking_with_slot(db_session, make_student):
    """Helper to create a slot and a student booking."""

    def _helper(examination, examiner, student=None, status="booked"):
        if not student:
            student = make_student()

        slot = ExaminationSlot(
            examination_id=examination.id,
            examiner_id=examiner.id,
            start_at=examination.booking_end + timedelta(days=1),
            end_at=examination.booking_end + timedelta(days=1, hours=1),
            max_capacity=10,
            booked_count=1 if status in ("booked", "completed") else 0,
            status="available",
        )
        db_session.add(slot)
        db_session.flush()

        booking = Booking(
            slot_id=slot.id,
            student_id=student.id,
            examination_id=examination.id,
            status=status,
            booked_at=examination.booking_start + timedelta(hours=1),
        )
        db_session.add(booking)
        db_session.commit()
        return booking, slot

    return _helper


@pytest.fixture
def student_client(client, student, db_session):
    """Creates an active student (must_change_password False), logs in via POST /login and returns (client, student)."""
    student.is_active = True
    student.must_change_password = False
    db_session.commit()

    client.post(
        "/login",
        data={
            "email": student.email,
            "password": "Passw0rd123!",
        },
        follow_redirects=True,
    )
    return client, student


@pytest.fixture
def make_open_booking_setup(
    db_session,
    make_examiner,
    make_admin,
    make_course,
    make_examination,
    make_rubric,
    make_assignment,
    make_student,
):
    """
    Builds a ready examination whose BOOKING window contains the frozen now
    (booking_open True, rubric total 100, approved assigned examiner)
    with one future available slot, returns (examination, slot, examiner, students).
    """

    def _setup(student_count=1, capacity=5):
        from app.services import windows

        now = windows.now_utc()

        examiner = make_examiner()
        admin_user = make_admin()
        course = make_course(created_by=admin_user.id)

        exam = make_examination(
            course=course,
            name="Midterm Viva",
            exam_type="viva",
            duration_minutes=30,
            max_marks=100,
            status="booking_open",
            slot_creation_open=True,
            booking_open=True,
            slot_creation_start=now - timedelta(days=5),
            slot_creation_end=now - timedelta(days=2),
            booking_start=now - timedelta(days=1),
            booking_end=now + timedelta(days=5),
            cancellation_deadline=now + timedelta(days=5),
        )

        make_rubric(exam, name="Technical Depth", weightage=60, max_score=60.0, position=1)
        make_rubric(exam, name="Communication", weightage=40, max_score=40.0, position=2)
        make_assignment(exam, examiner, assigned_by=admin_user)

        slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=examiner.id,
            start_at=exam.booking_end + timedelta(days=1),
            end_at=exam.booking_end + timedelta(days=1, hours=1),
            max_capacity=capacity,
            booked_count=0,
            status="available",
        )
        db_session.add(slot)
        db_session.commit()

        students = [make_student() for _ in range(student_count)]
        return exam, slot, examiner, students

    return _setup


@pytest.fixture
def make_published_evaluation(db_session):
    """Creates an evaluation with status published and per-criterion scores summing to total."""

    def _make(booking, examiner, total=85):
        from app.models import Evaluation, EvaluationScore
        from app.services import windows

        evaluation = Evaluation(
            booking_id=booking.id,
            examiner_id=examiner.id,
            total_marks=Decimal(str(total)),
            status="published",
            submitted_at=windows.now_utc(),
            published_at=windows.now_utc(),
        )
        db_session.add(evaluation)
        db_session.flush()

        rubrics = booking.slot.examination.rubrics
        if rubrics:
            remaining = Decimal(str(total))
            for i, r in enumerate(rubrics):
                if i == len(rubrics) - 1:
                    score = remaining
                else:
                    score = min(remaining, Decimal(str(r.max_score)))
                    remaining -= score
                sc = EvaluationScore(
                    evaluation=evaluation,
                    rubric_id=r.id,
                    score=score,
                    comment="Well done",
                )
                db_session.add(sc)

        db_session.commit()
        return evaluation

    return _make


# --- Phase 6 Additions ---
from tests.conftest_p6_additions import MutableClock, clock, run_in_threads  # noqa: E402, F401
