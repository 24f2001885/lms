#!/usr/bin/env bash
# =====================================================================
# P0.sh - Milestone M0: GitHub Repository Setup (Tier 1, Primary)
# Course commit message : Milestone-0 EMP-MAD-1   (fixed by the course)
# Branch                : phase/p0-repo-setup      (Master Blueprint 2.1)
# Depends on            : nothing
# Run from              : the folder that will become the repo root (e.g. emp/)
# This script contains NO application logic. It creates folders and
# writes prompt-only seed files. The only non-prompt file is .gitignore,
# because it is git setup (it keeps .env, instance/ and logs/ out of Git).
# =====================================================================
set -euo pipefail

PHASE="P0"
BRANCH="phase/p0-repo-setup"

# ---------------------------------------------------------------------
# 1. Git branch management
# ---------------------------------------------------------------------
echo "Initialising git (if needed)..."
if [ ! -d .git ]; then
  git init
fi

echo "Checking out milestone branch..."
# On a brand-new repo (no commits yet) this renames the unborn branch, which is fine.
git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"

# ---------------------------------------------------------------------
# 2. Directory & Docker setup
#    Tier 1 skeleton only. Tier 2 folders (api_v1, emails, chartjs, ...) are
#    created in P7+ and Tier 3 folders after Gate B. Do NOT add them here.
# ---------------------------------------------------------------------
echo "Creating Tier 1 directory skeleton..."
mkdir -p app/models
mkdir -p app/blueprints/auth app/blueprints/admin app/blueprints/examiner app/blueprints/student
mkdir -p app/services app/forms app/security
mkdir -p app/templates/macros app/templates/errors app/templates/auth
mkdir -p app/templates/admin app/templates/examiner app/templates/student
mkdir -p app/static/vendor/bootstrap app/static/vendor/bootstrap-icons app/static/css app/static/js
mkdir -p instance logs wheels migrations
mkdir -p scripts
mkdir -p tests/unit tests/integration tests/e2e
mkdir -p docs/report docs/seed_updates
mkdir -p .github/workflows

# ---------------------------------------------------------------------
# 3. File seeding
# ---------------------------------------------------------------------

