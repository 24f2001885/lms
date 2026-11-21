#!/usr/bin/env bash
# =====================================================================
# P10.sh - Phase P10: Responsive UI & Styling (Tier 2, Secondary)
# Course commit message : Milestone-10 EMP-Responsive-UI
# Branch                : phase/p10-responsive-ui
# Depends on            : P9 (tag p9-done), Gate A (tag tier1-complete)
# Source of truth       : PDR 6 (NFR: responsive, WCAG 2.1 AA, Chrome/Edge/Firefox),
#                         Design Plan 1, 2, 6, 7, 8 (breakpoints, a11y, palette),
#                         TDR 7 (Bootstrap only), Master Blueprint 3.2 (P10 row)
# Acceptance            : screens usable at 375, 768 and 1280 px; contrast and
#                         keyboard checks pass.
# This script contains NO application logic: only git/directory setup
# and prompt-only seed files. Files that already hold real code are never
# overwritten; their changes are in docs/seed_updates/P10_update_existing_files.md.
# =====================================================================
set -euo pipefail

PHASE="P10"
BRANCH="phase/p10-responsive-ui"
PREV_TAG="p9-done"

[ -d .git ] || { echo "ERROR: run this from the repository root."; exit 1; }
git rev-parse -q --verify "refs/tags/${PREV_TAG}" >/dev/null || { echo "ERROR: tag ${PREV_TAG} not found. Finish and tag P9 first."; exit 1; }
git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || { echo "GATE A CLOSED: tag tier1-complete is missing."; exit 1; }
[ -f app/validation/limits.py ] || { echo "ERROR: app/validation/limits.py missing (P9 not implemented)."; exit 1; }

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
git checkout main
[ -z "$(git status --porcelain)" ] || { echo "ERROR: working tree not clean. Commit or stash first."; exit 1; }
bash scripts/check_gate.sh "$BRANCH" || { echo "ERROR: gate check refused this branch."; exit 1; }
echo "Checking out milestone branch..."
git checkout -b "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup (only what P10 needs)
# ---------------------------------------------------------------------
mkdir -p app/static/css scripts docs docs/seed_updates
mkdir -p tests/unit tests/integration tests/e2e

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# ============================ UPDATE PROMPTS =========================

cat << 'EOF' > docs/seed_updates/P10_update_existing_files.md
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
EOF

# ============================== STYLESHEET ===========================

