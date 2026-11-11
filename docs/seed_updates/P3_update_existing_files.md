<!--
FILE PURPOSE: One update prompt per file that earlier phases already implemented and P3 must change. Do NOT regenerate these files from scratch. For each section give the LLM the section text plus the CURRENT file.
HOW TO USE: process the sections one at a time; after all are applied run the whole test suite.

SECTION 1: app/__init__.py
1. Register two Jinja filters: localdt (format a naive-UTC datetime with app.services.windows.format_local, empty string for None) and money_marks (strip trailing zeros from Decimal/float marks).
2. Do not register new blueprints (the admin blueprint already exists) and do not add other globals: badges are rendered by the macro in templates/macros/status_badge.html. Keep all P1/P2 behaviour.

SECTION 2: app/blueprints/admin/__init__.py (stub from P2)
1. Keep admin_bp = Blueprint("admin", __name__, url_prefix="/admin").
2. DELETE the stub dashboard route and the auth/role_landing_stub.html rendering for admin.
3. At the bottom import the route modules so they register on admin_bp: dashboard, courses, examinations, rubrics, examiners, students, slots, bookings, search, history (each with "# noqa: E402,F401").
4. No logic in this file besides the blueprint object and the imports.

SECTION 3: app/templates/base.html
1. Wrap the default top navbar in {% block site_nav %}...{% endblock %} and wrap the main element in {% block layout %}...{% endblock %} so role bases can replace them (admin sidebar, examiner/student top navs later).
2. Move the flash-message loop into a new partial templates/_flash.html (same markup: aria-live polite region, alert role) and include it from base.html inside the default layout block. Role bases that override layout must include _flash.html themselves.
3. Keep the skip-link target id main-content on whatever element holds the page content. Keep the csrf meta tag and all existing behaviour.

SECTION 4: app/static/css/app.css
1. Add styles for the admin shell: .admin-shell (flex layout), .admin-sidebar (width 240px, background #14283B, light text with 4.5:1 contrast, sticky), .admin-sidebar a.active (left border 4px primary), .admin-content (padding, min-width 0).
2. Add .stat-card (white card, large number, muted label), .timeline-switch (inline status + button row), .table-filter-bar (flex wrap, gap), .badge-outline-warning for the "Closed" examination badge (amber outline).
3. Below 992px the sidebar becomes a collapsed block above the content (full off-canvas drawer is P10).

SECTION 5: tests/conftest.py
1. Add factories make_assignment(examination, examiner, assigned_by=None) and make_evaluation(booking, examiner, status="draft", total=0, scores=None).
2. Add fixture freeze_now(dt): monkeypatches app.services.windows.now_utc to return dt and returns a helper to move the clock. This works ONLY because services call windows.now_utc() through the module (never "from ... import now_utc").
3. Add fixture admin_client: creates a seeded-like admin (must_change_password False), logs in via POST /login and returns the logged-in test client.

SECTION 6: tests/integration/test_rbac_access.py
1. The admin row of the matrix now expects 200 from /admin/dashboard with the real dashboard (content contains "Dashboard"); other roles' expectations are unchanged.
DEBUGGING:
# print("[DEBUG] applied P3 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections: the whole P0-P2 suite still passes (make test-core).
- GET /admin/dashboard as admin returns 200 and renders the sidebar; anonymous still 302 to /login; student 403.
-->
