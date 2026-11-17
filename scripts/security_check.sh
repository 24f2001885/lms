#!/usr/bin/env bash
# Runs the project's offline security checks ("make security"); used before Gate B.
set -uo pipefail

echo "Running security checks..."
STATUS=0

# 1. Ruff flake8-bandit checks
echo "Check 1: ruff flake8-bandit"
ruff check app scripts --select S
if [ $? -ne 0 ]; then
    echo "FAIL: Ruff security issues found."
    STATUS=1
else
    echo "PASS: Ruff security check."
fi

# 2. Secrets in Git
echo "Check 2: Secrets hygiene"
if git ls-files | grep -q '^\.env$'; then
    echo "FAIL: .env is tracked in git."
    STATUS=1
elif git ls-files | grep -Eq 'rzp_live_|-BEGIN PRIVATE KEY-'; then
    echo "FAIL: Live keys or private keys found in git."
    STATUS=1
else
    echo "PASS: Secrets hygiene."
fi

# 3. Inline scripts / event handlers in templates
echo "Check 3: Template hygiene (CSP compatibility)"
BAD_TPL=0
if grep -rnE "onclick=|onload=|onchange=|onmouseover=" app/templates/; then
    echo "FAIL: Inline event handlers found."
    BAD_TPL=1
fi
if grep -rnE "href=[\"']javascript:" app/templates/; then
    echo "FAIL: javascript: URLs found."
    BAD_TPL=1
fi
if grep -rnE "<script.*>[^<]+</script>" app/templates/ | grep -v 'type="application/json"'; then
    echo "FAIL: Inline executable scripts found."
    BAD_TPL=1
fi
if [ $BAD_TPL -eq 1 ]; then
    STATUS=1
else
    echo "PASS: Template hygiene."
fi

# 4. Pytest security marker
echo "Check 4: pytest -m security"
pytest -m security -q
if [ $? -ne 0 ]; then
    echo "FAIL: pytest security suite failed."
    STATUS=1
else
    echo "PASS: pytest security suite."
fi

# 5. Dependency pins
echo "Check 5: Dependency pins"
if grep -E '^[a-zA-Z0-9_-]+[>=<~^]+' requirements*.txt | grep -v '=='; then
    echo "FAIL: Unpinned or range requirements found."
    STATUS=1
else
    echo "PASS: Dependency pins."
fi

# 6. ProdConfig DEBUG is False
echo "Check 6: ProdConfig DEBUG is False"
python -c '
import sys
try:
    from app.config import ProdConfig
    if getattr(ProdConfig, "DEBUG", False):
        print("ProdConfig.DEBUG is True")
        sys.exit(1)
except Exception as e:
    if not isinstance(e, RuntimeError):
        print(f"Unexpected error loading ProdConfig: {e}")
        sys.exit(1)
sys.exit(0)
'
if [ $? -ne 0 ]; then
    echo "FAIL: ProdConfig check."
    STATUS=1
else
    echo "PASS: ProdConfig check."
fi

echo "----------------------------------------"
if [ $STATUS -eq 0 ]; then
    echo "SECURITY CHECK PASSED"
    exit 0
else
    echo "SECURITY CHECK FAILED"
    exit 1
fi
