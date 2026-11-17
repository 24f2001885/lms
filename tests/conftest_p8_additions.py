"""
tests/conftest_p8_additions.py - Phase 8 test fixtures and helpers.
"""

import types
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models.booking import Booking
from app.models.evaluation import Evaluation, EvaluationScore
from app.models.slot import ExaminationSlot


@pytest.fixture
def make_chart_dataset(
    db_session,
    make_admin,
    make_examiner,
    make_student,
    make_course,
    make_examination,
    make_rubric,
    make_assignment,
):
    """
    Creates a standard dataset for chart tests:
    - 2 examiners, 3 students, 2 examinations with rubrics
    - 5 slots (2 past, 3 future)
    - 5 bookings (active, completed, cancelled) spread over last 10 days
    - Evaluations in draft, submitted, published states
    """

    def _factory(base_dt: datetime | None = None):
        if base_dt is None:
            base_dt = datetime(2030, 6, 15, 12, 0, 0)

        admin = make_admin()
        course = make_course(created_by=admin.id)

        examiner1 = make_examiner(approved=True, full_name="Dr. First Examiner")
        examiner2 = make_examiner(approved=True, full_name="Dr. Second Examiner")

        student1 = make_student(full_name="Alice Student")
        student2 = make_student(full_name="Bob Student")
        student3 = make_student(full_name="Charlie Student")

        # 2 Examinations
        exam1 = make_examination(
            course=course,
            name="Data Structures Viva",
            max_marks=100,
            booking_start=base_dt - timedelta(days=12),
            booking_end=base_dt + timedelta(days=2),
            cancellation_deadline=base_dt + timedelta(days=1),
            status="booking_open",
            slot_creation_open=True,
            booking_open=True,
        )
        r1_1 = make_rubric(exam1, name="Concept", weightage=50, max_score=50.0, position=1)
        r1_2 = make_rubric(exam1, name="Implementation", weightage=50, max_score=50.0, position=2)
        make_assignment(exam1, examiner1, assigned_by=admin)

        exam2 = make_examination(
            course=course,
            name="Algorithms Practical",
            max_marks=100,
            booking_start=base_dt - timedelta(days=10),
            booking_end=base_dt + timedelta(days=5),
            cancellation_deadline=base_dt + timedelta(days=4),
            status="booking_open",
            slot_creation_open=True,
            booking_open=True,
        )
        r2_1 = make_rubric(exam2, name="Complexity", weightage=40, max_score=40.0, position=1)
        r2_2 = make_rubric(exam2, name="Correctness", weightage=60, max_score=60.0, position=2)
        make_assignment(exam2, examiner2, assigned_by=admin)
        make_assignment(exam2, examiner1, assigned_by=admin)

        # 5 slots: 2 past, 3 future
        # Slot 1: past, examiner1, exam1
        s1 = ExaminationSlot(
            examination_id=exam1.id,
            examiner_id=examiner1.id,
            start_at=base_dt - timedelta(days=5),
            end_at=base_dt - timedelta(days=5) + timedelta(hours=2),
            max_capacity=5,
            booked_count=2,
            status="completed",
        )
        # Slot 2: past, examiner2, exam2
        s2 = ExaminationSlot(
            examination_id=exam2.id,
            examiner_id=examiner2.id,
            start_at=base_dt - timedelta(days=3),
            end_at=base_dt - timedelta(days=3) + timedelta(hours=2),
            max_capacity=4,
            booked_count=1,
            status="completed",
        )
        # Slot 3: future, examiner1, exam1
        s3 = ExaminationSlot(
            examination_id=exam1.id,
            examiner_id=examiner1.id,
            start_at=base_dt + timedelta(days=2),
            end_at=base_dt + timedelta(days=2) + timedelta(hours=1),
            max_capacity=3,
            booked_count=1,
            status="available",
        )
        # Slot 4: future, examiner2, exam2
        s4 = ExaminationSlot(
            examination_id=exam2.id,
            examiner_id=examiner2.id,
            start_at=base_dt + timedelta(days=4),
            end_at=base_dt + timedelta(days=4) + timedelta(hours=1),
            max_capacity=5,
            booked_count=0,
            status="available",
        )
        # Slot 5: future, examiner1, exam2
        s5 = ExaminationSlot(
            examination_id=exam2.id,
            examiner_id=examiner1.id,
            start_at=base_dt + timedelta(days=6),
            end_at=base_dt + timedelta(days=6) + timedelta(hours=1),
            max_capacity=2,
            booked_count=0,
            status="available",
        )
        db_session.add_all([s1, s2, s3, s4, s5])
        db_session.commit()

        # 5 Bookings
        b1 = Booking(
            examination_id=exam1.id,
            slot_id=s1.id,
            student_id=student1.id,
            status="completed",
            booked_at=base_dt - timedelta(days=8),
        )
        b2 = Booking(
            examination_id=exam1.id,
            slot_id=s1.id,
            student_id=student2.id,
            status="completed",
            booked_at=base_dt - timedelta(days=7),
        )
        b3 = Booking(
            examination_id=exam1.id,
            slot_id=s1.id,
            student_id=student3.id,
            status="cancelled",
            booked_at=base_dt - timedelta(days=6),
            cancelled_at=base_dt - timedelta(days=5),
        )
        b4 = Booking(
            examination_id=exam2.id,
            slot_id=s2.id,
            student_id=student1.id,
            status="completed",
            booked_at=base_dt - timedelta(days=4),
        )
        b5 = Booking(
            examination_id=exam1.id,
            slot_id=s3.id,
            student_id=student3.id,
            status="booked",
            booked_at=base_dt - timedelta(days=1),
        )
        db_session.add_all([b1, b2, b3, b4, b5])
        db_session.commit()

        # 3 Evaluations
        # ev1: for b1 (student1, examiner1, exam1) - published, total 85
        ev1 = Evaluation(
            booking_id=b1.id,
            examiner_id=examiner1.id,
            total_marks=Decimal("85.0"),
            status="published",
            submitted_at=base_dt - timedelta(days=4),
            published_at=base_dt - timedelta(days=3),
        )
        # ev2: for b2 (student2, examiner1, exam1) - submitted, total 70
        ev2 = Evaluation(
            booking_id=b2.id,
            examiner_id=examiner1.id,
            total_marks=Decimal("70.0"),
            status="submitted",
            submitted_at=base_dt - timedelta(days=3),
        )
        # ev3: for b4 (student1, examiner2, exam2) - draft, total 60
        ev3 = Evaluation(
            booking_id=b4.id,
            examiner_id=examiner2.id,
            total_marks=Decimal("60.0"),
            status="draft",
        )
        db_session.add_all([ev1, ev2, ev3])
        db_session.flush()

        sc1_1 = EvaluationScore(evaluation_id=ev1.id, rubric_id=r1_1.id, score=Decimal("45.0"))
        sc1_2 = EvaluationScore(evaluation_id=ev1.id, rubric_id=r1_2.id, score=Decimal("40.0"))
        sc2_1 = EvaluationScore(evaluation_id=ev2.id, rubric_id=r1_1.id, score=Decimal("35.0"))
        sc2_2 = EvaluationScore(evaluation_id=ev2.id, rubric_id=r1_2.id, score=Decimal("35.0"))
        sc3_1 = EvaluationScore(evaluation_id=ev3.id, rubric_id=r2_1.id, score=Decimal("25.0"))
        sc3_2 = EvaluationScore(evaluation_id=ev3.id, rubric_id=r2_2.id, score=Decimal("35.0"))
        db_session.add_all([sc1_1, sc1_2, sc2_1, sc2_2, sc3_1, sc3_2])
        db_session.commit()

        return types.SimpleNamespace(
            base_dt=base_dt,
            admin=admin,
            examiner1=examiner1,
            examiner2=examiner2,
            student1=student1,
            student2=student2,
            student3=student3,
            exam1=exam1,
            exam2=exam2,
            slots=[s1, s2, s3, s4, s5],
            s1=s1,
            s2=s2,
            s3=s3,
            s4=s4,
            s5=s5,
            bookings=[b1, b2, b3, b4, b5],
            b1=b1,
            b2=b2,
            b3=b3,
            b4=b4,
            b5=b5,
            eval1=ev1,
            eval2=ev2,
            eval3=ev3,
        )

    return _factory