cat << 'EOF' > app/static/css/responsive.css
/*
FILE PURPOSE: All responsive layout and accessibility styling (Design Plan section 8). Loaded after app.css. Bootstrap 5 utilities and components do the heavy lifting; this file only adds what Bootstrap does not provide. Mobile-first: base rules are for xs, min-width media queries add behaviour upward.
DEPENDS ON: Bootstrap 5 CSS variables, palette tokens in app.css.
PROMPT FOR LLM IMPLEMENTATION:
1. Reflow (WCAG 1.4.10, down to 320 CSS px): img, svg, canvas, video max-width 100%; main and flex children min-width 0; long words and emails wrap (overflow-wrap: anywhere on .text-break, table cells and card text); pre and code wrap; no fixed pixel widths anywhere in this file except max-width values.
2. Focus (WCAG 2.4.7, 1.4.11): a global :focus-visible rule with outline 3px solid #0B5ED7 and outline-offset 2px (5.84:1 on white and 5.31+ on the page background); inside .admin-sidebar and .navbar-dark the outline is #FFFFFF (15:1 on #14283B); never outline: none without a replacement. Skip link: visually hidden until focused, then fixed at the top-left with a solid background and the same focus ring.
3. Touch targets below 768 px (Design Plan: larger touch targets): .btn, .nav-link, .navbar-toggler, .btn-close, .form-control, .form-select, .form-check-input (24 px box with a 44 px clickable label), .page-link and summary elements get min-height 44px and min-width 44px where they are icon-only; links inside running text are exempt.
4. xs (under 576 px): .btn-xs-block is width 100% with 0.5rem vertical gap; .btn-group-xs-stack is flex column with gap 0.5rem (flex row from sm); .auth-card margin-inline 0.75rem; .page-container padding-inline 0.75rem; .stat-card and chart cards full width; modals use .modal-dialog margin 0.5rem; .chart-box height 220px.
5. TABLE CARDS (under 576 px only): .table-stack thead is visually hidden but kept accessible (position absolute, 1px size, clip rect 0, overflow hidden, white-space nowrap); .table-stack tbody tr is display block with a 1px border, border-radius, background white, margin-bottom 0.75rem and padding 0.5rem; .table-stack td is display flex, justify-content space-between, gap 1rem, border none, text-align right; .table-stack td::before shows content attr(data-label) in bold, text-align left, flex 0 0 40%; .td-actions is flex-wrap with the buttons stacked full width; empty cells keep their label. From 576 px upward .table-stack behaves as a normal Bootstrap table (all overrides live inside @media (max-width: 575.98px)); .table-responsive provides horizontal scrolling for sm and md.
6. Admin shell: .admin-shell is a flex row from lg; below lg the sidebar is a Bootstrap offcanvas-lg drawer (width 280px, background #14283B, light text #E6EDF3 12.7:1, links padding 0.75rem 1rem for 44 px height, current item has a 4px left border #FFC107 on #14283B 9.2:1 and bold text); the top bar is sticky with z-index below the offcanvas backdrop; .admin-content has min-width 0 and padding 1rem (1.5rem from lg).
7. md (768 to 991): two-column layouts for forms with paired fields (row row-cols-md-2 already in markup); tables scroll inside .table-responsive; card grids two across.
8. lg (992 to 1199): sidebar static, 240px, sticky full height; dashboards 3 cards per row (handled by row-cols-lg-3).
9. xl (1200 and up): .page-container max-width 1200px; the admin content area inside the shell is capped at 1200px as well.
10. Navbar: .navbar-collapse links full width below lg with 44px height; active link underlined 3px (not colour alone); the Logout button looks like a nav link but remains a button.
11. Forced colours and high contrast: @media (forced-colors: active) keep borders on badges, buttons, cards and form controls (border: 1px solid CanvasText) and use Highlight for the focus ring.
12. Motion: @media (prefers-reduced-motion: reduce) set animation-duration and transition-duration to 0.01ms and scroll-behavior auto for all elements including Bootstrap offcanvas, collapse and modal.
13. Text spacing (WCAG 1.4.12): no fixed heights on text containers (use min-height only), so user-applied line-height 1.5, letter-spacing 0.12em, word-spacing 0.16em and paragraph spacing 2em never clip text.
14. Print: hide navbar, sidebar, buttons and chart controls, show links' URLs is NOT required; keep it to ten lines.
15. Keep the file under 260 lines, grouped by the headings above, every colour value commented with its contrast ratio.
DEBUGGING:
Temporary debug aid: add html { outline: 2px dashed magenta; } to confirm the file loads, then remove it.
OFFLINE DOCKER TEST CASES:
- No http:// or https:// string and no @import in the file.
- At 375 px a .table-stack td::before shows its data-label (checked in the browser test); at 576 px the table is a normal table.
- Every colour pair used in this file meets 4.5:1 (text) or 3:1 (focus ring, borders) in the contrast test.
*/
EOF

# ================================ SCRIPTS ============================

