# Examination Management Portal (EMP)

The **Examination Management Portal (EMP)** is a role-based web application designed for institutions to streamline the scheduling, slot reservation, and evaluation workflows for viva, practical, and project-demo examinations. Built with Python, Flask, Jinja2, Bootstrap 5, and SQLite, EMP provides dedicated, strictly isolated portals for **Administrators**, **Examiners**, and **Students** with automatic capacity enforcement and complete audit history.

---

## 1. Delivery Tiers & Gate Discipline

EMP follows a strict gated delivery model:

| Tier | Phases | Scope & Contents | Start Condition / Gate |
|---|---|---|---|
| **Tier 1: Primary** | P0 – P6 | Mandatory course scope (M0–M6): Auth, RBAC, Admin controls, Examiner slots, Student booking, and Evaluation tracking. | Starts immediately. |
| **Tier 2: Secondary** | P7 – P12 | Recommended course scope: RESTful JSON API (`/api/v1`), Chart.js visualizations, dual-layer validation, responsive polish, Flask-Login, and scorecard PDF. | **Gate A:** All Tier 1 acceptance checks pass; Git tag `tier1-complete` exists. |
| **Tier 3: Tertiary** | P13 – P17 | Additive scope: MCQ online tests (3 delivery modes), anti-cheat monitoring with auto-submit, and Razorpay fee payments (test mode). | **Gate B:** All Tier 1 & 2 checks pass; Git tag `tier2-complete` exists. Flags off by default. |

> **Hard Constraint:** No Tier 3 module, table, route, or branch is created before Gate B. Tier 3 features live behind feature flags (`ENABLE_ONLINE_TESTS`, `ENABLE_PROCTORING`, `ENABLE_PAYMENTS`) that remain disabled by default.

---

## 2. Quick Start

Follow these steps to run the application locally on a clean machine:

```bash
# 1. Clone the private repository and navigate to root
git clone <your-repo-url>
cd emp

# 2. Create and activate a Python 3.11+ (3.12 recommended) virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 3. Install Tier 1 runtime dependencies
pip install -r requirements.txt

# 4. Configure local environment variables
cp .env.example .env
# Edit .env and customize SECRET_KEY, ADMIN_EMAIL, and ADMIN_INITIAL_PASSWORD

# 5. Programmatically create SQLite schema and seed initial Admin
flask --app app init-db

# 6. Start the local Flask development server
flask --app app run --debug
```

---

## 3. Charts & Visualizations (Milestone P8)

EMP includes role-scoped visual analytics powered by Chart.js (v4.4.7 vendored offline at `app/static/vendor/chartjs/chart.umd.min.js`):

- **Admin (`/admin/charts` & dashboard widget):** Bookings over time (line), Booking status breakdown (doughnut), Examination completion (bar), Examiner workload (grouped bar), and Average results per examination (bar).
- **Examiner (`/examiner/charts` & dashboard widget):** Students evaluated per examination (bar), Upcoming slot participants (stacked bar), Bookings over time (line), and Average result per examination (bar).
- **Student (`/student/charts` & dashboard widget):** Booking history (doughnut), Booking trend (line), and Examination results (bar).

### Adding a New Chart
1. **Service:** Add a role-scoped function in `app/services/chart_data.py` returning `{"labels": [...], "series": [{"name": ..., "data": [...]}]}`.
2. **Endpoint:** Expose a GET route in `app/blueprints/api_v1/charts.py` and document it in `API_REFERENCE` (`app/blueprints/api_v1/docs.py`).
3. **Template:** Use `{{ chart_card(...) }}` from `app/templates/charts/_macros.html` and include `charts/_scripts.html` in `block scripts`.

---

## 4. Dual-Layer Validation (Milestone P9)

EMP implements a strict dual-layer validation architecture where frontend JavaScript (`app/static/js/validation.js`) and backend WTForms / API schemas share the exact same limits and message catalogue:

- **Shared Limits:** `app/validation/limits.py`
- **Shared Messages:** `app/validation/messages.py`
- **Custom Validators:** `app/validation/validators.py` (`SafeText`, `StrongPassword`, `PhoneChars`, `CourseCodeChars`, `RollNumber`, `DecimalPlaces`, `DateTimeLocal`, `EndAfterStart`, `ExaminationWindows`, `ScoreRange`)

### New Rules in P9
1. **Password Length Limit:** `PASSWORD_MAX = 128` (denial-of-service protection against bcrypt/hash amplification).
2. **Control Character Rejection:** `SafeText` rejects ASCII/Unicode control characters in all free-text fields.
3. **Automatic Whitespace Trimming:** Free-text inputs are stripped of leading/trailing whitespace before validation.

---

## 5. Responsive Layout and Accessibility (Milestone P10)

EMP provides WCAG 2.1 AA accessible design and fully responsive mobile-first layouts across viewports:

- **Breakpoints (Bootstrap 5 Grid):**
  - `<576px (xs)`: Single column, hamburger / offcanvas navigation drawer, stacked card tables (`table-stack`), full-width action buttons (`btn-xs-block`).
  - `576px – 767px (sm)`: Single column with larger touch targets (>=44px), two-column card grid.
  - `768px – 991px (md)`: Two-column layouts, horizontal table scroll wrappers (`table-responsive`), collapsible navigation drawer.
  - `992px – 1199px (lg)`: Static 240px sidebar for Admin, full horizontal navbar for Examiner/Student.
  - `>=1200px (xl)`: Content capped inside `.page-container` (max-width 1200px, centered).

### How to Add a Data Table with `table-stack`
Wrap your table in `.table-responsive` and apply the accessible ARIA stack classes:
```html
<div class="table-responsive">
  <table class="table table-hover align-middle table-stack" role="table">
    <caption class="visually-hidden">Human-readable description</caption>
    <thead role="rowgroup">
      <tr role="row">
        <th scope="col" role="columnheader">Field Name</th>
        <th scope="col" role="columnheader">Actions</th>
      </tr>
    </thead>
    <tbody role="rowgroup">
      <tr role="row">
        <td role="cell" data-label="Field Name">Value</td>
        <td role="cell" data-label="Actions" class="td-actions">...</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Running the Accessibility Audit
Audit all role pages and viewports offline:
```bash
# Run automated static WCAG 2.1 AA & responsive checks
make a11y

# Or run via pytest marker
make test-ui
```
For detailed audit criteria and WCAG checklists, see [accessibility_responsive_checklist.md](docs/accessibility_responsive_checklist.md).

