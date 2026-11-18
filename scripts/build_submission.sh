#!/usr/bin/env bash
# Builds submission_core.zip (Tier 1 + Tier 2, Tier 3 flags off).
set -euo pipefail

REF=${1:-HEAD}
ALLOW_DIRTY=${ALLOW_DIRTY:-0}

if [ -n "$(git status --porcelain)" ] && [ "$ALLOW_DIRTY" -eq 0 ]; then
    echo "ERROR: Working tree is dirty. Stash/commit changes or set ALLOW_DIRTY=1."
    exit 1
fi

if ! git rev-parse -q --verify "$REF" >/dev/null; then
    echo "ERROR: Ref '$REF' does not exist."
    exit 1
fi

echo "Building submission_core.zip from $REF..."
git archive --format=zip --prefix=emp/ -o submission_core.zip "$REF"

# Post-build checks
echo "Running post-build checks..."
ZIP_CONTENTS=$(unzip -l submission_core.zip)

# Check for required entries
REQUIRED=(
    "emp/README.md"
    "emp/requirements.txt"
    "emp/requirements-tier2.txt"
    "emp/Dockerfile"
    "emp/docker-compose.yml"
    "emp/Makefile"
    "emp/.env.example"
    "emp/app/__init__.py"
    "emp/app/models/user.py"
    "emp/app/services/booking_engine.py"
    "emp/app/blueprints/api_v1/__init__.py"
    "emp/app/services/scorecard.py"
    "emp/tests/"
    "emp/docs/ai_llm_declaration.md"
    "emp/docs/er_diagram.mmd"
    "emp/docs/report/report_draft.md"
)

for req in "${REQUIRED[@]}"; do
    if ! echo "$ZIP_CONTENTS" | grep -q "$req"; then
        echo "FAIL: Required entry missing: $req"
        exit 1
    fi
done

# Check for forbidden entries
FORBIDDEN=(
    "emp/.env$"
    "emp/instance/.*\.db"
    "emp/logs/"
    "tier3"
    "__pycache__"
    "\.pyc$"
    "emp/wheels/.*\.whl"
    "node_modules"
)

for forb in "${FORBIDDEN[@]}"; do
    if echo "$ZIP_CONTENTS" | grep -Eq "$forb"; then
        echo "FAIL: Forbidden entry found matching: $forb"
        exit 1
    fi
done

SIZE_MB=$(du -m submission_core.zip | cut -f1)
if [ "$SIZE_MB" -gt 20 ]; then
    echo "WARN: Zip size is large ($SIZE_MB MB)."
fi

COUNT=$(unzip -Z -1 submission_core.zip | wc -l)
SHA=$(shasum -a 256 submission_core.zip | cut -d' ' -f1)
COMMIT=$(git rev-parse "$REF")

echo "----------------------------------------"
echo "SUBMISSION ZIP OK"
echo "Commit: $COMMIT"
echo "Files:  $COUNT"
echo "Size:   $SIZE_MB MB"
echo "SHA256: $SHA"
exit 0
