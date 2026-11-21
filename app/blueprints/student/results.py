"""
FILE PURPOSE: STU-09 results list and STU-10 result detail with feedback (scorecard download arrives in P12).
DEPENDS ON: student_bp, student_required, app/services/student_queries.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/results (paginated published results only) and GET /student/results/<booking_id> (404 unless the booking belongs to the student AND its evaluation is published).
2. Detail data comes from student_queries.result_detail: examination, slot date, examiner name, total and maximum, per-criterion table (criterion, score, maximum, comment) and the remarks text under "Feedback".
3. Nothing about draft or submitted evaluations is ever shown, not even their existence.
DEBUGGING:
# print(f"[DEBUG] student result booking={booking_id} found={detail is not None}")
OFFLINE DOCKER TEST CASES:
- A submitted but unpublished evaluation returns 404 for the student and does not appear in the list.
- After the examiner publishes, the result appears with the correct total and feedback.
- Another student's booking id returns 404.

FILE PURPOSE: STU-09 results list and STU-10 result detail with feedback.
"""

from flask import abort, g, render_template, request

from app.blueprints.student import student_bp
from app.security.decorators import student_required
from app.services import student_queries


@student_bp.route("/results")
@student_required
def results_list():
    page = request.args.get("page", 1, type=int)
    pagination = student_queries.results(g.user.id, page=page)
    return render_template("student/results.html", pagination=pagination, page=pagination)


@student_bp.route("/results/<int:booking_id>")
@student_required
def result_detail(booking_id):
    detail = student_queries.result_detail(g.user.id, booking_id)
    if not detail:
        abort(404)
    return render_template("student/result_detail.html", detail=detail)
