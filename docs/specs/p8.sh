#!/usr/bin/env bash
# =====================================================================
# P8.sh - Phase P8: Charts & Visualization (Tier 2, Secondary)
# Course commit message : Milestone-8 EMP-Charts-Visualization
# Branch                : phase/p8-charts-visualization
# Depends on            : P7 (tag p7-done) - chart endpoints live in api_v1
# Screens               : ADM-19, EXM-10, STU-11 and the dashboard widgets
# Source of truth       : PDR 5.7, TDR 5.2 (chart endpoints), Design Plan 5.2-5.4,
#                         Master Blueprint 3.2 (P8 row)
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P8_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P8"
BRANCH="phase/p8-charts-visualization"
PREV_TAG="p7-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P7 first."; exit 1; }
git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || { echo "GATE A CLOSED: tag tier1-complete is missing."; exit 1; }
[ -f app/blueprints/api_v1/__init__.py ] || { echo "ERROR: app/blueprints/api_v1/__init__.py missing (P7 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
bash scripts/check_gate.sh "$BRANCH" || { echo "ERROR: gate check refused this branch."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P8 needs)
# ---------------------------------------------------------------------
mkdir -p app/services app/blueprints/api_v1
mkdir -p app/templates/charts app/templates/admin app/templates/examiner app/templates/student
mkdir -p app/static/js app/static/vendor/chartjs
mkdir -p tests/unit tests/integration tests/e2e docs/seed_updates

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P8_update_existing_files.md
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
EOF

# ============================== SERVICES =============================

cat << 'EOF' > app/services/chart_data.py
"""
FILE PURPOSE: Builds the data for every chart, already scoped to the viewer's role. Pure data: no Flask objects, no JSON responses, no HTML. Used by the chart endpoints (and later by the scorecard if needed).
DEPENDS ON: app/models, app/services/windows.py (now_utc, to_local), app/extensions.py, app/errors.py (AppError).
PROMPT FOR LLM IMPLEMENTATION:
1. Common contract: every function takes the acting user first and returns {"labels": [str, ...], "series": [{"name": str, "data": [number, ...]}, ...]} (TDR 5.2 shape); every series has exactly len(labels) numbers; numbers are int, or float rounded to 1 decimal for percentages; no None, no Decimal. A role that may not see a chart raises AppError("forbidden", "...", http_status=403) (the controller also checks first). Use COUNT/GROUP BY queries; never load entity rows only to count them. Clock: windows.now_utc() through the module.
2. SCOPE RULE for every chart: admin sees all non-deleted data; examiner only bookings/slots/evaluations of slots where slot.examiner_id equals the examiner and examinations assigned to them; student only their own bookings and their own PUBLISHED evaluations. No chart label or value may expose another person's name, email or marks (labels are dates, statuses, examination names, slot times or, for the admin workload chart only, examiner names).
3. bookings_by_day(user, days=30): window = the last `days` local days including today (days in 1..180). Select only the booked_at and cancelled_at columns inside the window, convert each to a LOCAL date with windows.to_local (APP_TIMEZONE; bucket in Python so DST or offsets cannot break SQL), zero-fill every day, labels are ISO local dates "YYYY-MM-DD", series "Booked" (by booked_at) and "Cancelled" (by cancelled_at).
4. booking_status(user): labels ["Booked", "Completed", "Cancelled"], one series "Bookings" with the counts for the viewer's scope (student: own bookings; examiner: bookings of own slots; admin: all).
5. participants_by_slot(user, limit=12): admin and examiner only. The next `limit` non-cancelled future slots by start_at (examiner: own), labels like "10 Jan 10:00 Viva" (local date-time plus examination name, truncated to 28 characters), series "Booked" (booked_count) and "Seats free" (max_capacity - booked_count).
6. examiner_workload(user): admin only (labels = examiner names, series "Slots" (non-cancelled), "Booked students" (active bookings in their slots), "Not yet submitted" (bookings without a submitted or published evaluation)); examiner (own view): labels = own examination names, series "Slots", "Booked students", "Evaluated" (submitted or published). Students get 403. Limit to 12 labels ordered by booked students desc.
7. examination_completion(user, limit=12): admin and examiner: the most recent `limit` non-deleted examinations by booking_start (examiner: assigned only); series "Booked" (active bookings), "Evaluation submitted" (submitted or published) and "Published". Students get 403.
8. results(user, limit=12): student: own published evaluations, labels = examination names, one series "Score %" = total_marks / max_marks * 100 (1 decimal); examiner: average percentage per examination over published evaluations in own slots, series "Average %"; admin: the same over all. Examinations without published results are omitted (never a 0 placeholder). An empty result returns labels [] and series with empty data, which the front end renders as "No data yet.".
9. validate_days(value) -> int: accepts only integers 1..180 (the page uses 7, 30, 90, 180), raises ValueError otherwise (controller returns 422).
DEBUGGING:
# print(f"[DEBUG] chart {name} user={user.id}:{user.role} labels={len(labels)} series={[len(s['data']) for s in series]}")
OFFLINE DOCKER TEST CASES:
- bookings_by_day returns exactly `days` labels, zero-filled; a booking at 23:30 UTC on Jan 10 lands on Jan 11 for Asia/Kolkata.
- Student and examiner results exclude draft/submitted evaluations; student values equal total/max*100 rounded to 1 decimal.
- A student calling examiner_workload, participants_by_slot or examination_completion raises AppError forbidden.
- Examiner A never sees Examiner B's slots or examinations in any chart; admin totals equal the sum over examiners.
- Every function returns series whose data length equals len(labels) and contains only int/float values.
- With no data every function returns the empty-but-valid shape.
"""
EOF

# =========================== API + PAGE ROUTES =======================

cat << 'EOF' > app/blueprints/api_v1/charts.py
"""
FILE PURPOSE: The chart data endpoints under /api/v1/charts (TDR 5.2: bookings-by-day, examiner-workload, examination-completion; P8 adds booking-status, participants-by-slot and results so every role in PDR 5.7 has its charts).
DEPENDS ON: api_bp, common.py (ok, translate_app_error, get_int_arg), app/services/chart_data.py, app/blueprints/api_v1/validation.py (ApiValidationError).
PROMPT FOR LLM IMPLEMENTATION:
1. Six GET routes, all session-authenticated (api_login_required) and returning chart_data output unchanged with status 200:
   - /api/v1/charts/bookings-by-day (admin, examiner, student; query days, default 30)
   - /api/v1/charts/booking-status (admin, examiner, student)
   - /api/v1/charts/participants-by-slot (admin, examiner)
   - /api/v1/charts/examiner-workload (admin, examiner)
   - /api/v1/charts/examination-completion (admin, examiner)
   - /api/v1/charts/results (admin, examiner, student)
2. Role guards use api_roles(...) so a disallowed role gets 403 "forbidden" before any query; anonymous gets 401; invalid days (not an integer, below 1, above 180) gets 422 validation_error with fields {"days": [...]}.
3. Add Cache-Control: no-store (already set by the blueprint hook) and never include user ids, emails or other identifying data in the payload.
4. No query logic here; the controller only parses days and calls chart_data.
DEBUGGING:
# print(f"[DEBUG] api chart {request.path} user={g.user.id}:{g.user.role} days={days}")
OFFLINE DOCKER TEST CASES:
- Every endpoint returns the exact shape {"labels": [...], "series": [{"name", "data"}]} with equal lengths.
- Student requests to participants-by-slot, examiner-workload and examination-completion return 403; anonymous returns 401.
- days=0, days=181 and days=abc return 422 with a "days" field message.
- Responses for the same role and data are identical between the endpoint and a direct chart_data call.
"""
EOF

cat << 'EOF' > app/blueprints/admin/charts.py
"""
FILE PURPOSE: ADM-19 Admin chart page.
DEPENDS ON: admin_bp, admin_required, app/templates/admin/charts.html.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /admin/charts (endpoint charts) with admin_required and an optional query parameter days restricted to 7, 30, 90 or 180 (default 30; anything else falls back to 30, never an error page).
2. Render admin/charts.html with days and the list of chart definitions (id, title, API url, chart type, description) so the template stays declarative. The route performs NO data queries; the browser fetches the endpoints.
DEBUGGING:
# print(f"[DEBUG] admin charts page days={days}")
OFFLINE DOCKER TEST CASES:
- Admin gets 200 with five chart cards; examiner and student get 403; anonymous 302 to /login.
- ?days=90 puts days=90 in the bookings-by-day card URL; ?days=5 falls back to 30.
"""
EOF

cat << 'EOF' > app/blueprints/examiner/charts.py
"""
FILE PURPOSE: EXM-10 Examiner chart page.
DEPENDS ON: examiner_bp, approved_examiner_required, app/templates/examiner/charts.html.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /examiner/charts (endpoint charts) with approved_examiner_required and the same days whitelist as the Admin page.
2. Render examiner/charts.html with four chart definitions: students evaluated (examination-completion), participants (participants-by-slot), bookings over time (bookings-by-day), average results (results). No queries in the route.
DEBUGGING:
# print(f"[DEBUG] examiner charts page user={g.user.id} days={days}")
OFFLINE DOCKER TEST CASES:
- Approved examiner gets 200 with four cards; pending examiner is redirected to /pending-approval; student and admin get 403.
"""
EOF

cat << 'EOF' > app/blueprints/student/charts.py
"""
FILE PURPOSE: STU-11 Student chart page.
DEPENDS ON: student_bp, student_required, app/templates/student/charts.html.
PROMPT FOR LLM IMPLEMENTATION:
1. GET /student/charts (endpoint charts) with student_required and the same days whitelist.
2. Render student/charts.html with three chart definitions: booking history (booking-status doughnut), booking trend (bookings-by-day line) and results (results bar). No queries in the route.
DEBUGGING:
# print(f"[DEBUG] student charts page user={g.user.id} days={days}")
OFFLINE DOCKER TEST CASES:
- Student gets 200 with three cards; admin and examiner get 403.
"""
EOF

# ============================= TEMPLATES =============================

cat << 'EOF' > app/templates/charts/_macros.html
<!--
FILE PURPOSE: The single reusable chart card used by every chart page and dashboard widget (Design Plan 5.2-5.4: chart pages and widgets).
PROMPT FOR LLM IMPLEMENTATION:
1. Macro chart_card(id, title, url, kind, description): renders a figure.chart-card containing a figcaption with the title (h2 or h3 passed by the caller via a heading_level argument, default 3), a one-sentence description in muted text, a div.chart-box with a canvas id="chart-<id>" carrying data-chart-url, data-chart-type (one of line, bar, stacked-bar, doughnut), role="img", aria-label="<title>: <description>" and aria-describedby pointing to the table container, a div.chart-state with role="status" for loading, empty and error texts (initially "Loading chart..."), a Retry button hidden until an error, and a details element "View data as table" whose body is an empty div id="chart-<id>-table" that the script fills.
2. A noscript element inside the card with the text "This chart needs JavaScript. The data is available as JSON at <url>." (the url shown as plain text).
3. Macro chart_days_selector(current, endpoint): a small GET form or a pill list for 7, 30, 90, 180 days using links (no JavaScript), the current value marked aria-current="true".
4. No colours in the markup; styling comes from app.css and charts.js.
DEBUGGING:
DEBUG (add as an HTML comment while debugging): chart card id={{ id }} url={{ url }} kind={{ kind }}
OFFLINE DOCKER TEST CASES:
- The rendered card has exactly one canvas with role img, a non-empty aria-label, data-chart-url equal to the given URL and a details element.
- Two cards on one page have different canvas ids.
-->
EOF

cat << 'EOF' > app/templates/charts/_scripts.html
<!--
FILE PURPOSE: Loads the vendored Chart.js and the project's charts.js, only on pages that have charts.
PROMPT FOR LLM IMPLEMENTATION:
1. Two script tags with defer, in this order: url_for static vendor/chartjs/chart.umd.min.js, then url_for static js/charts.js. No CDN, no inline script, no module type.
2. Include this partial from the scripts block of every page that renders chart cards (never from base.html, so other pages stay lighter).
DEBUGGING:
DEBUG (add as an HTML comment while debugging): charts scripts included for {{ request.endpoint }}
OFFLINE DOCKER TEST CASES:
- The page source lists the chart.umd.min.js script before charts.js and neither URL starts with http.
- Pages without charts do not contain these script tags.
-->
EOF

cat << 'EOF' > app/templates/admin/charts.html
<!--
FILE PURPOSE: ADM-19 Admin chart page.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend admin/base_admin.html; page_title "Charts"; the days selector macro in page_actions.
2. Five chart cards in a responsive grid (one column below lg, two from lg): Bookings over time (line, bookings-by-day with the selected days), Booking status (doughnut), Examination completion (grouped bar: booked, evaluation submitted, published), Examiner workload (grouped bar), Average results per examination (bar, y axis 0 to 100). Each card has a one-sentence description that says what the numbers mean.
3. Include charts/_scripts.html in block scripts.
DEBUGGING:
DEBUG (add as an HTML comment while debugging): admin charts days={{ days }}
OFFLINE DOCKER TEST CASES:
- Five canvases exist; the first card URL contains ?days=<selected>.
-->
EOF

cat << 'EOF' > app/templates/examiner/charts.html
<!--
FILE PURPOSE: EXM-10 Examiner chart page.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend examiner/base_examiner.html; page_title "My charts"; days selector.
2. Four cards: Students evaluated per examination (grouped bar), Participants per upcoming slot (stacked bar: booked and seats free), Bookings over time (line), Average result per examination (bar). Descriptions state that only the examiner's own data is shown.
3. Include charts/_scripts.html in block scripts.
DEBUGGING:
DEBUG (add as an HTML comment while debugging): examiner charts days={{ days }}
OFFLINE DOCKER TEST CASES:
- Four canvases exist and none of the data URLs contains a user id.
-->
EOF

cat << 'EOF' > app/templates/student/charts.html
<!--
FILE PURPOSE: STU-11 Student chart page.
PROMPT FOR LLM IMPLEMENTATION:
1. Extend student/base_student.html; page_title "My progress"; days selector.
2. Three cards: Booking history (doughnut of booked, completed, cancelled), Booking trend (line), Results (bar of score percentage per examination, y axis 0 to 100). Empty states are written in friendly text by charts.js ("No data yet. Book a slot to see your history.").
3. Include charts/_scripts.html in block scripts.
DEBUGGING:
DEBUG (add as an HTML comment while debugging): student charts days={{ days }}
OFFLINE DOCKER TEST CASES:
- Three canvases exist; a new student sees the empty-state text after the scripts run (e2e).
-->
EOF

# ============================== JAVASCRIPT ===========================

cat << 'EOF' > app/static/js/charts.js
/*
FILE PURPOSE: Progressive enhancement that turns every canvas[data-chart-url] into a Chart.js chart, with loading, empty and error states and an accessible data table. Tier 2 may use JavaScript (the no-JS rule only protects Tier 1 core logic).
DEPENDS ON: vendor/chartjs/chart.umd.min.js (global Chart), the card markup from templates/charts/_macros.html.
PROMPT FOR LLM IMPLEMENTATION:
1. Plain browser JavaScript in one IIFE, no modules, no framework, no external requests. On DOMContentLoaded find all canvas elements with data-chart-url and initialise each independently (one failing chart must never break the others).
2. For each canvas: set its card state to "loading" (data-chart-state attribute on the canvas: loading, ready, empty, error), fetch the URL with fetch(url, {credentials: "same-origin", headers: {"Accept": "application/json"}}). On HTTP 401 show "Please sign in again."; 403 "You do not have access to this chart."; any other failure or invalid JSON "The chart could not be loaded." with the Retry button visible (clicking it repeats the fetch). Never show raw error text or stack traces.
3. Empty rule: when labels is empty OR every number in every series is 0, set state "empty", show the card's friendly empty text (data-empty-text attribute, default "No data yet.") and do not create a chart.
4. Chart creation: map data-chart-type to Chart.js config: line (tension 0.2, points), bar (grouped), stacked-bar (stacked x and y), doughnut (cutout 60%, legend at the bottom). Integer-only y ticks for counts (precision 0, beginAtZero true); percentage charts (data-y-max="100") fix the y axis to 0..100 and format ticks with a % sign. Responsive true, maintainAspectRatio false (the .chart-box fixes the height).
5. Colours: use this fixed accessible palette in order for series and slices: #1F4E79 (primary), #FD7E14 (orange), #198754 (success), #6F42C1 (purple), #6C757D (secondary), #DC3545 (danger). Do not rely on colour alone: line series also get different borderDash patterns and bar series different borderWidth, and the legend is always shown for more than one series.
6. Motion: when window.matchMedia("(prefers-reduced-motion: reduce)").matches disable all animation (options.animation = false) and set data-animated="false" on the canvas.
7. Accessible data table: after a successful load fill the div #chart-<id>-table with a real table (caption = chart title, th scope="col" for the series names, th scope="row" for each label, numeric cells) built with createElement/textContent (never innerHTML with server data), so screen reader users and keyboard users get the same numbers as the chart.
8. When the chart is ready set data-chart-state="ready" on the canvas (tests wait for it). Destroy an existing Chart instance on Retry to avoid canvas reuse errors. If window.Chart is undefined (vendor file missing) set state "error" with "Charts are unavailable because the Chart.js file is missing." and log one console.error.
9. Keep the file under 220 lines with a short comment per function; no global variables other than the IIFE.
DEBUGGING:
// console.debug("[charts] init", canvas.id, canvas.dataset.chartUrl);   (leave commented; enable while debugging)
OFFLINE DOCKER TEST CASES:
- With demo data every canvas reaches data-chart-state="ready" within 3 seconds and has a non-zero width and height.
- With all-zero data the state is "empty" and no chart object exists; the empty text is visible.
- When the endpoint is blocked (route aborted) the state is "error", the Retry button is visible and clicking it after the route is restored loads the chart.
- With reduced motion emulated, data-animated is "false".
- The data table has one row per label and one column per series plus the label column.
- The browser makes no request to any host other than 127.0.0.1.
*/
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_chart_data.py
"""
FILE PURPOSE: Unit tests for chart_data (data correctness and role scoping).
DEPENDS ON: app/services/chart_data.py, tests/conftest.py (make_chart_dataset, freeze_now).
PROMPT FOR LLM IMPLEMENTATION:
1. Shape tests: test_every_function_returns_valid_shape (labels/series lengths equal, only int/float), test_empty_database_returns_empty_valid_shape for all six functions and all roles allowed to call them.
2. bookings_by_day: test_zero_filled_days_count_equals_days, test_local_date_bucketing_near_midnight_kolkata, test_cancelled_series_uses_cancelled_at, test_window_excludes_older_bookings, test_days_validation (0, 181, "x" raise ValueError; 7, 30, 90, 180 pass).
3. booking_status: test_status_counts_per_role (student own, examiner own slots, admin all).
4. participants_by_slot: test_only_future_non_cancelled_slots, test_limit_and_order, test_label_truncation, test_examiner_scope, test_student_forbidden.
5. examiner_workload: test_admin_labels_are_examiner_names, test_examiner_view_uses_own_examinations, test_not_yet_submitted_counts, test_student_forbidden.
6. examination_completion: test_counts_booked_submitted_published, test_deleted_examinations_excluded, test_limit_most_recent_first, test_examiner_only_assigned.
7. results: test_only_published_included, test_percent_rounding_one_decimal, test_examiner_average_over_own_slots_only, test_admin_average_over_all, test_examinations_without_results_omitted.
8. Scope/PII: test_no_labels_contain_other_users_names_or_emails (student and examiner outputs checked against all fixture names), test_examiner_a_never_sees_b.
DEBUGGING:
# print(f"[DEBUG] chart case {name}: labels={data['labels']} series={data['series']}")
OFFLINE DOCKER TEST CASES:
- 34 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_api_charts.py
"""
FILE PURPOSE: Endpoint tests for /api/v1/charts/*.
DEPENDS ON: tests/conftest.py (api fixture, make_chart_dataset), tests/conftest.py assert_shape.
PROMPT FOR LLM IMPLEMENTATION:
1. test_each_endpoint_shape_for_allowed_roles (loop over endpoint x role table), test_forbidden_roles_403_json (student on participants-by-slot, examiner-workload, examination-completion), test_anonymous_401_json, test_pending_examiner_403_not_approved, test_days_validation_422_with_field, test_default_days_30_labels_count, test_endpoint_equals_service_output, test_no_store_header_and_json_content_type, test_no_identifying_fields_in_payload (walk payloads for keys like id, email, user_id, password), test_scoping_two_examiners_do_not_leak, test_admin_totals_equal_sum_of_examiners, test_api_docs_lists_chart_endpoints (drift guard from P7 still green).
2. Assert exact status, error code and shape in every case.
DEBUGGING:
# print(f"[DEBUG] {response.status_code} {response.get_json()}")
OFFLINE DOCKER TEST CASES:
- 14 tests (about 40 parametrised cases) pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_chart_pages.py
"""
FILE PURPOSE: Markup and access tests for the three chart pages and the dashboard widgets (no browser).
DEPENDS ON: tests/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Access: test_admin_page_roles (admin 200; examiner, student 403; anonymous 302), test_examiner_page_roles (approved 200; pending 302 /pending-approval; others 403), test_student_page_roles.
2. Markup per page: test_card_counts (admin 5, examiner 4, student 3), test_each_canvas_has_role_img_aria_label_and_data_attributes, test_chart_urls_resolve_to_existing_endpoints (each data-chart-url path exists in app.url_map and the role may call it), test_days_selector_marks_current_and_whitelists, test_noscript_fallback_present, test_scripts_local_and_ordered (chart.umd.min.js before charts.js), test_no_external_urls_in_pages.
3. Dashboards: test_dashboard_widgets_present_for_each_role (admin 2, examiner 2, student 2 canvases) and test_non_chart_pages_have_no_chart_scripts.
4. Sidebar: test_admin_sidebar_has_eleven_links_with_charts_under_dashboard.
5. Vendor file: test_vendor_chartjs_file_exists (skip with a clear message when the file has not been downloaded yet, fail in CI on main).
DEBUGGING:
# print(f"[DEBUG] chart page {url} canvases={len(canvases)}")
OFFLINE DOCKER TEST CASES:
- 17 tests pass offline once the Chart.js file is vendored.
"""
EOF

cat << 'EOF' > tests/e2e/test_charts_render.py
"""
FILE PURPOSE: Browser tests that the charts really render, degrade gracefully and stay offline and accessible.
DEPENDS ON: tests/e2e/conftest.py (live_server, page fixtures, clock), scripts/seed_demo_data.py data or make_chart_dataset, vendored Chart.js.
PROMPT FOR LLM IMPLEMENTATION:
1. Mark with @pytest.mark.e2e and @pytest.mark.charts. Seed the live server database with the chart dataset, then for each role (admin, examiner, student) sign in with its own browser context.
2. test_admin_charts_render: open /admin/charts, wait until every canvas has data-chart-state="ready", assert width and height greater than 0, open each "View data as table" details and assert row counts equal the number of labels, assert no console errors and that every network request host is 127.0.0.1.
3. test_examiner_and_student_pages_render (same checks, 4 and 3 charts).
4. test_empty_state_for_new_student: a student with no bookings sees "No data yet." text and no chart object on the history card.
5. test_error_state_and_retry: abort the booking-status request with page.route, assert state "error", the Retry button visible and a friendly message without technical text; remove the route, click Retry, assert state "ready".
6. test_reduced_motion: emulate prefers-reduced-motion and assert data-animated="false".
7. test_keyboard_access: Tab reaches each "View data as table" summary, Enter opens it, and the focus ring is visible (computed outline width greater than 0).
8. test_dashboard_widgets_render on the three dashboards.
DEBUGGING:
# print(f"[DEBUG] chart e2e {url} states={[c.get_attribute('data-chart-state') for c in canvases]}")
OFFLINE DOCKER TEST CASES:
- All tests pass with the network disabled (docker compose --profile test run --rm test make test-e2e).
- Removing app/static/vendor/chartjs/chart.umd.min.js makes the pages show the friendly "Chart.js file is missing" message instead of crashing.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs -type d -empty -exec touch {}/.gitkeep \;

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P8 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Download Chart.js 4.x (UMD, minified) once while online into app/static/vendor/chartjs/chart.umd.min.js and record the version in app/static/vendor/README.md."
echo "2. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P8_update_existing_files.md section by section with the CURRENT files."
echo "3. Run 'docker compose --profile test run --rm test' (or 'make test-core' and 'make test-charts'), then open the dashboards of all three roles on 'make demo-data'."
echo "4. Run 'git add . && git commit -m \"wip: P8 charts\"'  (wip: commits are free-form)."
echo "5. When green: 'git checkout main && git merge --squash phase/p8-charts-visualization && git commit -m \"Milestone-8 EMP-Charts-Visualization\" && git tag p8-done && git push origin main --tags'."
echo "6. Decisions to confirm: six chart endpoints (TDR names three; booking-status, participants-by-slot and results are added so examiner and student charts from the PDR exist); charts need JavaScript with a data-table fallback."
echo "7. Execute P9.sh"
echo "====================================================="
