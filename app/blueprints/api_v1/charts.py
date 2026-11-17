"""
FILE PURPOSE: Chart data endpoints under /api/v1/charts.
TDR 5.2 / PDR 5.7: bookings-by-day, booking-status, participants-by-slot,
examiner-workload, examination-completion, results.
"""

from flask import g, request

from app.blueprints.api_v1 import api_bp
from app.blueprints.api_v1.common import api_login_required, api_roles, ok
from app.blueprints.api_v1.validation import ApiValidationError
from app.services import chart_data


@api_bp.route("/charts/bookings-by-day", methods=["GET"])
@api_login_required
@api_roles("admin", "examiner", "student")
def chart_bookings_by_day():
    raw_days = request.args.get("days", 30)
    try:
        days = chart_data.validate_days(raw_days)
    except (ValueError, TypeError):
        raise ApiValidationError({"days": ["Days must be an integer between 1 and 180."]}) from None

    data = chart_data.bookings_by_day(g.user, days=days)
    return ok(data)


@api_bp.route("/charts/booking-status", methods=["GET"])
@api_login_required
@api_roles("admin", "examiner", "student")
def chart_booking_status():
    data = chart_data.booking_status(g.user)
    return ok(data)


@api_bp.route("/charts/participants-by-slot", methods=["GET"])
@api_login_required
@api_roles("admin", "examiner")
def chart_participants_by_slot():
    data = chart_data.participants_by_slot(g.user)
    return ok(data)


@api_bp.route("/charts/examiner-workload", methods=["GET"])
@api_login_required
@api_roles("admin", "examiner")
def chart_examiner_workload():
    data = chart_data.examiner_workload(g.user)
    return ok(data)


@api_bp.route("/charts/examination-completion", methods=["GET"])
@api_login_required
@api_roles("admin", "examiner")
def chart_examination_completion():
    data = chart_data.examination_completion(g.user)
    return ok(data)


@api_bp.route("/charts/results", methods=["GET"])
@api_login_required
@api_roles("admin", "examiner", "student")
def chart_results():
    data = chart_data.results(g.user)
    return ok(data)
