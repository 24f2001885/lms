"""
The scorecard download route for students (T2 extra).
"""

from flask import abort, g, make_response

from app.blueprints.student import student_bp
from app.extensions import db
from app.security.decorators import student_required
from app.services import scorecard
from app.services.audit_service import SCORECARD_DOWNLOAD, log_action


@student_bp.route("/bookings/<int:id>/scorecard.pdf")
@student_required
def download_scorecard(id: int):
    result = scorecard.build_scorecard(g.user.id, id)
    if not result:
        abort(404)

    pdf_bytes, filename = result

    try:
        log_action(g.user.id, SCORECARD_DOWNLOAD, "booking", id)
        db.session.commit()
    except Exception:
        db.session.rollback()

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=\"{filename}\"; filename*=UTF-8''{filename}"
    )
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["Content-Length"] = str(len(pdf_bytes))
    return resp