cat << 'EOF' > scripts/a11y_audit.py
"""
FILE PURPOSE: Offline, dependency-free static accessibility and responsive-markup auditor for the rendered pages (the project's WCAG 2.1 AA safety net; no axe-core, no network). Used by tests and by "make a11y".
DEPENDS ON: Python standard library (html.parser, re, dataclasses, argparse), app factory and scripts/seed_demo_data.py (only in CLI mode).
PROMPT FOR LLM IMPLEMENTATION:
1. Core API: dataclass Issue(rule, severity, message, snippet, page) with severity "error" or "warning"; function audit_html(html, page="") -> list[Issue] that parses the document with html.parser into a light tree (tag, attrs, text, children, parent) and runs the rule functions below. The module must import without Flask so unit tests can call audit_html on small snippets.
2. Rules (each a small function, id in the message): A11Y-01 html has a non-empty lang; A11Y-02 non-empty title; A11Y-03 exactly one h1; A11Y-04 heading levels never skip downward by more than one; A11Y-05 exactly one main landmark, one header, one footer, and a nav landmark has an accessible name when there is more than one nav; A11Y-06 the first focusable element is a skip link whose #target exists; A11Y-07 every input (except hidden, submit, button), select and textarea has an accessible name (label for, wrapping label, aria-label or aria-labelledby); A11Y-08 buttons and links have an accessible name (text, aria-label, aria-labelledby, img alt, title as last resort is an error); A11Y-09 img has alt (empty alt allowed only with role presentation or aria-hidden); A11Y-10 no duplicate id values; A11Y-11 aria-labelledby, aria-describedby, aria-controls and label-for ids exist; A11Y-12 th has scope or headers, data tables have a caption or aria-label; A11Y-13 no tabindex above 0; A11Y-14 target=_blank has rel containing noopener; A11Y-15 viewport meta exists and has no user-scalable=no or maximum-scale below 2; A11Y-16 inputs for email, name, tel and passwords have a matching autocomplete; A11Y-17 iframe and object have a title; A11Y-18 modals (class modal) have role dialog or aria-modal, aria-labelledby and a close control; A11Y-19 the flash container has aria-live polite or assertive and alerts have role alert; A11Y-20 offcanvas and collapse toggles have aria-controls and an accessible name, aria-expanded on collapse toggles; A11Y-21 colour is not the only cue: a badge or status element has visible text; A11Y-22 tables inside forms keep labels for their inputs.
3. Responsive rules (severity error): R-01 viewport meta present; R-02 every table.table-stack has role table plus roles on rows and cells and every td has a non-empty data-label equal to the text of the th of the same column index; R-03 every data table is inside .table-responsive; R-04 no inline style sets a fixed width above 320px; R-05 every .btn inside .td-actions or a booking/cancel form has btn-xs-block; R-06 the admin pages contain #adminSidebar with offcanvas-lg and a toggler pointing to it; R-07 every navbar-expand-lg has a toggler with aria-controls, aria-expanded and aria-label; R-08 no element uses the display utility that hides table columns (d-none on th/td) without a visible alternative.
4. crawl(app, roles, page_urls) iterates the given URLs per role with a Flask test client, audits every HTML 200 response and returns {page: [Issue]}; non-HTML and redirects are skipped; the crawl never submits forms.
5. CLI: python scripts/a11y_audit.py [--demo] [--role admin|examiner|student|public] [--format text|json]. With --demo it builds the app on a temporary database, runs scripts/seed_demo_data.py main(app), signs in as each demo role, builds the URL list from app.url_map (GET rules, path variables filled from demo ids) and prints a table page, rule, severity, message. Exit code 0 when there are no errors (warnings allowed), 1 when any error exists, 2 on usage problems.
6. No third-party package; no network; output deterministic (sorted).
DEBUGGING:
# print(f"[DEBUG] audit page={page} nodes={node_count} issues={len(issues)}")
OFFLINE DOCKER TEST CASES:
- audit_html on a minimal good page returns [].
- Each rule has a bad snippet in tests/unit/test_a11y_audit_rules.py that triggers exactly that rule id.
- python scripts/a11y_audit.py --demo exits 0 on the finished project and prints the number of pages audited.
"""
EOF

# ================================ DOCS ===============================

