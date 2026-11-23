"""
app/services/recruiter_demo.py - Idempotent Recruiter Demo Seeder.

Provisions realistic, production-grade demo entities for recruiters and reviewers:
- Administrator: admin@lms.com / Demo@123
- Examiner: examiner@lms.com / Demo@123 (linked to active CS201 & CS301 courses)
- Student: student@lms.com / Demo@123 (enrolled with completed viva & quiz scorecards)
- 2 Scheduled Examination sessions with bookable slots and capacity limits
- 1 Sample MCQ assessment test demonstrating the online proctored quiz engine
- Evaluated exam records with rubric scoring so Chart.js visual analytics populate immediately.
"""

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models.booking import Booking
from app.models.course import Course
from app.models.evaluation import Evaluation, EvaluationScore
from app.models.examination import Examination
from app.models.examination_examiner import ExaminationExaminer
from app.models.examiner_profile import ExaminerProfile
from app.models.rubric import ExaminationRubric
from app.models.slot import ExaminationSlot
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.services import windows

DEMO_PASSWORD = "Demo@123"  # noqa: S105


def _ensure_user(email: str, full_name: str, role: str) -> User:
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(
            email=email,
            full_name=full_name,
            role=role,
            approval_status="approved",
            is_active=True,
            must_change_password=False,
        )
        u.set_password(DEMO_PASSWORD)
        db.session.add(u)
        db.session.flush()
    else:
        u.set_password(DEMO_PASSWORD)
        u.is_active = True
        u.approval_status = "approved"
        u.must_change_password = False
    return u


