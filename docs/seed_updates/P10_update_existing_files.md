<!--
FILE PURPOSE: Update prompts for files already implemented in earlier phases that P10 must change. Do NOT regenerate them from scratch; give the LLM the section plus the CURRENT file. Apply the sections in order. Bootstrap 5 is the ONLY CSS framework (course rule): everything below uses Bootstrap utilities, Bootstrap components (navbar, offcanvas, collapse, modal, card, grid) and project CSS; no other CSS library, no CSS preprocessor.

BREAKPOINTS (Design Plan section 8, Bootstrap 5 grid)
- xs under 576: single column, hamburger navigation, Admin sidebar becomes an off-canvas drawer, record tables become stacked cards, booking/cancel/evaluation action buttons are full width.
- sm 576 to 767: single column, larger touch targets (44 px minimum), two-column card grid for examinations.
- md 768 to 991: two-column layouts, Admin sidebar still a drawer (collapsible), tables scroll horizontally inside their container.
- lg 992 to 1199: Admin sidebar visible, dashboard cards 3 per row.
- xl 1200 and up: content capped at 1200 px.

SECTION 1: app/templates/base.html
1. After the app.css link add the stylesheet url_for static css/responsive.css. Keep the viewport meta exactly "width=device-width, initial-scale=1" (never maximum-scale, never user-scalable=no: users must be able to zoom).
2. Skip link text "Skip to main content", first focusable element, targets the main element which gets tabindex="-1" so focus really moves. Keep lang="en", one main landmark, header and footer landmarks, flash region aria-live="polite".
3. Wrap page content in a container with the class page-container (max-width 1200px, centred) unless a child template overrides it.

SECTION 2: app/templates/admin/base_admin.html (drawer)
1. Replace the P3 "collapsed block below 992px" with a Bootstrap responsive off-canvas: a top bar (always visible) containing a hamburger button with class d-lg-none, data-bs-toggle="offcanvas", data-bs-target="#adminSidebar", aria-controls="adminSidebar", aria-label "Open navigation menu", the brand, the user name and the Logout form.
2. The aside becomes id="adminSidebar" class "offcanvas-lg offcanvas-start admin-sidebar" with tabindex="-1" and aria-labelledby="adminSidebarTitle": an offcanvas-header (d-lg-none) with the title "Navigation" (id adminSidebarTitle) and a close button (btn-close, aria-label "Close navigation menu", data-bs-dismiss="offcanvas", data-bs-target="#adminSidebar"), then an offcanvas-body containing the existing nav (aria-label "Admin") with all 11 links, current page marked aria-current="page".
3. From lg upward the sidebar is a static column (240 px); below lg it is the drawer (this covers the md "collapsible" requirement). The content area gets min-width 0 so wide tables never push the page sideways.

SECTION 3: app/templates/examiner/base_examiner.html and app/templates/student/base_student.html
1. Use navbar navbar-expand-lg. The toggler button has class navbar-toggler, data-bs-toggle="collapse", data-bs-target="#mainNav", aria-controls="mainNav", aria-expanded="false" and aria-label "Toggle navigation". The links and the Logout form live inside div#mainNav.collapse.navbar-collapse. Current page link has aria-current="page". Logout stays a POST form with CSRF.
2. Below lg the menu items are full-width tap targets (padding handled in responsive.css).

SECTION 4: every template that renders a record table
1. Files: admin/courses_list, examinations_list, examiners_list, students_list, slots_list, slot_detail, bookings_list, evaluations_list, history (all four tabs), search_results, examiner_detail, student_detail, rubrics, examination_detail (examiners panel and rubric summary), booking_detail (evaluation and history tables if any); examiner/slots_list, slot_students, evaluations_pending, evaluations_submitted, evaluation_form (criteria table), examination_detail; student/bookings, history, results, result_detail, examination_detail (slots table); api/docs (endpoint table).
2. Markup rule for a data table: wrapper div.table-responsive (the fallback for sm to md and for browsers without the card layout), table class "table table-hover align-middle table-stack", caption (visually hidden class visually-hidden is fine) describing the table, th scope="col" in thead, and EVERY td carries data-label with exactly the text of its column header (action cells data-label="Actions" and class td-actions). Because the card layout changes table display, add the roles role="table" on the table, role="rowgroup" on thead and tbody, role="row" on tr, role="columnheader" on th and role="cell" on td, but ONLY on table-stack tables.
3. Key-value tables with two columns or fewer and small chart data tables are exempt: they use class "table table-sm table-static" and keep the scroll wrapper.
4. Do not hide columns with display classes (information must stay available); long text cells use class text-break.