cat << 'EOF' > docs/accessibility_responsive_checklist.md
<!--
FILE PURPOSE: Manual quality checklist and results log for responsiveness and WCAG 2.1 AA (things the automated tests cannot prove), used for the report and the viva.
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Accessibility and responsive checklist". Intro: automated checks (make a11y, make test-ui) plus this manual pass; record date, tester, browser and result for every row.
2. Table "Responsive matrix": rows for widths 320, 375, 768, 1024 and 1280 px and for Chrome, Edge and Firefox (PDR NFR), columns: Admin (dashboard, examinations list, examination detail, rubric page, bookings list, charts), Examiner (dashboard, slot form, evaluation form), Student (examinations, booking modal, bookings, results), Public (login, register). Cells are empty "pass/fail + note" fields.
3. Checklist sections with checkboxes: Keyboard (every control reachable and operable, visible focus, skip link, modal and drawer focus trap and return, Esc closes), Screen reader spot checks with NVDA or VoiceOver (page title, headings list, landmarks list, form labels and errors announced, table navigation on a stacked table, chart data table, flash messages announced once), Zoom and reflow (200 percent and 400 percent, 320 px, no horizontal scrolling except data tables), Colour and contrast (the contrast test list plus focus ring on every background, never colour alone), Motion (reduced motion respected), Text spacing (apply the WCAG 1.4.12 bookmarklet values, nothing clipped), Touch (44 px targets on a real phone), Forms (errors linked to fields, summary focus, required marked in text).
4. A "Known limitations and decisions" section prefilled with: Admin sidebar is a drawer below 992 px (including md), tables become cards below 576 px, charts need JavaScript with a data-table fallback, Test-taking pages (Tier 3) are desktop-first and designed later.
5. Keep it under 120 lines of plain Markdown.
DEBUGGING:
(none: documentation file)
OFFLINE DOCKER TEST CASES:
- The matrix lists every page named in the Design Plan for the three roles at the five widths.
-->
EOF

# ================================ TESTS ==============================

cat << 'EOF' > tests/unit/test_color_contrast.py
"""
FILE PURPOSE: Proves the palette meets WCAG 2.1 AA contrast (4.5:1 text, 3:1 non-text) and that the CSS really contains the fixed tokens.
DEPENDS ON: app/static/css/app.css, app/static/css/responsive.css (read as text), Python only.
PROMPT FOR LLM IMPLEMENTATION:
1. Implement the WCAG relative luminance and contrast ratio functions in the test file (sRGB linearisation, (L1+0.05)/(L2+0.05)); a helper parse_css_colour(css_text, token) that finds hex values assigned to custom properties or rules.
2. Text pairs that must be at least 4.5: body #212529 on #F5F7FA and on white; muted #5C636A on #F5F7FA and on white; link #1F4E79 on #F5F7FA; white on primary #1F4E79 and hover #173B5C; white on success #198754, danger #DC3545, secondary #6C757D and purple #6F42C1; dark #212529 on warning #FFC107, on orange #FD7E14 and on info #0DCAF0; amber text #7A5C00 on white; invalid-feedback #B02A37 on #F5F7FA; success text #146C43 on white; sidebar text #E6EDF3 and muted #AFC0D0 on #14283B; alert pairs #055160/#CFF4FC, #664D03/#FFF3CD, #842029/#F8D7DA, #0F5132/#D1E7DD.
3. Non-text pairs that must be at least 3.0: form control border #6C757D on white and on #F5F7FA; focus ring #0B5ED7 on white and on #F5F7FA; focus ring #FFFFFF on #14283B; outline-badge border #7A5C00 on white; sidebar active border #FFC107 on #14283B.
4. Negative guard tests documenting why fixes exist (they must FAIL the threshold, proving the old values were wrong): #6C757D on #F5F7FA is below 4.5, white on #FD7E14 below 4.5, white on #0DCAF0 below 4.5, #DEE2E6 on white below 3.
5. CSS token tests: app.css contains the fixed muted colour #5C636A, form-control border #6C757D, badge-full with dark text, badge-outline-warning with #7A5C00, invalid-feedback #B02A37; responsive.css contains the focus ring #0B5ED7, the prefers-reduced-motion block, the forced-colors block, and the table-stack rules inside a max-width 575.98px media query; neither file contains http:// or https:// or @import.
6. Print a small table of all ratios when run with -s so the numbers can be pasted into the report.
DEBUGGING:
# print(f"[DEBUG] contrast {fg} on {bg} = {ratio:.2f}")
OFFLINE DOCKER TEST CASES:
- 45 parametrised cases pass offline; changing the muted colour back to #6C757D makes the muted-on-page-background case fail.
"""
EOF

