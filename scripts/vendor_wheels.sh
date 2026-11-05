#!/usr/bin/env bash
set -euo pipefail 

cd "$(dirname "$0")/.."

echo "======================================================================"
echo "LMS Offline Wheel Caching Utility"
echo "======================================================================"

if ! command -v pip >/dev/null 2>&1 && ! command -v pip3 >/dev/null 2>&1; then
    echo "ERROR: pip is not installed or not in PATH." >&2
    exit 1
fi

PIP_CMD="pip"
if ! command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip3"
fi

mkdir -p wheels

echo "Scanning for requirements files..."
DOWNLOAD_COUNT=0
for req_file in requirements*.txt; do
    if [ -f "$req_file" ]; then
        echo "--> Downloading wheels for: $req_file"
        $PIP_CMD download --dest wheels/ -r "$req_file"
        DOWNLOAD_COUNT=$((DOWNLOAD_COUNT + 1))
    fi
done

if [ "$DOWNLOAD_COUNT" -eq 0 ]; then
    echo "WARNING: No requirements*.txt files found."
else
    WHEEL_COUNT=$(find wheels -type f \( -name "*.whl" -o -name "*.tar.gz" \) | wc -l)
    TOTAL_SIZE=$(du -sh wheels | cut -f1)
    echo "======================================================================"
    echo "SUCCESS: Cached $WHEEL_COUNT package archive(s) in wheels/ (Total size: $TOTAL_SIZE)."
    echo "Note: The wheels/ folder is excluded from git via .gitignore."
    echo "======================================================================"
fi



# DEBUGGING:
# echo "[DEBUG] downloading from: $f" for each requirements file
# OFFLINE DOCKER TEST CASES:
# - After one online run, docker build --network none --target runtime . succeeds.
# - Running the script twice is harmless (idempotent).