SECTION 5: action buttons and forms on small screens
1. Add class btn-xs-block to: Book / Confirm booking / Cancel booking buttons (student), Save, Submit, Publish, Save draft (the three evaluation buttons stack with a gap), Approve, Reject, Deactivate, Activate, Reschedule, Move booking, modal confirm buttons, login and register submit buttons. Wrap groups of related buttons in div.btn-group-xs-stack so they stack on xs and sit inline from sm.
2. Form fields: no change in markup; touch size is handled in responsive.css (44 px minimum height below 768 px).

SECTION 6: grids
1. Dashboards (admin stat cards, examiner and student cards): row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3.
2. student/examinations.html and examiner/examinations_list.html card grids: row row-cols-1 row-cols-sm-2 g-3.
3. Chart cards: col-12 col-lg-6 (already one per row below lg).
4. auth cards (login, register, change password) and error pages: use the class auth-card (max-width 420px, width 100%, centred, side margins on xs).

SECTION 7: app/static/css/app.css (contrast fixes found by the audit of the Design Plan palette; keep the rest)
1. Muted text: #6C757D fails 4.5:1 on the page background #F5F7FA (4.37). Set the muted text colour used by .text-muted, .form-text, small and .deadline-note to #5C636A (5.68 on #F5F7FA, 6.09 on white). Placeholders #5C636A.
2. Badges: white text on orange #FD7E14 (2.57) and on info #0DCAF0 (1.96) FAIL. .badge-full and .text-bg-info use dark text #212529 (6.00 and 7.88). White text stays only on primary, success #198754 (4.53), danger #DC3545 (4.53), secondary, purple.
3. The "Closed" examination badge (class badge-outline-warning): text and border #7A5C00 on white (6.25); keep it outlined, 1px solid, background transparent.
4. Form controls and checkboxes: the default border #DEE2E6 (1.3:1) fails the 3:1 non-text rule. Use border-color #6C757D (4.69 on white, 4.37 on the page background) for .form-control, .form-select, .form-check-input.
5. Validation text: .invalid-feedback and .text-danger inside forms use #B02A37 (6.05 on the page background); alerts keep Bootstrap's text colours (all above 7:1).
6. Success text used on white (for example "Total 100: ready") uses #146C43 (6.45).
7. Links inside main content are underlined by default (not only coloured); hover increases thickness. Navigation links and buttons are exempt.
8. Keep the palette tokens of the Design Plan otherwise unchanged; document each change in a comment with the contrast ratio.

SECTION 8: app/static/js/charts.js (P8)
1. On widths below 576 px set the legend position to "bottom" with smaller font, limit x tick rotation to 45 degrees, and enable ticks.autoSkip so labels never overlap; re-apply on resize through Chart.js's own responsive handling (no custom resize listeners).

SECTION 9: tests
1. tests/conftest.py: add fixture page_urls(role) returning every GET page URL of that role with path variables resolved from a prepared dataset (use make_chart_dataset plus one booking, evaluation, slot, examination, user per id), built from app.url_map; skip /api paths and POST-only routes.
2. tests/e2e/conftest.py: parametrise the browser from the environment variable E2E_BROWSERS (default "chromium", also accepts firefox and webkit when installed) so the same tests can run on Chrome-family and Firefox engines.
3. Update any test that expected the P3 "collapsed sidebar block" or a navbar without the toggler.

SECTION 10: pyproject.toml, Makefile, README.md, docs
1. pyproject.toml: register markers a11y and responsive. Makefile: targets a11y (python scripts/a11y_audit.py --demo) and test-ui (pytest -m "a11y or responsive").
2. README.md: section "Responsive layout and accessibility" (breakpoints, how to add a table with table-stack, running make a11y, link to docs/accessibility_responsive_checklist.md).
DEBUGGING:
# print("[DEBUG] applied P10 update section N")
OFFLINE DOCKER TEST CASES:
- After all sections the P0-P9 suite passes (templates gain attributes only; no text changes).
- The accessibility audit script reports zero errors over all pages of all three roles on demo data.
- At 375 px no page scrolls horizontally and the Admin menu opens as a drawer.
-->