cat << 'EOF' > tests/unit/test_a11y_audit_rules.py
"""
FILE PURPOSE: Tests for the auditor itself: every rule fires on a bad snippet and stays silent on a good one (so a green audit is meaningful).
DEPENDS ON: scripts/a11y_audit.py (import by path).
PROMPT FOR LLM IMPLEMENTATION:
1. Provide a GOOD_PAGE constant: a minimal valid page (lang, title, viewport, skip link, header, nav with aria-label, main with tabindex -1, one h1, a labelled form, an accessible data table with caption and scopes, a footer) and assert audit_html(GOOD_PAGE) == [].
2. For each rule id A11Y-01 to A11Y-22 and R-01 to R-08 write one test that mutates GOOD_PAGE minimally to break that single rule and asserts that exactly that rule id is reported (and no other error), for example removing lang, adding a second h1, an input without label, a duplicate id, an aria-describedby to a missing id, tabindex="3", target=_blank without rel, user-scalable=no, a table-stack td without data-label, a td-actions button without btn-xs-block, an admin page without #adminSidebar.
3. test_issue_ordering_is_deterministic and test_crawl_skips_non_html_and_redirects (use a tiny fake app/client).
4. test_cli_exit_codes with subprocess: --demo exit 0 on a clean tree; a temporary bad template makes it exit 1 (use monkeypatch on the crawl function instead of editing files).
DEBUGGING:
# print(f"[DEBUG] rule test {rule}: issues={[i.rule for i in issues]}")
OFFLINE DOCKER TEST CASES:
- About 35 tests pass offline.
"""
EOF

cat << 'EOF' > tests/integration/test_responsive_markup.py
"""
FILE PURPOSE: Structural responsive checks over every rendered page of every role (no browser needed).
DEPENDS ON: tests/conftest.py (page_urls fixture, factories), scripts/a11y_audit.py (responsive rules R-01 to R-08).
PROMPT FOR LLM IMPLEMENTATION:
1. test_every_page_has_viewport_and_css (viewport exactly "width=device-width, initial-scale=1", app.css then responsive.css, both local).
2. test_data_tables_follow_the_table_stack_contract: for all pages and roles every data table is wrapped in .table-responsive, has class table-stack with the role attributes, th scope col, and every td data-label equals its column header text (reports page, table index and column on failure).
3. test_admin_shell_drawer_markup: each admin page contains #adminSidebar with offcanvas-lg, a hamburger toggler with d-lg-none and the aria attributes, a close button with aria-label, and exactly 11 sidebar links.
4. test_navbars_have_toggler for examiner and student pages (aria-controls mainNav, aria-expanded, aria-label) and the Logout form is inside the collapse.
5. test_action_buttons_are_full_width_on_xs: booking, cancel, approve and evaluation buttons carry btn-xs-block and sit in a btn-group-xs-stack when more than one.
6. test_grids_use_documented_column_classes (dashboards row-cols-1 row-cols-md-2 row-cols-lg-3; student examinations row-cols-sm-2).
7. test_no_fixed_width_inline_styles_and_no_hidden_columns (no style with width above 320px, no d-none on th/td).
8. test_container_and_main_landmark (page-container present, main has tabindex -1, skip link first).
9. Mark with @pytest.mark.responsive.
DEBUGGING:
# print(f"[DEBUG] responsive check {role} {url}: tables={table_count} issues={issues}")
OFFLINE DOCKER TEST CASES:
- All pages (about 60 across the three roles) pass; removing a data-label makes test_data_tables_follow_the_table_stack_contract name the page and column.
"""
EOF

