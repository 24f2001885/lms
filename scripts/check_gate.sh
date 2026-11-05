#!/usr/bin/env bash
set -euo pipefail

TARGET_BRANCH="${1:-}"
ERRORS=0

echo "======================================================================"
echo "LMS Gate Verification Audit"
echo "======================================================================"

#check for git tag existnce 
tag_exists() {
    git rev-parse -q --verify "refs/tags/$1" >/dev/null 2>&1
}

#create branch 
if [ -n "$TARGET_BRANCH" ]; then
    echo "[CHECK] Validating branch creation target: '$TARGET_BRANCH'..."

    # Branch names starting with tier3/ require tag 'tier2-complete' (Gate B)
    if [[ "$TARGET_BRANCH" =~ ^tier3/ ]]; then
        if ! tag_exists "tier2-complete"; then
            echo " [FAIL] GATE B CLOSED: Tag 'tier2-complete' not found." >&2
            echo "        Complete and tag Tier 1 and Tier 2 before starting Tier 3." >&2
            exit 1
        fi
        echo " [PASS] Gate B open. Branch '$TARGET_BRANCH' allowed."
        exit 0
    fi

    # Branch names for Tier 2 (p7 to p12) require tag 'tier1-complete' (Gate A)
    if [[ "$TARGET_BRANCH" =~ ^phase/p(7|8|9|10|11|12)- ]]; then
        if ! tag_exists "tier1-complete"; then
            echo " [FAIL] GATE A CLOSED: Tag 'tier1-complete' not found." >&2
            echo "        Complete and tag Tier 1 (P0-P6) before starting Tier 2." >&2
            exit 1
        fi
        echo " [PASS] Gate A open. Branch '$TARGET_BRANCH' allowed."
        exit 0
    fi

    echo " [PASS] Branch '$TARGET_BRANCH' is Tier 1 (always allowed)."
    exit 0
fi

#teir 3 repo isolation 
if ! tag_exists "tier2-complete"; then
    echo "[AUDIT] Checking Tier 3 premature artifacts (Gate B closed)..."
    TIER3_PATHS=(
        "app/blueprints/tier3"
        "app/models/tier3"
        "app/services/tier3"
        "app/templates/tier3"
        "app/static/js/tier3"
        "tests/tier3"
        "requirements-tier3.txt"
    )
    for p in "${TIER3_PATHS[@]}"; do
        if [ -e "$p" ] && [ -n "$(ls -A "$p" 2>/dev/null)" ]; then
            echo " [FAIL] Tier 3 file/folder exists before Gate B: $p"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi

#tier 2 repo isolation 
if ! tag_exists "tier1-complete"; then
    echo "[AUDIT] Checking Tier 2 premature artifacts (Gate A closed)..."
    TIER2_PATHS=(
        "app/blueprints/api_v1"
        "app/models/email_log.py"
        "app/services/mailer.py"
        "requirements-tier2.txt"
    )
    for p in "${TIER2_PATHS[@]}"; do
        if [ -e "$p" ]; then
            echo " [FAIL] Tier 2 file exists before Gate A: $p"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi

#secret key leak check 
echo "[AUDIT] Auditing secret and credential hygiene..."

# 4a. .env must never be tracked by git
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo " [FAIL] Security violation: .env is tracked in git index!"
    ERRORS=$((ERRORS + 1))
fi

# 4b. No live Razorpay keys or secrets in committed code
if git grep -EIq "rzp_live_[a-zA-Z0-9]+" 2>/dev/null; then
    echo " [FAIL] Security violation: Live Razorpay key detected in tracked files!"
    ERRORS=$((ERRORS + 1))
fi

# 4c. Feature flags in .env.example must never be 'true' by default
if [ -f .env.example ] && grep -Ei "^ENABLE_.*=true" .env.example >/dev/null 2>&1; then
    echo " [FAIL] Gate violation: Feature flag enabled in .env.example (must be false by default)!"
    ERRORS=$((ERRORS + 1))
fi

if [ "$ERRORS" -gt 0 ]; then
    echo "GATE CHECK FAILED: $ERRORS violation(s) detected."
    exit 1
else
    echo "GATE CHECK PASSED: All repository isolation checks satisfied."
    exit 0
fi
# DEBUGGING:
# echo "[DEBUG] rule=${RULE} result=${RESULT}" >&2    (print every rule outcome when GATE_DEBUG=1)
# OFFLINE DOCKER TEST CASES:
# - Fresh P0 repo: scripts/check_gate.sh exits 0.
# - scripts/check_gate.sh tier3/p13-x exits 1 while tag tier2-complete is missing.
# - After creating the app/blueprints/tier3 folder with no tier2-complete tag, the audit exits 1.
# - After git tag tier2-complete, scripts/check_gate.sh tier3/p13-x exits 0 when run from the tagged commit.