def seed_recruiter_demo_data() -> dict:
    """Idempotently seed the full recruiter demo dataset."""
    now = windows.now_utc()

    # -------------------------------------------------------------------------
    # 1. Administrators: abhishekpathak4312@gmail.com & admin@lms.com
    # -------------------------------------------------------------------------
    admin = _ensure_user("abhishekpathak4312@gmail.com", "Abhishek Pathak", "admin")
    _ensure_user("admin@lms.com", "System Administrator", "admin")

    # -------------------------------------------------------------------------
    # 2. Examiners: examiner@demo.com & examiner@lms.com
    # -------------------------------------------------------------------------
    examiner = _ensure_user("examiner@demo.com", "Prof. Sarah Jenkins", "examiner")
    examiner_alt = _ensure_user("examiner@lms.com", "Prof. Sarah Jenkins", "examiner")

    for ex in (examiner, examiner_alt):
        ex_profile = ExaminerProfile.query.filter_by(user_id=ex.id).first()
        if not ex_profile:
            ex_profile = ExaminerProfile(
                user_id=ex.id,
                department="Computer Science & Engineering",
                designation="Associate Professor",
                contact_phone="+91 9876543210",
                status="active",
            )
            db.session.add(ex_profile)
        else:
            ex_profile.status = "active"

    # -------------------------------------------------------------------------
    # 3. Students: student@demo.com & student@lms.com
    # -------------------------------------------------------------------------
    student = _ensure_user("student@demo.com", "Alex Mercer", "student")
    student_alt = _ensure_user("student@lms.com", "Alex Mercer", "student")

    stu_profiles_data = [
        (student, "CS2026-0042"),
        (student_alt, "CS2026-0043"),
    ]
    for st, roll in stu_profiles_data:
        stu_profile = StudentProfile.query.filter_by(user_id=st.id).first()
        if not stu_profile:
            stu_profile = StudentProfile(
                user_id=st.id,
                roll_number=roll,
                program="B.Tech Computer Science",
                contact_phone="+91 9123456789",
            )
            db.session.add(stu_profile)

    # -------------------------------------------------------------------------
    # 4. Courses: Data Structures & Algorithms & Database Systems
    # -------------------------------------------------------------------------
    course_dsa = Course.query.filter_by(code="CS201").first()
    if not course_dsa:
        course_dsa = Course(
            code="CS201",
            name="Data Structures & Algorithms",
            description="Core algorithms, balanced search trees, graph theory, and dynamic programming.",
            status="active",
            created_by=admin.id,
        )
        db.session.add(course_dsa)
        db.session.flush()
    else:
        course_dsa.name = "Data Structures & Algorithms"
        course_dsa.status = "active"

    course_db = Course.query.filter_by(code="CS301").first()
    if not course_db:
        course_db = Course(
            code="CS301",
            name="Database Systems",
            description="Relational data modeling, indexing, transaction recovery, and SQL query tuning.",
            status="active",
            created_by=admin.id,
        )
        db.session.add(course_db)
        db.session.flush()
    else:
        course_db.name = "Database Systems"
        course_db.status = "active"

    # -------------------------------------------------------------------------
    # 5. Examination 1: DSA Comprehensive Oral Viva (Session 1)
    # -------------------------------------------------------------------------
    exam_viva = Examination.query.filter_by(name="DSA Comprehensive Oral Viva").first()
    if not exam_viva:
        exam_viva = Examination(
            course_id=course_dsa.id,
            name="DSA Comprehensive Oral Viva",
            description="Oral defense evaluating runtime complexity, graph traversals, and dynamic programming.",
            exam_type="viva",
            duration_minutes=20,
            max_marks=100,
            slot_creation_start=now - timedelta(days=12),
            slot_creation_end=now - timedelta(days=6),
            booking_start=now - timedelta(days=6),
            booking_end=now + timedelta(days=14),
            cancellation_deadline=now + timedelta(days=13),
            slot_creation_open=True,
            booking_open=True,
            status="booking_open",
        )
        db.session.add(exam_viva)
        db.session.flush()
    else:
        exam_viva.status = "booking_open"
        exam_viva.booking_open = True
        exam_viva.slot_creation_open = True

    # Assign examiner to exam_viva
    if not ExaminationExaminer.query.filter_by(
        examination_id=exam_viva.id, examiner_id=examiner.id
    ).first():
        db.session.add(
            ExaminationExaminer(
                examination_id=exam_viva.id,
                examiner_id=examiner.id,
                assigned_by=admin.id,
            )
        )

    # Rubrics for exam_viva
    rubrics_viva_data = [
        (
            "Algorithmic Complexity & Analysis",
            30.0,
            30.0,
            1,
            "Evaluation of Big-O notations, asymptotic bounds, and recurrence relations.",
        ),
        (
            "Data Structures Implementation",
            40.0,
            40.0,
            2,
            "Proficiency in balanced trees, heaps, hash collision resolution, and graph representations.",
        ),
        (
            "Problem Solving & Optimization",
            30.0,
            30.0,
            3,
            "Formulation of optimal subproblems, greedy choices, and memory constraints.",
        ),
    ]
    rubrics_viva = {}
    for crit_name, weight, max_s, pos, desc in rubrics_viva_data:
        r = ExaminationRubric.query.filter_by(
            examination_id=exam_viva.id, criterion_name=crit_name
        ).first()
        if not r:
            r = ExaminationRubric(
                examination_id=exam_viva.id,
                criterion_name=crit_name,
                weightage=weight,
                max_score=max_s,
                position=pos,
                description=desc,
            )
            db.session.add(r)
            db.session.flush()
        rubrics_viva[crit_name] = r

    # Slots for exam_viva
    # Slot 1A: Past/Completed slot
    slot_viva_completed = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_viva.id,
        ExaminationSlot.status == "completed",
    ).first()
    if not slot_viva_completed:
        slot_viva_completed = ExaminationSlot(
            examination_id=exam_viva.id,
            examiner_id=examiner.id,
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(days=2) + timedelta(minutes=45),
            max_capacity=5,
            booked_count=1,
            status="completed",
        )
        db.session.add(slot_viva_completed)
        db.session.flush()

    # Slot 1B: Upcoming bookable slot
    slot_viva_open = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_viva.id,
        ExaminationSlot.status == "available",
    ).first()
    if not slot_viva_open:
        slot_viva_open = ExaminationSlot(
            examination_id=exam_viva.id,
            examiner_id=examiner.id,
            start_at=now + timedelta(days=2, hours=10),
            end_at=now + timedelta(days=2, hours=12),
            max_capacity=5,
            booked_count=0,
            status="available",
        )
        db.session.add(slot_viva_open)
        db.session.flush()

    # Booking & Evaluation for student in slot_viva_completed
    booking_viva = Booking.query.filter_by(
        student_id=student.id, examination_id=exam_viva.id
    ).first()
    if not booking_viva:
        booking_viva = Booking(
            student_id=student.id,
            slot_id=slot_viva_completed.id,
            examination_id=exam_viva.id,
            status="completed",
            booked_at=now - timedelta(days=3),
        )
        db.session.add(booking_viva)
        db.session.flush()
    else:
        booking_viva.status = "completed"
        booking_viva.slot_id = slot_viva_completed.id

    eval_viva = Evaluation.query.filter_by(booking_id=booking_viva.id).first()
    if not eval_viva:
        eval_viva = Evaluation(
            booking_id=booking_viva.id,
            examiner_id=examiner.id,
            total_marks=Decimal("88.50"),
            remarks="Outstanding grasp of balanced search trees and shortest-path graph algorithms. Well-structured proof derivations.",
            status="published",
            submitted_at=now - timedelta(days=2),
            published_at=now - timedelta(days=2),
        )
        db.session.add(eval_viva)
        db.session.flush()

        scores_viva = [
            (
                rubrics_viva["Algorithmic Complexity & Analysis"].id,
                Decimal("27.00"),
                "Clear asymptotic bound derivation for amortized analysis.",
            ),
            (
                rubrics_viva["Data Structures Implementation"].id,
                Decimal("36.00"),
                "Excellent AVL rotation walkthrough with balance factors.",
            ),
            (
                rubrics_viva["Problem Solving & Optimization"].id,
                Decimal("25.50"),
                "Correct recursive relation with memoization cache.",
            ),
        ]
        for r_id, sc, comm in scores_viva:
            db.session.add(
                EvaluationScore(
                    evaluation_id=eval_viva.id,
                    rubric_id=r_id,
                    score=sc,
                    comment=comm,
                )
            )

    # -------------------------------------------------------------------------
    # 6. Examination 2: Database Systems Practical Assessment (Session 2)
    # -------------------------------------------------------------------------
    exam_db = Examination.query.filter_by(name="Database Systems Practical Assessment").first()
    if not exam_db:
        exam_db = Examination(
            course_id=course_db.id,
            name="Database Systems Practical Assessment",
            description="Hands-on evaluation covering SQL schema design, normal forms, and transaction isolation.",
            exam_type="practical",
            duration_minutes=25,
            max_marks=100,
            slot_creation_start=now - timedelta(days=7),
            slot_creation_end=now - timedelta(days=3),
            booking_start=now - timedelta(days=3),
            booking_end=now + timedelta(days=20),
            cancellation_deadline=now + timedelta(days=19),
            slot_creation_open=True,
            booking_open=True,
            status="booking_open",
        )
        db.session.add(exam_db)
        db.session.flush()
    else:
        exam_db.status = "booking_open"
        exam_db.booking_open = True
        exam_db.slot_creation_open = True

    if not ExaminationExaminer.query.filter_by(
        examination_id=exam_db.id, examiner_id=examiner.id
    ).first():
        db.session.add(
            ExaminationExaminer(
                examination_id=exam_db.id,
                examiner_id=examiner.id,
                assigned_by=admin.id,
            )
        )

    rubrics_db_data = [
        (
            "Schema Normalization (3NF/BCNF)",
            35.0,
            35.0,
            1,
            "Decomposition of functional dependencies and multi-valued dependencies.",
        ),
        (
            "Query Execution & Index Tuning",
            35.0,
            35.0,
            2,
            "B+ Tree index selectivity, EXPLAIN query plan analysis, and cost optimization.",
        ),
        (
            "Transaction Isolation & Locking",
            30.0,
            30.0,
            3,
            "Serializability, two-phase locking protocols, and deadlock avoidance.",
        ),
    ]
    for crit_name, weight, max_s, pos, desc in rubrics_db_data:
        if not ExaminationRubric.query.filter_by(
            examination_id=exam_db.id, criterion_name=crit_name
        ).first():
            db.session.add(
                ExaminationRubric(
                    examination_id=exam_db.id,
                    criterion_name=crit_name,
                    weightage=weight,
                    max_score=max_s,
                    position=pos,
                    description=desc,
                )
            )

    # Slots for exam_db
    slot_db_active = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_db.id,
        ExaminationSlot.booked_count > 0,
    ).first()
    if not slot_db_active:
        slot_db_active = ExaminationSlot(
            examination_id=exam_db.id,
            examiner_id=examiner.id,
            start_at=now + timedelta(days=3, hours=14),
            end_at=now + timedelta(days=3, hours=16),
            max_capacity=4,
            booked_count=1,
            status="available",
        )
        db.session.add(slot_db_active)
        db.session.flush()

    slot_db_open = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_db.id,
        ExaminationSlot.booked_count == 0,
    ).first()
    if not slot_db_open:
        slot_db_open = ExaminationSlot(
            examination_id=exam_db.id,
            examiner_id=examiner.id,
            start_at=now + timedelta(days=5, hours=9),
            end_at=now + timedelta(days=5, hours=11),
            max_capacity=6,
            booked_count=0,
            status="available",
        )
        db.session.add(slot_db_open)
        db.session.flush()

    # Active upcoming booking for student in exam_db
    booking_db = Booking.query.filter_by(student_id=student.id, examination_id=exam_db.id).first()
    if not booking_db:
        booking_db = Booking(
            student_id=student.id,
            slot_id=slot_db_active.id,
            examination_id=exam_db.id,
            status="booked",
            booked_at=now - timedelta(days=1),
        )
        db.session.add(booking_db)
        db.session.flush()

    # -------------------------------------------------------------------------
    # 7. Examination 3: Online Proctored MCQ Assessment (Quiz Engine Demo)
    # -------------------------------------------------------------------------
    exam_mcq = Examination.query.filter_by(
        name="Online Proctored MCQ Assessment: Systems & Architecture"
    ).first()
    if not exam_mcq:
        exam_mcq = Examination(
            course_id=course_dsa.id,
            name="Online Proctored MCQ Assessment: Systems & Architecture",
            description="Automated proctored quiz engine evaluating computer systems, memory hierarchies, and concurrency.",
            exam_type="assessment",
            duration_minutes=30,
            max_marks=100,
            slot_creation_start=now - timedelta(days=8),
            slot_creation_end=now - timedelta(days=4),
            booking_start=now - timedelta(days=4),
            booking_end=now + timedelta(days=25),
            cancellation_deadline=now + timedelta(days=24),
            slot_creation_open=True,
            booking_open=True,
            status="booking_open",
        )
        db.session.add(exam_mcq)
        db.session.flush()
    else:
        exam_mcq.status = "booking_open"
        exam_mcq.booking_open = True
        exam_mcq.slot_creation_open = True

    if not ExaminationExaminer.query.filter_by(
        examination_id=exam_mcq.id, examiner_id=examiner.id
    ).first():
        db.session.add(
            ExaminationExaminer(
                examination_id=exam_mcq.id,
                examiner_id=examiner.id,
                assigned_by=admin.id,
            )
        )

    rubrics_mcq_data = [
        (
            "Part A: Data Structures MCQ Questions",
            40.0,
            40.0,
            1,
            "Multiple-choice questions testing binary trees, hash map complexity, and graph traversals.",
        ),
        (
            "Part B: SQL & Database Transactions MCQ",
            30.0,
            30.0,
            2,
            "Objective questions covering write-ahead logging, two-phase commits, and isolation levels.",
        ),
        (
            "Part C: System Architecture & Concurrency",
            30.0,
            30.0,
            3,
            "Proctored quiz items evaluating race condition detection, mutex locks, and pipelining.",
        ),
    ]
    rubrics_mcq = {}
    for crit_name, weight, max_s, pos, desc in rubrics_mcq_data:
        r = ExaminationRubric.query.filter_by(
            examination_id=exam_mcq.id, criterion_name=crit_name
        ).first()
        if not r:
            r = ExaminationRubric(
                examination_id=exam_mcq.id,
                criterion_name=crit_name,
                weightage=weight,
                max_score=max_s,
                position=pos,
                description=desc,
            )
            db.session.add(r)
            db.session.flush()
        rubrics_mcq[crit_name] = r

    # Slots for exam_mcq
    slot_mcq_completed = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_mcq.id,
        ExaminationSlot.status == "completed",
    ).first()
    if not slot_mcq_completed:
        slot_mcq_completed = ExaminationSlot(
            examination_id=exam_mcq.id,
            examiner_id=examiner.id,
            start_at=now - timedelta(days=1),
            end_at=now - timedelta(days=1) + timedelta(minutes=60),
            max_capacity=10,
            booked_count=1,
            status="completed",
        )
        db.session.add(slot_mcq_completed)
        db.session.flush()

    slot_mcq_open = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == exam_mcq.id,
        ExaminationSlot.status == "available",
    ).first()
    if not slot_mcq_open:
        slot_mcq_open = ExaminationSlot(
            examination_id=exam_mcq.id,
            examiner_id=examiner.id,
            start_at=now + timedelta(days=4, hours=11),
            end_at=now + timedelta(days=4, hours=13),
            max_capacity=15,
            booked_count=0,
            status="available",
        )
        db.session.add(slot_mcq_open)
        db.session.flush()

    # Completed booking & score for exam_mcq
    booking_mcq = Booking.query.filter_by(student_id=student.id, examination_id=exam_mcq.id).first()
    if not booking_mcq:
        booking_mcq = Booking(
            student_id=student.id,
            slot_id=slot_mcq_completed.id,
            examination_id=exam_mcq.id,
            status="completed",
            booked_at=now - timedelta(days=2),
        )
        db.session.add(booking_mcq)
        db.session.flush()

    eval_mcq = Evaluation.query.filter_by(booking_id=booking_mcq.id).first()
    if not eval_mcq:
        eval_mcq = Evaluation(
            booking_id=booking_mcq.id,
            examiner_id=examiner.id,
            total_marks=Decimal("92.00"),
            remarks="Completed all proctored quiz sections in 24 minutes. Top 5% performance with zero proctoring warnings.",
            status="published",
            submitted_at=now - timedelta(days=1),
            published_at=now - timedelta(days=1),
        )
        db.session.add(eval_mcq)
        db.session.flush()

        scores_mcq = [
            (
                rubrics_mcq["Part A: Data Structures MCQ Questions"].id,
                Decimal("38.00"),
                "19 of 20 questions answered correctly.",
            ),
            (
                rubrics_mcq["Part B: SQL & Database Transactions MCQ"].id,
                Decimal("28.00"),
                "14 of 15 questions answered correctly.",
            ),
            (
                rubrics_mcq["Part C: System Architecture & Concurrency"].id,
                Decimal("26.00"),
                "13 of 15 questions answered correctly.",
            ),
        ]
        for r_id, sc, comm in scores_mcq:
            db.session.add(
                EvaluationScore(
                    evaluation_id=eval_mcq.id,
                    rubric_id=r_id,
                    score=sc,
                    comment=comm,
                )
            )

    # Re-synchronize slot capacity counts
    for s in ExaminationSlot.query.all():
        active_count = Booking.query.filter(
            Booking.slot_id == s.id,
            Booking.status.in_(["booked", "completed"]),
        ).count()
        s.booked_count = min(active_count, s.max_capacity)

    db.session.commit()

    return {
        "admin_email": admin.email,
        "examiner_email": examiner.email,
        "student_email": student.email,
        "courses_count": Course.query.count(),
        "examinations_count": Examination.query.count(),
        "slots_count": ExaminationSlot.query.count(),
        "evaluations_count": Evaluation.query.count(),
    }