# --- .gitignore (REAL content: this is git setup, not application code) ---
cat << 'EOF' > .gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Secrets and local state (never commit)
.env
instance/*
!instance/.gitkeep
logs/*
!logs/.gitkeep
*.db
*.sqlite3

# Offline wheel cache for Docker builds (large; regenerate with scripts/vendor_wheels.sh)
wheels/*
!wheels/.gitkeep

# Test artefacts
playwright-report/
test-results/
.playwright/

# Editors and OS
.vscode/
.idea/
.DS_Store
Thumbs.db
EOF

# --- README.md ---
cat << 'EOF' > README.md
<!--
FILE PURPOSE: Project front page for the EMP repository (course graders and teammates read this first).
PROMPT FOR LLM IMPLEMENTATION:
1. Title "Examination Management Portal (EMP)" with a one-paragraph summary: role-based web app for Admin, Examiner and Student to schedule, book and evaluate viva, practical and project-demo examinations (Flask, Jinja2, Bootstrap 5, SQLite).
2. Section "Delivery tiers": a 3-row table (Tier 1 Primary = phases P0-P6 mandatory; Tier 2 Secondary = P7-P12 optional; Tier 3 Tertiary = P13-P17 extras: online tests, anti-cheat, Razorpay). State plainly that nothing in Tier 3 is started until tags tier1-complete and tier2-complete exist, and that Tier 3 is behind feature flags that are OFF by default.
3. Section "Quick start" with numbered commands taken verbatim from TDR section 13: create venv, pip install -r requirements.txt, copy .env.example to .env and edit SECRET_KEY and ADMIN_* values, create the database with the flask init-db command (app factory, FLASK_APP=app), run the dev server on http://127.0.0.1:5000. Add a Windows activation line.
4. Section "Running tests": make test-core for Tier 1/2 (unit, integration, e2e), and the Docker equivalent using the test compose profile with no network. Mention that Playwright browsers must be installed once while online.
5. Section "Docker (optional)": docker compose up --build, where the SQLite file lives (instance/ bind mount), and the offline wheel workflow using scripts/vendor_wheels.sh.
6. Section "Git workflow": branch names phase/pN-slug, wip: commits, one squashed commit per phase, the table of unique commit messages P0-P6 exactly as in Master Blueprint section 3.1 (P0 = Milestone-0 EMP-MAD-1), tags pN-done, tier1-complete, tier2-complete, and the collaborator MADI-cs2003 requirement.
7. Section "Project layout": a short annotated tree of the Tier 1 folders created in P0 (app/, tests/, scripts/, docs/, instance/, logs/).
8. Section "Known issues and resolutions": an empty 4-column table (Date, Phase, Issue, Resolution) that every later phase must append to (Definition of Done in Master Blueprint 2.6).
9. Section "AI/LLM usage": link to docs/ai_llm_declaration.md and one sentence that every file must be understood by the team before the viva.
10. Section "Seeded-prompt convention": explain that seed files contain PROMPT / DEBUGGING / OFFLINE DOCKER TEST CASES docstrings and that docs/seed_updates/ holds update prompts for files that already contain real code.
11. Keep the whole file under 150 lines; plain Markdown only, no images, no badges.
DEBUGGING:
(none: documentation file) Verify with: grep -c "^## " README.md  (expect at least 9 sections)
OFFLINE DOCKER TEST CASES:
- Every command shown in "Quick start" runs unchanged on a clean machine after P1 is merged.
- The commit-message table matches docs/Master_Blueprint.md character for character.
-->
EOF

# --- requirements.txt ---
cat << 'EOF' > requirements.txt
# FILE PURPOSE: Tier 1 runtime dependencies only (Tier 2 goes to requirements-tier2.txt in P7, Tier 3 to requirements-tier3.txt after Gate B).
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Pin EXACT versions (==) of the latest stable releases that support Python 3.11 and 3.12, for reproducible offline builds.
# 2. Include exactly these packages, one per line, alphabetical, no extras: Flask (3.x), Flask-SQLAlchemy (3.x, on SQLAlchemy 2.x), SQLAlchemy (2.x), Flask-WTF, WTForms, email-validator (needed by the WTForms Email validator), Werkzeug (3.x, password hashing with scrypt default), python-dotenv.
# 3. Do NOT add Flask-Login, Flask-Mail, Flask-RESTful, ReportLab, razorpay, gunicorn or anything Tier 2 / Tier 3. Do NOT add any CSS or JS packages.
# 4. First line of real content must be a comment with the Python versions supported, e.g. "# Python 3.11+ (3.12 recommended)".
# DEBUGGING:
# python -m pip check   (expect "No broken requirements found.")
# OFFLINE DOCKER TEST CASES:
# - pip install --no-index --find-links=wheels/ -r requirements.txt succeeds after scripts/vendor_wheels.sh has run once.
# - python -c "import flask, flask_sqlalchemy, flask_wtf, dotenv, email_validator" exits 0 inside the container.
EOF

# --- requirements-dev.txt ---
cat << 'EOF' > requirements-dev.txt
# FILE PURPOSE: Developer and test tooling (not needed to simply run the app).
# PROMPT FOR LLM IMPLEMENTATION:
# 1. First line must be "-r requirements.txt" so one install covers everything.
# 2. Pin exact versions of: pytest, pytest-cov, ruff, black, playwright (Python package for e2e tests), aiosmtpd (local mail sink, used from P12).
# 3. Add a comment above playwright: "run 'playwright install chromium' once while online; tests then run offline".
# 4. No Tier 3 tooling.
# DEBUGGING:
# pytest --version && ruff --version && black --version
# OFFLINE DOCKER TEST CASES:
# - docker compose --profile test run --rm test pytest --version prints a version with the network disabled.
EOF

# --- .env.example ---
cat << 'EOF' > .env.example
# FILE PURPOSE: Template for the local .env file. Placeholders only, never real secrets. .env itself is git-ignored.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Include ONLY the "Core (T1)" variables from TDR section 16: FLASK_APP=app, FLASK_ENV=development, SECRET_KEY, DATABASE_URL, APP_TIMEZONE=Asia/Kolkata, ADMIN_EMAIL, ADMIN_FULL_NAME, ADMIN_INITIAL_PASSWORD, SESSION_COOKIE_SECURE=false, PERMANENT_SESSION_LIFETIME_MINUTES=30, LOG_LEVEL=INFO, LOG_FILE=logs/emp.log.
# 2. Every secret value must be an obvious placeholder such as change-me-to-a-long-random-string; add a comment line showing how to generate one: python -c "import secrets; print(secrets.token_hex(32))".
# 3. Set DATABASE_URL to sqlite:///instance/emp.db and add a comment that a relative path is resolved against the PROJECT ROOT by app/config.py (decided in P1 to avoid the instance/instance/ double-folder trap of Flask-SQLAlchemy 3).
# 4. Add one comment per variable saying what it does and which phase first uses it.
# 5. Do NOT include MAIL_*, LOGIN_RATE_LIMIT_*, ENABLE_*, PROCTORING_*, RAZORPAY_* or SEAT_HOLD_* (Tier 2 adds MAIL_* in P12; Tier 3 flags and keys arrive in P13/P16). Gate B requires that no ENABLE_* flag is ever true in this file.
# DEBUGGING:
# grep -E "ENABLE_|RAZORPAY|MAIL_" .env.example   (expect no output in P0)
# OFFLINE DOCKER TEST CASES:
# - cp .env.example .env then flask init-db (after P1) starts without a missing-variable error.
# - No line contains a real-looking key (scripts/check_gate.sh greps for rzp_live and long hex strings).
EOF

# --- pyproject.toml ---
cat << 'EOF' > pyproject.toml
# FILE PURPOSE: One place for ruff, black and pytest configuration.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. [tool.black]: line-length = 100, target-version = ["py311"].
# 2. [tool.ruff]: line-length = 100, target-version = "py311"; [tool.ruff.lint] select = ["E","F","I","N","B","UP"]; exclude migrations, .venv, wheels, instance, logs. Per-file ignore for tests: allow long lines and assert statements.
# 3. [tool.pytest.ini_options]: testpaths = ["tests"], pythonpath = ["."] (so "import app" works without installing), addopts = "-ra -q", and markers: e2e (needs Playwright), tier3 (only exists after Gate B), slow.
# 4. [tool.coverage.run] source = ["app"], omit tests; [tool.coverage.report] show_missing = true, fail_under = 0 for now (raised to 80 in P6).
# 5. No [project] / packaging section is needed; this is an application, not a library.
# DEBUGGING:
# ruff check . --show-settings | head   and   pytest --collect-only -q
# OFFLINE DOCKER TEST CASES:
# - black --check . and ruff check . both pass on the P0 files.
# - pytest --collect-only finds tests/unit/test_smoke_app.py without import errors.
EOF

# --- Dockerfile ---
cat << 'EOF' > Dockerfile
# FILE PURPOSE: One image definition with a "runtime" target (run the app) and a "test" target (run pytest and Playwright offline).
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Base image python:3.12-slim. Set PYTHONDONTWRITEBYTECODE=1, PYTHONUNBUFFERED=1, PIP_DISABLE_PIP_VERSION_CHECK=1. WORKDIR /app.
# 2. Stage "base": create a non-root user "emp" (uid 1000), COPY requirements.txt and the wheels/ folder (wheels/.gitkeep guarantees it exists), then install dependencies: if wheels/ contains any .whl file use "pip install --no-index --find-links=wheels/ -r requirements.txt", otherwise plain "pip install -r requirements.txt".
# 3. Stage "runtime" (FROM base): COPY the project, make instance/ and logs/ owned by emp, USER emp, EXPOSE 5000, CMD runs the Flask dev server on 0.0.0.0:5000 using the app factory (flask --app app run --host 0.0.0.0 --port 5000). gunicorn is NOT needed.
# 4. Stage "test" (FROM base, as root for installs, then back to emp): install requirements-dev.txt (same offline-wheel rule), run "playwright install --with-deps chromium" (needs internet ONCE at build time; add a comment saying so), COPY the project, default CMD "make test-core".
# 5. Keep layers cache-friendly: copy dependency files before source code. No secrets, no .env copied into the image (it is injected by compose).
# 6. Add a HEALTHCHECK on the runtime stage that requests http://127.0.0.1:5000/ with python -c and urllib (no curl dependency).
# DEBUGGING:
# RUN echo "[DEBUG] pip freeze (first 20):" && pip freeze | head -20     (keep as a commented line, enable when debugging builds)
# OFFLINE DOCKER TEST CASES:
# - docker build --target runtime . succeeds with the network disabled after wheels were vendored.
# - docker run --rm <image> id -u prints 1000 (non-root).
# - docker build --target test . then docker run --network none <image> python -c "import app" exits 0.
EOF

# --- docker-compose.yml ---
cat << 'EOF' > docker-compose.yml
# FILE PURPOSE: Run the app locally (service "app") and run tests fully offline (service "test", profile "test").
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Service "app": build context ".", target runtime, ports "5000:5000", env_file .env, volumes ./instance:/app/instance and ./logs:/app/logs, restart "unless-stopped". Command inherits the Dockerfile CMD.
# 2. Service "test": profiles ["test"], build target test, network_mode "none", tmpfs mount for /tmp/emp-test (the throw-away SQLite file lives here), environment: FLASK_ENV=testing, DATABASE_URL=sqlite:////tmp/emp-test/test.db, SECRET_KEY=test-secret, MAIL_SUPPRESS_SEND is NOT set yet (Tier 2). Command: make test-core.
# 3. Do NOT add RAZORPAY_* or ENABLE_* variables or any second container; SQLite is a file so one image is enough. Tier 3 environment entries are added in P16/P17.
# 4. Use Compose v2 syntax (no "version:" key). Add a header comment with the three commands: docker compose up --build, docker compose --profile test run --rm test, docker compose down.
# DEBUGGING:
# docker compose config   (prints the resolved file; run it after every edit)
# OFFLINE DOCKER TEST CASES:
# - docker compose config exits 0.
# - docker compose --profile test run --rm test cannot reach the internet (python -c "import urllib.request as u; u.urlopen('http://example.com', timeout=2)" must fail).
EOF

# --- .dockerignore ---
cat << 'EOF' > .dockerignore
# FILE PURPOSE: Keep the Docker build context small and free of secrets.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Exclude: .git, .github, .venv, venv, __pycache__, *.pyc, .pytest_cache, .ruff_cache, .env (but NOT .env.example), instance/*, logs/*, *.db, docs/report, playwright-report, test-results, .vscode, .idea.
# 2. Do NOT exclude wheels/ (the offline build needs it), requirements*.txt, app/, tests/, scripts/, Makefile or pyproject.toml.
# DEBUGGING:
# docker build --no-cache --progress=plain .   (check "transferring context" size is small)
# OFFLINE DOCKER TEST CASES:
# - A container started from the image has no /app/.env and no /app/.git folder.
EOF

# --- Makefile ---
cat << 'EOF' > Makefile
# FILE PURPOSE: Single entry point for every repeated command (local and Docker).
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Declare .PHONY targets and a self-documenting "help" target (default goal) that lists all targets with one-line descriptions.
# 2. Targets: run (flask dev server with debug), init-db (flask init-db, available after P1), lint (ruff check . then black --check .), format (ruff --fix then black .), test-unit, test-integration, test-e2e, test-core (unit + integration + e2e for Tier 1 and Tier 2, exit non-zero on first failure), test (alias of test-core), coverage.
# 3. test-tier3: if tests/tier3 does not exist print "Tier 3 not started (see Gate B)" and exit 0; otherwise run pytest tests/tier3 AFTER test-core.
# 4. tier3-branch: usage "make tier3-branch NAME=p13-test-foundation" - runs scripts/check_gate.sh tier3/$(NAME) and, only if it passes, creates branch tier3/$(NAME) from tag tier2-complete.
# 5. gate-check: runs scripts/check_gate.sh with no arguments (repository-wide guard, also used by CI).
# 6. docker-up (docker compose up --build), docker-test (docker compose --profile test run --rm test), docker-down, vendor-wheels (scripts/vendor_wheels.sh), clean (remove caches and __pycache__, never touch instance/ or .env).
# 7. Use $(PYTHON) variable defaulting to python; recipe lines must be tab-indented; silence echo with @ only for help output.
# DEBUGGING:
# make -n test-core   (dry run prints commands without executing)
# OFFLINE DOCKER TEST CASES:
# - make help lists every target.
# - make lint passes on a clean checkout of P0.
# - make test-tier3 exits 0 and prints the "Tier 3 not started" notice.
EOF

# --- scripts/check_gate.sh ---
cat << 'EOF' > scripts/check_gate.sh
#!/usr/bin/env bash
# FILE PURPOSE: Enforce the tier gates from Master Blueprint 2.3 (Tier 3 cannot start before Gate B; Tier 2 cannot start before Gate A).
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Bash with "set -euo pipefail". Usage: scripts/check_gate.sh [branch-name]. No argument = repository-wide audit; with an argument = check whether that branch may be created.
# 2. Helper "tag_exists NAME" using: git rev-parse -q --verify refs/tags/NAME.
# 3. Branch rule A: branch names starting "tier3/" require tag tier2-complete AND that HEAD is a descendant of that tag (git merge-base --is-ancestor). Otherwise print "GATE B CLOSED: finish and tag Tier 1 + Tier 2 first" to stderr and exit 1.
# 4. Branch rule B: branch names matching phase/p7-* through phase/p12-* require tag tier1-complete; otherwise print "GATE A CLOSED" and exit 1. Names matching phase/p0-* to phase/p6-* are always allowed.
# 5. Repository audit (no argument): if tag tier2-complete is missing, fail (exit 1) when ANY of these exist: app/blueprints/tier3, app/models/tier3, app/services/tier3, app/templates/tier3, app/static/js/tier3, tests/tier3, requirements-tier3.txt. If tag tier1-complete is missing, fail when any Tier 2 artefact exists: app/blueprints/api_v1, app/models/email_log.py, app/services/mailer.py, requirements-tier2.txt.
# 6. Secret hygiene: fail if .env is tracked (git ls-files --error-unmatch .env succeeds) or if any tracked file matches rzp_live_ or a RAZORPAY_KEY_SECRET= line with a non-placeholder value.
# 7. Flag hygiene: fail if .env.example contains a line matching ^ENABLE_.*=true (case-insensitive).
# 8. Print a coloured-free, one-line PASS/FAIL per rule, then a final "GATE CHECK PASSED" or "GATE CHECK FAILED (n problems)". Exit codes: 0 ok, 1 gate violation, 2 usage error.
# DEBUGGING:
# echo "[DEBUG] rule=${RULE} result=${RESULT}" >&2    (print every rule outcome when GATE_DEBUG=1)
# OFFLINE DOCKER TEST CASES:
# - Fresh P0 repo: scripts/check_gate.sh exits 0.
# - scripts/check_gate.sh tier3/p13-x exits 1 while tag tier2-complete is missing.
# - After creating the app/blueprints/tier3 folder with no tier2-complete tag, the audit exits 1.
# - After git tag tier2-complete, scripts/check_gate.sh tier3/p13-x exits 0 when run from the tagged commit.
EOF

# --- scripts/vendor_wheels.sh ---
cat << 'EOF' > scripts/vendor_wheels.sh
#!/usr/bin/env bash
# FILE PURPOSE: Download every Python wheel once (while online) so Docker builds and tests work offline.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Bash with "set -euo pipefail"; cd to the repo root (directory of this script, one level up).
# 2. Create wheels/ if missing and run: pip download -r requirements.txt -r requirements-dev.txt -d wheels/ for every requirements*.txt that currently exists (loop over the files so Tier 2 and Tier 3 files are picked up automatically when they appear).
# 3. Print how many .whl / .tar.gz files are in wheels/ and the folder size; remind the user that wheels/ is git-ignored.
# 4. Exit with a clear message if pip is not available. Never delete existing wheels.
# DEBUGGING:
# echo "[DEBUG] downloading from: $f" for each requirements file
# OFFLINE DOCKER TEST CASES:
# - After one online run, docker build --network none --target runtime . succeeds.
# - Running the script twice is harmless (idempotent).
EOF

# --- .github/workflows/ci.yml ---
cat << 'EOF' > .github/workflows/ci.yml
# FILE PURPOSE: GitHub Actions pipeline that mirrors the local make targets.
# PROMPT FOR LLM IMPLEMENTATION:
# 1. Trigger on push and pull_request for all branches. Use ubuntu-latest and Python 3.12 (actions/setup-python with pip cache).
# 2. Job "gate": checkout with fetch-depth 0 and fetch-tags true, then run scripts/check_gate.sh (repository-wide audit).
# 3. Job "quality" (needs gate): pip install -r requirements-dev.txt, then make lint.
# 4. Job "core-tests" (needs gate): install deps, install Playwright chromium, create .env from .env.example with a throw-away SECRET_KEY and ADMIN_INITIAL_PASSWORD (inline env), then make test-core.
# 5. Do NOT add a Tier 3 job yet; P13 will add one that runs only when tests/tier3 exists. No deploy step (the course needs none). No secrets are required by this file.
# DEBUGGING:
# - name: Debug environment   run: python --version && pip list | head -30    (keep commented out)
# OFFLINE DOCKER TEST CASES:
# - Validate YAML locally: python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))" exits 0.
# - Every run: line in the workflow also works when typed in the local shell.
EOF

# --- app/__init__.py (placeholder app so flask run works in P0) ---
cat << 'EOF' > app/__init__.py
"""
FILE PURPOSE: Minimal Flask application factory so "flask run" shows a placeholder page at the end of P0. P1 expands this file (see docs/seed_updates/).
DEPENDS ON: requirements.txt (Flask, python-dotenv).
PROMPT FOR LLM IMPLEMENTATION:
1. Define create_app(config_name: str | None = None) -> Flask. For P0 the config_name argument is accepted and ignored.
2. Build the app with Flask(__name__, instance_relative_config=True). Set app.config["SECRET_KEY"] from the environment variable SECRET_KEY, falling back to the literal "dev-only-change-me" (P1 replaces this with proper config classes).
3. Create the instance folder if it does not exist (os.makedirs(app.instance_path, exist_ok=True)) so Docker bind mounts and SQLite work later.
4. Register exactly one route: GET "/" returning a small hard-coded HTML string (status 200, text/html) with an h1 "Examination Management Portal (EMP)" and a paragraph "Placeholder page - Milestone P0. Features arrive in P1 to P6."
5. No database, no blueprints, no templates, no extensions, no CSS framework in this phase.
6. No side effects at import time other than defining create_app; the module must be importable by "flask --app app run" and by pytest.
7. Add type hints and keep the whole file under 40 lines.
DEBUGGING:
# print(f"[DEBUG] create_app called, config_name={config_name!r}, instance_path={app.instance_path}")
OFFLINE DOCKER TEST CASES:
- GET / returns 200 and the body contains "Examination Management Portal".
- Calling create_app() twice returns two different Flask objects (no hidden global state).
- docker compose up --build serves the page on http://127.0.0.1:5000/ and the container health check passes.
"""
EOF

# --- tests/unit/test_smoke_app.py ---
cat << 'EOF' > tests/unit/test_smoke_app.py
"""
FILE PURPOSE: First green test of the project; proves the factory, the test runner and the Docker test profile work.
DEPENDS ON: app/__init__.py, pyproject.toml (pythonpath = ["."]).
PROMPT FOR LLM IMPLEMENTATION:
1. Import create_app from app. Build the Flask app inside each test (no shared fixtures needed yet; tests/conftest.py arrives in P1).
2. Write test_root_returns_placeholder_page: use app.test_client(), GET "/", assert status 200, assert "Examination Management Portal" in response.get_data(as_text=True).
3. Write test_factory_returns_independent_apps: two create_app() calls are different objects and each has a non-empty SECRET_KEY.
4. Write test_unknown_route_is_404: GET "/does-not-exist" returns 404.
5. Each test has a one-line docstring and no print statements (use assert messages instead).
6. P1 will keep this file passing; do not couple it to database code.
DEBUGGING:
# print(f"[DEBUG] status={response.status_code} body_head={response.data[:80]!r}")
OFFLINE DOCKER TEST CASES:
- pytest tests/unit/test_smoke_app.py passes in the venv and in docker compose --profile test run --rm test.
- The three tests above are the whole file (3 passed).
"""
EOF

# --- docs/ai_llm_declaration.md ---
cat << 'EOF' > docs/ai_llm_declaration.md
<!--
FILE PURPOSE: Running log for the mandatory AI/LLM declaration in the final report (PDR risk R-9: viva failure from over-reliance on AI).
PROMPT FOR LLM IMPLEMENTATION:
1. Title "AI / LLM Usage Declaration" and a short intro sentence stating this file is updated at the end of every phase.
2. A table with columns: Phase, Tool and model used, What it was asked to produce (files or prompts), What the team changed or verified by hand, Team member who can explain it in the viva.
3. Pre-fill one row per phase P0-P6 with empty cells except the Phase column, plus a final row "Final report and demo video".
4. Below the table add a checklist titled "Before the viva": every file can be explained by its owner; no secret or key was pasted into any AI tool; seeded prompts are kept under docs/seed_updates/ or in file docstrings.
5. Keep it under 60 lines, plain Markdown.
DEBUGGING:
(none: documentation file) Verify with: grep -c "^|" docs/ai_llm_declaration.md  (table rows present)
OFFLINE DOCKER TEST CASES:
- The table has at least 8 data rows by the end of P6 and no empty "Team member" cell.
-->
EOF

# --- docs/seed_updates/README.md ---
cat << 'EOF' > docs/seed_updates/README.md
<!--
FILE PURPOSE: Explains the "update prompt" convention used when a later phase must change a file that an earlier phase already implemented.
PROMPT FOR LLM IMPLEMENTATION:
1. Explain the rule: seed scripts NEVER overwrite a file that already contains real code. If phase N needs to change a file created in an earlier phase (for example app/__init__.py), the script writes a prompt file docs/seed_updates/PN_<topic>.md instead.
2. Describe the hand-off: give the LLM (a) the update prompt, (b) the CURRENT contents of the target file, and ask it to return the full updated file while keeping all existing behaviour and tests green.
3. List the naming pattern PN_update_<file>.md and tell the team to keep the files after use as an audit trail (they are small).
4. Keep it under 30 lines.
DEBUGGING:
(none: documentation file)
OFFLINE DOCKER TEST CASES:
- After a phase is implemented, every update prompt listed for that phase has been applied (checked by running the phase test suite).
-->
EOF

# --- planning documents (optional convenience copy) ---
[ -f 1_PDR_EMP_v2.md ] && cp 1_PDR_EMP_v2.md docs/PDR.md || true
[ -f 2_TDR_EMP_v2.md ] && cp 2_TDR_EMP_v2.md docs/TDR.md || true
[ -f 3_UIUX_Design_Plan_EMP_v2.md ] && cp 3_UIUX_Design_Plan_EMP_v2.md docs/UIUX_Design_Plan.md || true
[ -f 4_Master_Project_Blueprint_EMP_v2.md ] && cp 4_Master_Project_Blueprint_EMP_v2.md docs/Master_Blueprint.md || true

# --- keep empty folders in Git, make scripts executable ---
find app tests scripts docs instance logs wheels migrations .github -type d -empty -exec touch {}/.gitkeep \;
chmod +x scripts/*.sh

# ---------------------------------------------------------------------
# 4. Phase completion echo
# ---------------------------------------------------------------------
echo "====================================================="
echo "Milestone P0 Seeded Successfully!"
echo "NEXT STEPS:"
echo "1. Provide the seeded files to your LLM to generate the code (give it docs/Master_Blueprint.md section 3.1 P0 row as context)."
echo "2. Run 'docker compose up --build' to test offline (or 'make run' in a venv). Browse http://127.0.0.1:5000/ and run 'make test-core'."
echo "3. Copy the 4 planning files into docs/ as PDR.md, TDR.md, UIUX_Design_Plan.md, Master_Blueprint.md if the script did not find them."
echo "4. Run 'git add . && git commit -m \"Milestone-0 EMP-MAD-1\"'  (P0 is a single commit with the course-mandated message)."
echo "5. New repo (no earlier commits): 'git branch -M main', create the PRIVATE GitHub repo, then 'git remote add origin <url> && git push -u origin main'."
echo "   Repo already had commits on main: 'git checkout main && git merge --squash phase/p0-repo-setup && git commit -m \"Milestone-0 EMP-MAD-1\"'."
echo "6. Add collaborator MADI-cs2003 (GitHub > Settings > Collaborators), then 'git tag p0-done && git push origin p0-done'."
echo "7. Execute P1.sh"
echo "====================================================="
