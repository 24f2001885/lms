<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P8 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file.

SECTION 1: app/blueprints/api_v1/__init__.py
1. Add the import of the new route module charts next to the existing imports (with "# noqa: E402,F401").

SECTION 2: app/blueprints/api_v1/docs.py
1. Append six rows to API_REFERENCE for the chart endpoints (GET /api/v1/charts/bookings-by-day, /booking-status, /participants-by-slot, /examiner-workload, /examination-completion, /results) with roles, the days query parameter where it applies, the success shape {"labels": [...], "series": [{"name", "data"}]} and the possible errors (401, 403, 422). The drift-guard test must stay green.

SECTION 3: app/blueprints/admin/__init__.py, app/blueprints/examiner/__init__.py, app/blueprints/student/__init__.py
1. Add one import line each for the new route module charts (with "# noqa: E402,F401"). Nothing else changes.

SECTION 4: app/templates/admin/base_admin.html and the sidebar tests
1. Add the sidebar link "Charts" (endpoint admin.charts) directly under "Dashboard" in the Overview group. The sidebar now has 11 links.
2. Update every test that counts sidebar links (P3 sidebar test, P6 test_sidebar_has_ten_links) from 10 to 11 and rename the P6 test to test_sidebar_has_eleven_links.

SECTION 5: app/templates/admin/dashboard.html, app/templates/examiner/dashboard.html, app/templates/student/dashboard.html
1. Replace the empty div id="charts-widget" reserved in Tier 1 by the widgets below, using the macro file templates/charts/_macros.html and including templates/charts/_scripts.html in block scripts:
   - Admin: bookings-by-day (line, last 30 days) and examination-completion (grouped bar), plus a link "All charts" to /admin/charts.
   - Examiner: examination-completion (students evaluated) and participants-by-slot (stacked bar), plus a link to /examiner/charts.
   - Student: booking-status (doughnut) and results (bar), plus a link to /student/charts.
2. The widgets sit below the existing cards, two per row from md upward and one per row below md.

SECTION 6: app/static/css/app.css
1. Add chart styles: .chart-card (card with padding), .chart-box (position relative, height 280px, 220px below 576px, width 100%), .chart-state (centered muted text for loading, empty and error), .chart-card details summary (focus ring, cursor), .chart-data-table (small table, max-height 240px with overflow auto). No colour except the existing palette variables.

SECTION 7: app/static/vendor/README.md
1. Add the Chart.js entry: file app/static/vendor/chartjs/chart.umd.min.js (Chart.js 4.x UMD build, MIT licence), to be downloaded once from the official release while online; record the exact version in the file and add the file to the verification command.

SECTION 8: tests/conftest.py
1. Add factory make_chart_dataset(): two examiners, three students, two examinations with rubric, five slots (two past, three future), a mix of booked, cancelled and completed bookings spread over the last 10 days and evaluations in draft, submitted and published states, using the frozen clock. Return a simple namespace with the created objects and the expected counts used by the chart tests.

SECTION 9: pyproject.toml, Makefile, README.md
1. pyproject.toml: register the pytest marker "charts". Makefile: add target test-charts (pytest -m charts) and make sure test-e2e includes tests/e2e/test_charts_render.py.
2. README.md: add a "Charts" section (where they appear per role, Chart.js is vendored, how to add a chart: endpoint, chart_data function, card macro).
DEBUGGING:
# print("[DEBUG] applied P8 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the whole suite passes (P0-P7 unchanged except the two sidebar tests).
- /admin/dashboard shows two chart cards and the sidebar has 11 links; /student/dashboard shows two cards for a student with data.
-->
