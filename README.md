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