cat << 'EOF' > tests/integration/test_accessibility_static.py
"""
FILE PURPOSE: Runs the full static accessibility audit over every page of every role and fails on any error (the automated half of WCAG 2.1 AA).
DEPENDS ON: scripts/a11y_audit.py, tests/conftest.py (page_urls fixture).
PROMPT FOR LLM IMPLEMENTATION:
1. test_all_pages_have_zero_a11y_errors: for public pages (login, register, error pages, API docs), admin, examiner (approved) and student, call crawl and assert that no Issue with severity "error" exists; on failure print a compact table page / rule / message.
2. test_warnings_are_listed_not_fatal: warnings are collected and printed with -s but never fail the test; keep an allow-list file tests/a11y_allowlist.txt (rule id plus page glob plus reason) that starts EMPTY and must be justified line by line.
3. test_forms_error_state_markup: render each form page with invalid POST data (using the P9 cases) and audit the RESULT pages as well, so the error state (summary, aria-invalid, error ids, aria-describedby) is covered.
4. test_flash_messages_region: a page with success, warning and danger flashes passes A11Y-19.
5. test_modal_markup: pages with confirm modals pass A11Y-18 (role dialog, aria-labelledby, close control).
6. test_error_pages_audited: 403, 404 and 500 pages pass the same rules.
7. Mark with @pytest.mark.a11y.
DEBUGGING:
# print(f"[DEBUG] a11y {role} pages={len(pages)} errors={error_count} warnings={warning_count}")
OFFLINE DOCKER TEST CASES:
- Zero errors over all pages; adding an unlabeled input to any template makes the matching page and rule appear in the failure output.
"""
EOF

cat << 'EOF' > tests/e2e/test_responsive_viewports.py
"""
FILE PURPOSE: Real-browser checks at the Design Plan widths: 375, 768 and 1280 px (acceptance) plus 320 px reflow and 200 percent zoom.
DEPENDS ON: tests/e2e/conftest.py (live_server, browser fixtures, E2E_BROWSERS), demo or chart dataset.
PROMPT FOR LLM IMPLEMENTATION:
1. Mark @pytest.mark.e2e and @pytest.mark.responsive; parametrise viewport (320x640, 375x812, 768x1024, 1280x800, 640x800 as 200 percent zoom of 1280) and role (public, admin, examiner, student); visit every page returned by the page_urls helper (or a representative list of at least 8 pages per role).
2. All viewports: no horizontal scrolling (document.documentElement.scrollWidth <= window.innerWidth), no console errors, no request leaving 127.0.0.1, every page has focusable content.
3. 375 px: the hamburger toggler is visible and the sidebar/menu hidden; admin drawer opens, focus moves into it, Tab cycles inside the drawer, Escape closes it and focus returns to the toggler; examiner and student navbar collapse opens and closes; a .table-stack row is display block, thead is visually hidden, td::before content equals its data-label (getComputedStyle(td, "::before").content), action buttons have the same width as their container (within 1 px), and tap targets of buttons, nav links, form controls and icon buttons are at least 44x44 px.
4. 768 px: card grids show two columns (compare card x positions), tables are normal tables inside a scrolling container (display table, not block), the admin sidebar is still a drawer with the hamburger visible.
5. 1280 px: the admin sidebar is visible and static, the hamburger is hidden, dashboard cards are three per row, content width does not exceed 1200 px plus the sidebar.
6. 320 px and 640x800: reflow without horizontal scrolling for every page; long email addresses and examination names wrap (no element wider than the viewport).
7. Text spacing: inject a style applying line-height 1.5, letter-spacing 0.12em, word-spacing 0.16em and paragraph spacing 2em to all elements, then assert no horizontal overflow and that no element with overflow hidden has scrollHeight greater than clientHeight plus 1 (no clipped text).
8. Reduced motion: emulate prefers-reduced-motion and assert the computed transition-duration of the offcanvas is 0 (or 1 ms or less).
9. Take a full-page screenshot per role and width into test-results/responsive/ (kept as report material).
DEBUGGING:
# print(f"[DEBUG] viewport={width}x{height} role={role} url={url} overflow={overflow}")
OFFLINE DOCKER TEST CASES:
- All parametrised cases pass offline on chromium; with E2E_BROWSERS=chromium,firefox the same cases pass on both engines.
- Removing the table-stack CSS makes the 375 px table test fail; removing offcanvas-lg makes the drawer test fail.
"""
EOF

