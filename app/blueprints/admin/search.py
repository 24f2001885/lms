"""
FILE PURPOSE: ADM-17 search across students, examiners, examinations and bookings.
DEPENDS ON: admin_bp, admin_required, app/forms/admin_actions.py (AdminSearchForm), app/services/search_service.py.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/search with query parameters q, kind, page. Validate with AdminSearchForm (GET). Invalid kind -> 400-style message on the page, never a 500.
2. Render admin/search_results.html with the result page, grouped display per kind (table columns differ), and links to the matching detail pages (student, examiner, examination, booking).
3. Empty q shows the instruction "Enter a name or ID to search."; no-result shows "No results for <q>" with q escaped by Jinja autoescape.
DEBUGGING:
# print(f"[DEBUG] search kind={kind} q={q!r}")
OFFLINE DOCKER TEST CASES:
- /admin/search?kind=student&q=ana lists matching students with links.
- kind=booking&q=<booking id> finds that booking first.
- q containing <script> is displayed escaped (the raw tag never appears in the HTML).
- Non-admin gets 403.

app/blueprints/admin/search.py - ADM-17 search across students, examiners, exams, bookings.
"""

from flask import render_template, request

from app.blueprints.admin import admin_bp
from app.forms.admin_actions import AdminSearchForm
from app.forms.common import parse_page
from app.security.decorators import admin_required
from app.services import search_service


@admin_bp.route("/search", methods=["GET"])
@admin_required
def search():
    """Multi-entity administrative search."""
    form = AdminSearchForm(request.args)
    kind = request.args.get("kind", "student").strip().lower()
    q = request.args.get("q", "").strip()
    page, per_page = parse_page(request.args)

    page_results = None
    if q and kind in ("student", "examiner", "examination", "booking"):
        page_results = search_service.search(kind=kind, q=q, page=page, per_page=per_page)

    return render_template(
        "admin/search_results.html",
        form=form,
        kind=kind,
        q=q,
        page=page_results,
    )