#!/usr/bin/env bash
# FILE PURPOSE: Gate B verification script (Master Blueprint 2.3).
set -uo pipefail

TAG_FLAG=""
ALLOW_PENDING_VIDEO=0
FAILURES=0

for arg in "$@"; do
    case "$arg" in
        --tag)
            TAG_FLAG="--tag"
            ;;
        --allow-pending-video)
            ALLOW_PENDING_VIDEO=1
            ;;
    esac
done

check() {
    local name="$1"
    shift
    if "$@" >/tmp/gate_b_out.log 2>&1; then
        echo "[PASS] ${name}"
    else
        echo "[FAIL] ${name}"
        tail -n 15 /tmp/gate_b_out.log | sed 's/^/       /'
        FAILURES=$((FAILURES + 1))
    fi
}

warn_check() {
    local name="$1"
    shift
    if "$@" >/tmp/gate_b_out.log 2>&1; then
        echo "[PASS] ${name}"
    else
        if [ "$ALLOW_PENDING_VIDEO" -eq 1 ]; then
            echo "[WARN] ${name} (pending video allowed)"
        else
            echo "[FAIL] ${name}"
            tail -n 15 /tmp/gate_b_out.log | sed 's/^/       /'
            FAILURES=$((FAILURES + 1))
        fi
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
    echo "ERROR: Gate B must run on branch 'main' (currently on '${CURRENT_BRANCH}')."
    exit 2
fi

# Check 1: Gate A holds
verify_gate_a() {
    git rev-parse -q --verify "refs/tags/tier1-complete" >/dev/null || return 1
    bash scripts/verify_gate_a.sh
}
check "Check 1: Gate A still holds (tier1-complete exists and passes)" verify_gate_a

# Check 2: Tags p7-done to p12-done and squash commit messages
verify_tier2_tags_and_commits() {
    for n in 7 8 9 10 11 12; do
        git rev-parse -q --verify "refs/tags/p${n}-done" >/dev/null || return 1
    done

    local msgs=(
        "Milestone-7 EMP-API-Integration"
        "Milestone-8 EMP-Charts-Visualization"
        "Milestone-9 EMP-Validation"
        "Milestone-10 EMP-Responsive-UI"
        "Milestone-11 EMP-Flask-Login-Security"
        "Milestone-12 EMP-Scorecard-Email"
    )
    for m in "${msgs[@]}"; do
        local count
        count=$(git log --grep="^${m}" --oneline | wc -l)
        if [ "$count" -ne 1 ]; then
            echo "Expected commit '${m}' exactly once, found ${count}"
            return 1
        fi
    done
}
check "Check 2: Tags p7-done through p12-done and unique milestone commit messages" verify_tier2_tags_and_commits

# Check 3: scripts/check_gate.sh passes
if [ -x scripts/check_gate.sh ]; then
    check "Check 3: scripts/check_gate.sh passes" bash scripts/check_gate.sh
fi

# Check 4: make test-core
check "Check 4: Core test suite (make test-core)" make test-core

# Check 5: Individual markers
verify_markers() {
    local markers=(api charts validation responsive a11y security mail scorecard concurrency)
    for mk in "${markers[@]}"; do
        local out
        out=$(pytest -m "$mk" -q --collect-only 2>&1)
        if echo "$out" | grep -q "collected 0 items"; then
            echo "Marker $mk has 0 items"
            return 1
        fi
        pytest -m "$mk" -q || return 1
    done
}
check "Check 5: Individual markers pass (api, charts, validation, responsive, a11y, security, mail, scorecard, concurrency)" verify_markers

# Check 6: Coverage >= 80%
check "Check 6: Branch coverage >= 80%" pytest --cov=app --cov-branch --cov-fail-under=80 -q

# Check 7: Security and accessibility
verify_sec_a11y() {
    make security && make a11y
}
check "Check 7: Security (ruff/bandit) and accessibility audits pass" verify_sec_a11y

# Check 8: API drift-guard and traceability verified
verify_traceability_tier2() {
    if [ ! -f docs/tier2_traceability.md ]; then return 1; fi
    local unverified
    unverified=$(grep "^| T2-" docs/tier2_traceability.md | grep -v "| yes |" || true)
    if [ -n "$unverified" ]; then
        echo "Unverified rows in tier2_traceability.md:"
        echo "$unverified"
        return 1
    fi
}
check "Check 8: Tier 2 traceability matrix marked verified" verify_traceability_tier2

# Check 9: Submission package and report files
verify_submission_and_report() {
    bash scripts/build_submission.sh HEAD || return 1

    [ -f docs/report/report_draft.md ] || return 1
    local req_headings=(
        "Student details"
        "Project details and approach"
        "AI/LLM declaration"
        "Frameworks and libraries"
        "ER diagram"
        "API endpoints"
        "Video link"
    )
    for h in "${req_headings[@]}"; do
        grep -q "## ${h}" docs/report/report_draft.md || { echo "Missing heading: $h"; return 1; }
    done

    # Check ai_llm_declaration has no empty cells for P0 to P12
    for p in P0 P1 P2 P3 P4 P5 P6 P7 P8 P9 P10 P11 P12; do
        grep -E "\|\s*\*\*${p}\*\*\s*\|" docs/ai_llm_declaration.md | grep -qv "|\s*|" || { echo "Empty cell in $p declaration"; return 1; }
    done
}
check "Check 9: Submission package build and report headings" verify_submission_and_report

# Video link check
verify_video_link() {
    [ -f docs/report/video_link.txt ] || return 1
    grep -E "^https://" docs/report/video_link.txt >/dev/null || return 1
}
warn_check "Check 9b: docs/report/video_link.txt contains an https URL" verify_video_link

# Check 10: .env.example safe and no requirements-tier3.txt
verify_env_and_tier3() {
    ! grep -E "^ENABLE_.*=true" .env.example || return 1
    ! grep -i "RAZORPAY" .env.example || return 1
    [ ! -f requirements-tier3.txt ] || return 1
}
check "Check 10: .env.example safe defaults and no requirements-tier3.txt" verify_env_and_tier3

echo "-----------------------------------------------------"
if [ "$FAILURES" -eq 0 ]; then
    echo "GATE B PASSED"
    if [ "$TAG_FLAG" = "--tag" ]; then
        if ! git rev-parse -q --verify "refs/tags/tier2-complete" >/dev/null; then
            git tag -a tier2-complete -m "Gate B passed"
            echo "Created tag tier2-complete. Push with: git push origin tier2-complete"
        else
            echo "Tag tier2-complete already exists."
        fi
    else
        echo "Hint: Run 'bash scripts/verify_gate_b.sh --tag' to create tier2-complete."
        echo "Reminder: Tier 3 branches may only be created from this tag (make tier3-branch)."
    fi
    exit 0
else
    echo "GATE B FAILED (${FAILURES} checks)"
    exit 1
fi
