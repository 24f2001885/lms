

from app.models.audit_log import AuditLog
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

# Tuple of all 12 Tier 1 table names for integrity checks and tests
ALL_TABLE_NAMES = (
    "audit_logs",
    "bookings",
    "courses",
    "evaluation_scores",
    "evaluations",
    "examination_examiners",
    "examination_rubrics",
    "examination_slots",
    "examinations",
    "examiner_profiles",
    "student_profiles",
    "users",
)

__all__ = [
    "User",
    "ExaminerProfile",
    "StudentProfile",
    "Course",
    "Examination",
    "ExaminationRubric",
    "ExaminationExaminer",
    "ExaminationSlot",
    "Booking",
    "Evaluation",
    "EvaluationScore",
    "AuditLog",
    "ALL_TABLE_NAMES",
]