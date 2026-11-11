<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P4 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file.

SECTION 1: app/blueprints/examiner/__init__.py (stub from P2)
1. Keep examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner").
2. DELETE the stub dashboard route and its use of auth/role_landing_stub.html.
3. At the bottom import the route modules so they register on examiner_bp: dashboard, examinations, slots, evaluations (each with "# noqa: E402,F401"). No logic besides the blueprint and the imports.

SECTION 2: app/services/audit_service.py
1. Add action-name constants: SLOT_CREATE = "slot.create", SLOT_UPDATE = "slot.update", SLOT_DELETE = "slot.delete", EVALUATION_SAVE = "evaluation.save", EVALUATION_SUBMIT = "evaluation.submit", EVALUATION_PUBLISH = "evaluation.publish". Nothing else changes.

SECTION 3: tests/conftest.py
1. Add factory make_ready_examination(examiner=None, now=None): creates an admin, a course, an examination whose slot-creation window contains now (default the frozen clock) with slot_creation_open True and booking window afterwards, rubric criteria weighted 60 and 40 (max scores 60 and 40, max_marks 100), and an approved assignment of the examiner (created if None). Returns (examination, examiner).
2. Add fixture examiner_client: creates an approved active examiner (must_change_password False), logs in via POST /login and returns (client, examiner).
3. Add helper make_booking_with_slot(examination, examiner, student=None, status="booked") returning (booking, slot) with slot.booked_count incremented to match.

SECTION 4: app/static/css/app.css
1. Add .slot-meter (thin progress bar for seats used) and .score-input (narrow numeric input, right aligned). No other changes.
DEBUGGING:
# print("[DEBUG] applied P4 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P3 suite still passes.
- GET /examiner/dashboard as an approved examiner returns 200 with the real dashboard; pending examiners are still redirected to /pending-approval.
-->
<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P4 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file.

SECTION 1: app/blueprints/examiner/__init__.py (stub from P2)
1. Keep examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner").
2. DELETE the stub dashboard route and its use of auth/role_landing_stub.html.
3. At the bottom import the route modules so they register on examiner_bp: dashboard, examinations, slots, evaluations (each with "# noqa: E402,F401"). No logic besides the blueprint and the imports.

SECTION 2: app/services/audit_service.py
1. Add action-name constants: SLOT_CREATE = "slot.create", SLOT_UPDATE = "slot.update", SLOT_DELETE = "slot.delete", EVALUATION_SAVE = "evaluation.save", EVALUATION_SUBMIT = "evaluation.submit", EVALUATION_PUBLISH = "evaluation.publish". Nothing else changes.

SECTION 3: tests/conftest.py
1. Add factory make_ready_examination(examiner=None, now=None): creates an admin, a course, an examination whose slot-creation window contains now (default the frozen clock) with slot_creation_open True and booking window afterwards, rubric criteria weighted 60 and 40 (max scores 60 and 40, max_marks 100), and an approved assignment of the examiner (created if None). Returns (examination, examiner).
2. Add fixture examiner_client: creates an approved active examiner (must_change_password False), logs in via POST /login and returns (client, examiner).
3. Add helper make_booking_with_slot(examination, examiner, student=None, status="booked") returning (booking, slot) with slot.booked_count incremented to match.

SECTION 4: app/static/css/app.css
1. Add .slot-meter (thin progress bar for seats used) and .score-input (narrow numeric input, right aligned). No other changes.
DEBUGGING:
# print("[DEBUG] applied P4 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P3 suite still passes.
- GET /examiner/dashboard as an approved examiner returns 200 with the real dashboard; pending examiners are still redirected to /pending-approval.
-->