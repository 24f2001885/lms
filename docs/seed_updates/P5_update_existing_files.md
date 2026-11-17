<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P5 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file.

SECTION 1: app/blueprints/student/__init__.py (stub from P2)
1. Keep student_bp = Blueprint("student", __name__, url_prefix="/student").
2. DELETE the stub dashboard route and its use of auth/role_landing_stub.html.
3. At the bottom import the route modules so they register on student_bp: dashboard, examinations, bookings, results (each with "# noqa: E402,F401"). No logic besides the blueprint and the imports.

SECTION 2: app/services/audit_service.py
1. Add action-name constants: BOOKING_CREATE = "booking.create", BOOKING_CANCEL = "booking.cancel". (P6 adds BOOKING_RESCHEDULE, BOOKING_ADMIN_CANCEL, SLOT_CANCEL, SYSTEM_* constants.)

SECTION 3: app/templates/auth/role_landing_stub.html
1. DELETE this file: all three stub dashboards are now replaced (admin P3, examiner P4, student P5). Also delete any test that still references it.

SECTION 4: tests/conftest.py
1. Add fixture student_client: creates an active student (must_change_password False), logs in via POST /login and returns (client, student).
2. Add factory make_open_booking_setup(student_count=1, capacity=5): builds a ready examination whose BOOKING window contains the frozen now (booking_open True, rubric total 100, approved assigned examiner) with one future available slot, returns (examination, slot, examiner, students).
3. Add factory make_published_evaluation(booking, examiner, total): creates an evaluation with status published and per-criterion scores summing to total.

SECTION 5: app/static/css/app.css
1. Add .slot-row-full (muted text colour), .deadline-note (small muted text), .exam-card (card with hover shadow and a status badge slot in the corner). No other changes.
DEBUGGING:
# print("[DEBUG] applied P5 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P4 suite still passes and GET /student/dashboard returns the real dashboard for a student.
- grep finds no reference to role_landing_stub anywhere in app/ or tests/.
-->