cat << 'EOF' > tests/e2e/test_keyboard_accessibility.py
"""
FILE PURPOSE: Keyboard-only and focus behaviour in a real browser (WCAG 2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7).
DEPENDS ON: tests/e2e/conftest.py.
PROMPT FOR LLM IMPLEMENTATION:
1. Mark @pytest.mark.e2e and @pytest.mark.a11y.
2. test_skip_link_first_and_works: first Tab focuses "Skip to main content", Enter moves focus to main (document.activeElement is main).
3. test_focus_indicator_visible_everywhere: Tab through every focusable element on each representative page (public, admin, examiner, student) and assert the focused element has a computed outline-width of at least 2px (or an equivalent box-shadow) and an outline colour that is not transparent; on the admin sidebar the colour is white.
4. test_no_keyboard_trap: pressing Tab repeatedly (limit 200) eventually returns focus to the document start or browser chrome without getting stuck; Shift+Tab does the reverse.
5. test_modal_focus_management: open the booking confirm modal and a delete confirm modal with the keyboard; focus moves inside, Tab and Shift+Tab stay inside, Escape closes, focus returns to the trigger button.
6. test_offcanvas_focus_management at 375 px (same assertions for the Admin drawer).
7. test_logical_tab_order: the order of focus follows the visual order for the booking form, the examination form and the evaluation form (compare bounding-box top and left of consecutive focused elements, allowing one wrap per row).
8. test_forms_operable_by_keyboard: fill and submit the registration form and the slot form using only the keyboard (Tab, typing, Space on checkboxes and radios, Enter to submit) and reach the success flash; the select element changes with arrow keys.
9. test_live_regions: after a successful action the flash text is inside an element with aria-live polite or role alert, and after a failed validation the error summary receives focus.
10. test_headings_and_landmarks_navigable: each page exposes one main, a labelled nav and a sensible heading outline (use the accessibility tree snapshot of Playwright and assert the roles).
DEBUGGING:
# print(f"[DEBUG] focus step={step} element={tag}#{element_id} outline={outline_width}")
OFFLINE DOCKER TEST CASES:
- All tests pass offline; removing the global :focus-visible rule makes test_focus_indicator_visible_everywhere fail.
"""
EOF

# --- keep empty folders in Git ---
find app tests docs scripts -type d -empty -exec touch {}/.gitkeep \;
chmod +x scripts/*.sh 2>/dev/null || true

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P10 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code. Apply docs/seed_updates/P10_update_existing_files.md in ORDER (base.html and the three layouts first, then the table templates, then app.css) with the CURRENT files."
echo "2. Run 'make a11y' and 'make test-ui', then 'docker compose --profile test run --rm test' (or 'make test-core'); open the app at 375, 768 and 1280 px and fill in docs/accessibility_responsive_checklist.md."
echo "3. Run 'git add . && git commit -m \"wip: P10 responsive UI\"'  (wip: commits are free-form)."
echo "4. When green: 'git checkout main && git merge --squash phase/p10-responsive-ui && git commit -m \"Milestone-10 EMP-Responsive-UI\" && git tag p10-done && git push origin main --tags'."
echo "5. Decisions to confirm: Admin sidebar is a drawer below 992 px (covers md); tables become cards only below 576 px; palette fixes for muted text, orange and info badges, form borders and the amber badge (contrast measured); responsive checks use a home-made offline auditor instead of axe-core."
echo "6. Execute P11.sh (Flask-Login and security) when it is generated."
echo "====================================================="
