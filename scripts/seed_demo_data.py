"""
FILE PURPOSE: Fill a fresh database with realistic demo data using ONLY the service layer.
"""

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    Course,
    Examination,
    ExaminationExaminer,
    ExaminationRubric,
    ExaminerProfile,
    StudentProfile,
    User,
)
from app.services import (
    admin_service,
    booking_engine,
    evaluation_service,
    exam_status,
    slot_service,
    windows,
)


@contextmanager
def fake_clock(target_dt: datetime):
    original = windows.now_utc
    windows.now_utc = lambda: target_dt
    try:
        yield
    finally:
        windows.now_utc = original


def main(app=None):
    if os.environ.get("FLASK_ENV") == "production":
        print("ERROR: Refusing to seed demo data in production.", file=sys.stderr)
        sys.exit(1)

    if app is None:
        app = create_app()

    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not db_uri.startswith("sqlite:///"):
        print("ERROR: Demo seed only runs against a local SQLite database.", file=sys.stderr)
        sys.exit(1)

    demo_password = os.environ.get("DEMO_PASSWORD", "Demo#12345")

    with app.app_context():
        orig_suppress = app.config.get("MAIL_SUPPRESS_SEND")
        orig_async = app.config.get("MAIL_ASYNC")
        app.config["MAIL_SUPPRESS_SEND"] = True
        app.config["MAIL_ASYNC"] = False

        db.create_all()
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(
                email=os.environ.get("ADMIN_EMAIL", "admin@example.edu"),
                password_hash=generate_password_hash(
                    os.environ.get("ADMIN_INITIAL_PASSWORD", "Admin#12345")
                ),
                full_name="System Admin",
                role="admin",
                approval_status="approved",
                is_active=True,
            )
            db.session.add(admin)
            db.session.commit()

        if Course.query.filter_by(code="DEMO101").first():
            print("Demo data already present.")
            app.config["MAIL_SUPPRESS_SEND"] = orig_suppress
            app.config["MAIL_ASYNC"] = orig_async
            return

        base_now = windows.now_utc()
        pw_hash = generate_password_hash(demo_password)

        try:
            # 1. Examiners (3 approved, 1 pending)
            examiners = []
            for idx in range(1, 4):
                u = User(
                    email=f"examiner{idx}@demo.local",
                    password_hash=pw_hash,
                    full_name=f"Dr. Examiner {idx}",
                    role="examiner",
                    approval_status="pending",
                    is_active=True,
                )
                db.session.add(u)
                db.session.flush()
                db.session.add(ExaminerProfile(user_id=u.id, department="Computer Science"))
                db.session.commit()
                admin_service.approve_examiner(admin.id, u.id)
                examiners.append(u)

            pending_ex = User(
                email="examiner.pending@demo.local",
                password_hash=pw_hash,
                full_name="Pending Examiner",
                role="examiner",
                approval_status="pending",
                is_active=True,
            )
            db.session.add(pending_ex)
            db.session.flush()
            db.session.add(ExaminerProfile(user_id=pending_ex.id, department="Mathematics"))
            db.session.commit()

            # 2. 20 Students
            students = []
            for idx in range(1, 21):
                st = User(
                    email=f"student{idx:02d}@demo.local",
                    password_hash=pw_hash,
                    full_name=f"Student {idx:02d}",
                    role="student",
                    approval_status="approved",
                    is_active=True,
                )
                db.session.add(st)
                db.session.flush()
                db.session.add(StudentProfile(user_id=st.id, roll_number=f"26CS{idx:03d}"))
                students.append(st)
            db.session.commit()

            # 3. Courses
            c_active = Course(
                code="DEMO101",
                name="Core Computer Science",
                description="Active demo course",
                status="active",
                created_by=admin.id,
            )
            c_inactive = Course(
                code="DEMO102",
                name="Legacy Systems",
                description="Inactive demo course",
                status="inactive",
                created_by=admin.id,
            )
            db.session.add_all([c_active, c_inactive])
            db.session.commit()

            # 4. Examination A: Booking OPEN right now
            exam_a = Examination(
                course_id=c_active.id,
                name="Viva - Data Structures",
                exam_type="viva",
                duration_minutes=30,
                max_marks=100,
                slot_creation_start=base_now - timedelta(days=10),
                slot_creation_end=base_now - timedelta(days=5),
                booking_start=base_now - timedelta(days=4),
                booking_end=base_now + timedelta(days=10),
                cancellation_deadline=base_now + timedelta(days=8),
                slot_creation_open=True,
                booking_open=False,
                status="slot_creation",
            )
            db.session.add(exam_a)
            db.session.flush()
            db.session.add_all(
                [
                    ExaminationRubric(
                        examination_id=exam_a.id,
                        criterion_name="Concept",
                        weightage=Decimal("40"),
                        max_score=Decimal("40"),
                        position=1,
                    ),
                    ExaminationRubric(
                        examination_id=exam_a.id,
                        criterion_name="Implementation",
                        weightage=Decimal("40"),
                        max_score=Decimal("40"),
                        position=2,
                    ),
                    ExaminationRubric(
                        examination_id=exam_a.id,
                        criterion_name="Communication",
                        weightage=Decimal("20"),
                        max_score=Decimal("20"),
                        position=3,
                    ),
                    ExaminationExaminer(
                        examination_id=exam_a.id,
                        examiner_id=examiners[0].id,
                        assigned_by=admin.id,
                        assigned_at=base_now - timedelta(days=10),
                    ),
                    ExaminationExaminer(
                        examination_id=exam_a.id,
                        examiner_id=examiners[1].id,
                        assigned_by=admin.id,
                        assigned_at=base_now - timedelta(days=10),
                    ),
                ]
            )
            db.session.commit()

            with fake_clock(base_now - timedelta(days=7)):
                s_a1 = slot_service.create_slot(
                    examiners[0].id,
                    exam_a.id,
                    base_now + timedelta(days=2),
                    base_now + timedelta(days=2, hours=2),
                    3,
                )
                s_a2 = slot_service.create_slot(
                    examiners[0].id,
                    exam_a.id,
                    base_now + timedelta(days=3),
                    base_now + timedelta(days=3, hours=2),
                    3,
                )
                s_a3 = slot_service.create_slot(
                    examiners[1].id,
                    exam_a.id,
                    base_now + timedelta(days=4),
                    base_now + timedelta(days=4, hours=2),
                    2,
                )
                s_a4 = slot_service.create_slot(
                    examiners[1].id,
                    exam_a.id,
                    base_now + timedelta(days=5),
                    base_now + timedelta(days=5, hours=1),
                    1,
                )

            exam_a.slot_creation_open = False
            exam_a.booking_open = True
            exam_a.status = "booking_open"
            db.session.commit()

            with fake_clock(base_now - timedelta(days=1)):
                # Fill slot s_a1 (capacity 3)
                for idx in range(3):
                    booking_engine.book_slot(students[idx].id, s_a1.id)
                # Book 3 into s_a2, cancel one, reschedule one
                for idx in range(3, 6):
                    booking_engine.book_slot(students[idx].id, s_a2.id)
                b_cancel = booking_engine.book_slot(students[6].id, s_a3.id)
                booking_engine.cancel_booking(students[6].id, b_cancel.id)
                b_move = booking_engine.book_slot(students[7].id, s_a3.id)
                booking_engine.reschedule_booking(b_move.id, s_a4.id, admin.id)
                booking_engine.book_slot(students[8].id, s_a3.id)

            # 5. Examination B: Slot Creation OPEN right now
            exam_b = Examination(
                course_id=c_active.id,
                name="Practical - Databases",
                exam_type="practical",
                duration_minutes=60,
                max_marks=100,
                slot_creation_start=base_now - timedelta(days=1),
                slot_creation_end=base_now + timedelta(days=3),
                booking_start=base_now + timedelta(days=4),
                booking_end=base_now + timedelta(days=12),
                cancellation_deadline=base_now + timedelta(days=10),
                slot_creation_open=True,
                booking_open=False,
                status="slot_creation",
            )
            db.session.add(exam_b)
            db.session.flush()
            db.session.add_all(
                [
                    ExaminationRubric(
                        examination_id=exam_b.id,
                        criterion_name="Queries",
                        weightage=Decimal("60"),
                        max_score=Decimal("60"),
                        position=1,
                    ),
                    ExaminationRubric(
                        examination_id=exam_b.id,
                        criterion_name="Schema",
                        weightage=Decimal("40"),
                        max_score=Decimal("40"),
                        position=2,
                    ),
                    ExaminationExaminer(
                        examination_id=exam_b.id,
                        examiner_id=examiners[0].id,
                        assigned_by=admin.id,
                        assigned_at=base_now,
                    ),
                    ExaminationExaminer(
                        examination_id=exam_b.id,
                        examiner_id=examiners[2].id,
                        assigned_by=admin.id,
                        assigned_at=base_now,
                    ),
                ]
            )
            db.session.commit()

            # 6. Examination C: Past & Completed
            exam_c = Examination(
                course_id=c_active.id,
                name="Project demo - Web",
                exam_type="project_demo",
                duration_minutes=45,
                max_marks=100,
                slot_creation_start=base_now - timedelta(days=20),
                slot_creation_end=base_now - timedelta(days=15),
                booking_start=base_now - timedelta(days=14),
                booking_end=base_now - timedelta(days=8),
                cancellation_deadline=base_now - timedelta(days=9),
                slot_creation_open=True,
                booking_open=False,
                status="slot_creation",
            )
            db.session.add(exam_c)
            db.session.flush()
            r_c1 = ExaminationRubric(
                examination_id=exam_c.id,
                criterion_name="Architecture",
                weightage=Decimal("50"),
                max_score=Decimal("50"),
                position=1,
            )
            r_c2 = ExaminationRubric(
                examination_id=exam_c.id,
                criterion_name="Delivery",
                weightage=Decimal("50"),
                max_score=Decimal("50"),
                position=2,
            )
            db.session.add_all(
                [
                    r_c1,
                    r_c2,
                    ExaminationExaminer(
                        examination_id=exam_c.id,
                        examiner_id=examiners[2].id,
                        assigned_by=admin.id,
                        assigned_at=base_now - timedelta(days=20),
                    ),
                ]
            )
            db.session.commit()

            with fake_clock(base_now - timedelta(days=18)):
                s_c1 = slot_service.create_slot(
                    examiners[2].id,
                    exam_c.id,
                    base_now - timedelta(days=6),
                    base_now - timedelta(days=6) + timedelta(hours=4),
                    6,
                )

            exam_c.slot_creation_open = False
            exam_c.booking_open = True
            exam_c.status = "booking_open"
            db.session.commit()

            past_bookings = []
            with fake_clock(base_now - timedelta(days=11)):
                for idx in range(10, 16):
                    past_bookings.append(booking_engine.book_slot(students[idx].id, s_c1.id))

            exam_c.booking_open = False
            db.session.commit()

            exam_status.sync_all(now=base_now)

            # Evaluate 5 of 6 bookings (4 published, 1 submitted)
            for idx in range(5):
                ev = evaluation_service.save_evaluation(
                    examiner_id=examiners[2].id,
                    booking_id=past_bookings[idx].id,
                    scores={r_c1.id: Decimal("42"), r_c2.id: Decimal("43")},
                    remarks="Well structured demo.",
                    submit=True,
                )
                if idx < 4:
                    evaluation_service.publish_evaluation(examiners[2].id, ev.id)

            exam_status.sync_all(now=base_now)

            print("Demo data created successfully:")
            print("  Accounts: 1 Admin, 4 Examiners (3 approved, 1 pending), 20 Students")
            print(f"  Demo Password: {demo_password}")
            print("  Examinations:")
            print("    - Viva - Data Structures (booking_open)")
            print("    - Practical - Databases (slot_creation)")
            print("    - Project demo - Web (completed, 4 published results)")
            from app.models.email_log import EmailLog

            email_count = EmailLog.query.count()
            print(f"  Email logs created: {email_count}")
            print("  Login URL: http://127.0.0.1:5000/login")

        except Exception as exc:
            db.session.rollback()
            print(f"ERROR: Demo seed failed: {exc}", file=sys.stderr)
            sys.exit(1)
        finally:
            app.config["MAIL_SUPPRESS_SEND"] = orig_suppress
            app.config["MAIL_ASYNC"] = orig_async


if __name__ == "__main__":
    main()
