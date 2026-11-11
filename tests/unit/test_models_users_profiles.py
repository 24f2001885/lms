import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ExaminerProfile, User


def test_user_role_check(app, make_user):
    """Verify that an invalid role is rejected by the check constraint."""
    user = User(
        email="invalid_role@test.local",
        full_name="Bad Role",
        role="superuser",  # Invalid role
        password_hash="fakehash",
    )
    db.session.add(user)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_approval_status_check(app):
    """Verify that an invalid approval status is rejected by check constraint."""
    user = User(
        email="bad_status@test.local",
        full_name="Bad Status",
        role="examiner",
        approval_status="maybe",  # Invalid status
        password_hash="fakehash",
    )
    db.session.add(user)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_email_unique(app, make_user):
    """Verify that duplicate email addresses are rejected."""
    make_user(email="duplicate@test.local")
    user2 = User(
        email="duplicate@test.local",
        full_name="Second User",
        role="student",
        password_hash="fakehash",
    )
    db.session.add(user2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_email_case_duplicate_rejected(app, make_user):
    """Verify that uppercase emails violate the email_lowercase check constraint."""
    user = User(
        email="UPPERCASE@TEST.LOCAL",
        full_name="Upper User",
        role="student",
        password_hash="fakehash",
    )
    db.session.add(user)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_defaults(app):
    """Verify default boolean and status flags upon user creation."""
    user = User(
        email="defaults@test.local",
        full_name="Default User",
        role="student",
        password_hash="fakehash",
    )
    db.session.add(user)
    db.session.commit()

    assert user.is_active is True
    assert user.approval_status == "approved"
    assert user.must_change_password is False


def test_password_hashing_roundtrip(app):
    """Verify set_password and check_password correctness."""
    user = User(
        email="hash_test@test.local",
        full_name="Hash User",
        role="student",
    )
    user.set_password("SecurePass123!")
    assert user.check_password("SecurePass123!") is True
    assert user.check_password("WrongPassword") is False
    assert user.password_hash != "SecurePass123!"


def test_examiner_profile_one_per_user(app, make_examiner):
    """Verify that a second examiner profile for the same user is rejected."""
    examiner = make_examiner()
    duplicate_profile = ExaminerProfile(user_id=examiner.id, department="Math")
    db.session.add(duplicate_profile)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_student_roll_number_unique(app, make_student):
    """Verify that two students cannot share the same roll number."""
    s1 = make_student()
    s2 = make_student()

    s1.student_profile.roll_number = "ROLL9999"
    db.session.commit()

    s2.student_profile.roll_number = "ROLL9999"
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_student_roll_number_nullable_many(app, make_student):
    """Verify that multiple students can have NULL roll numbers."""
    s1 = make_student()
    s2 = make_student()

    s1.student_profile.roll_number = None
    s2.student_profile.roll_number = None
    db.session.commit()  # Must not raise IntegrityError


def test_delete_user_with_profile_restricted(app, make_student):
    """Verify ondelete='RESTRICT' blocks deleting a User with an active profile."""
    student = make_student()
    db.session.delete(student)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_repr_hides_password(app, make_user):
    """Verify __repr__ does not reveal password hash."""
    user = make_user(password="SecretPassword123!")
    repr_str = repr(user)
    assert "SecretPassword123!" not in repr_str
    assert "password_hash" not in repr_str