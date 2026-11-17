#!/usr/bin/env bash
# FILE PURPOSE: Gate A verification script (Master Blueprint 2.3).
set -uo pipefail

TAG_FLAG="${1:-}"
FAILURES=0

check() {
    local name="$1"
    shift
    if "$@" >/tmp/gate_a_out.log 2>&1; then
        echo "[PASS] ${name}"
    else
        echo "[FAIL] ${name}"
        tail -n 15 /tmp/gate_a_out.log | sed 's/^/       /'
        FAILURES=$((FAILURES + 1))
    fi
}

if [ ! -d .git ]; then
    echo "ERROR: Must be run from repository root."
    exit 2
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Working tree is dirty. Commit or stash changes first."
    exit 2
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "ERROR: Gate A must run on branch 'main' (currently on '${CURRENT_BRANCH}')."
    exit 2
fi

# Check 1: Tags p0-done .. p6-done
verify_tags() {
    for n in 0 1 2 3 4 5 6; do
        git rev-parse -q --verify "refs/tags/p${n}-done" >/dev/null || return 1
    done
}
check "Tags p0-done through p6-done exist" verify_tags

# Check 2: Repository audit script
if [ -x scripts/check_gate.sh ]; then
    check "scripts/check_gate.sh passes" bash scripts/check_gate.sh
fi

# Check 3: Core test suite
check "Core test suite (make test-core)" make test-core

# Check 4: Concurrency tests
check "Concurrency suite (pytest -m concurrency)" pytest -m concurrency -q

# Check 5: Branch coverage >= 80%
check "Branch coverage >= 80%" pytest --cov=app --cov-branch --cov-fail-under=80 -q

# Check 6: Programmatic DB creation
verify_db_init() {
    TMP_DIR=$(mktemp -d)
    DATABASE_URL="sqlite:///${TMP_DIR}/check.db" flask --app app init-db
    python3 -c "import sqlite3; c=sqlite3.connect('${TMP_DIR}/check.db'); assert c.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] == 1"
    rm -rf "$TMP_DIR"
}
check "Programmatic SQLite DB & Admin creation" verify_db_init

# Check 7: Traceability verified
verify_traceability() {
    if [ ! -f docs/tier1_traceability.md ]; then return 1; fi
    ! grep "^| T1-" docs/tier1_traceability.md | grep -vq "| yes |"
}
check "Tier 1 traceability matrix marked verified" verify_traceability

# Check 8: .env.example safe defaults
verify_env() {
    ! grep -E "^ENABLE_.*=true" .env.example
}
check ".env.example has all Tier 3 flags disabled" verify_env

echo "-----------------------------------------------------"
if [ "$FAILURES" -eq 0 ]; then
    echo "GATE A PASSED"
    if [ "$TAG_FLAG" = "--tag" ]; then
        if ! git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null; then
            git tag -a tier1-complete -m "Gate A passed"
            echo "Created tag tier1-complete. Push with: git push origin tier1-complete"
        else
            echo "Tag tier1-complete already exists."
        fi
    else
        echo "Hint: Run 'bash scripts/verify_gate_a.sh --tag' to create tier1-complete."
    fi
    exit 0
else
    echo "GATE A FAILED (${FAILURES} checks)"
    exit 1
fi
