
PYTHON ?= python3
FLASK  ?= flask

.PHONY: help run init-db lint format test test-unit test-integration test-e2e test-core test-tier3 gate-check tier3-branch docker-up docker-test docker-down vendor-wheels clean

# Default target: display self-documenting help menu
help:
	@echo "======================================================================"
	@echo "Examination Management Portal (LMS) - Developer Commands"
	@echo "======================================================================"
	@echo "Development:"
	@echo "  make run              Start Flask development server with debug reload"
	@echo "  make init-db          Initialize SQLite schema & seed Admin account"
	@echo ""
	@echo "Code Quality & Formatting:"
	@echo "  make lint             Run ruff static check and black format check"
	@echo "  make format           Automatically reformat code with ruff & black"
	@echo ""
	@echo "Testing & Gates:"
	@echo "  make test             Alias for test-core"
	@echo "  make test-core        Run Tier 1 & Tier 2 unit, integration & e2e tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-e2e         Run Playwright browser integration tests"
	@echo "  make test-tier3       Run Tier 3 tests (only after Gate B)"
	@echo "  make gate-check       Execute repository tier-gate integrity check"
	@echo "  make tier3-branch     Create a Tier 3 branch (requires NAME=<slug>)"
	@echo ""
	@echo "Docker & Offline Tools:"
	@echo "  make docker-up        Build and start application in Docker container"
	@echo "  make docker-test      Run complete test suite offline in Docker"
	@echo "  make docker-down      Stop and remove Docker containers"
	@echo "  make vendor-wheels    Download offline wheels for offline builds"
	@echo "  make clean            Remove bytecode, cache, and temporary test files"
	@echo "======================================================================"

#dev and db 
run:
	$(FLASK) --app app run --debug

init-db:
	$(FLASK) --app app init-db

#lint and format 
lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .
#test
test: test-core

test-unit:
	pytest tests/unit -q

test-integration:
	pytest tests/integration -q

test-api:
	pytest -m api -v

test-e2e:
	pytest tests/e2e -q -m e2e

test-core:
	pytest tests/unit tests/integration -q
	@if [ -d tests/e2e ] && [ -n "$$(ls -A tests/e2e/*.py 2>/dev/null)" ]; then \
		pytest tests/e2e -q -m e2e; \
	fi

test-tier3:
	@if [ ! -d tests/tier3 ]; then \
		echo "Tier 3 not started (see Gate B requirement in Master Blueprint)"; \
		exit 0; \
	else \
		$(MAKE) test-core && pytest tests/tier3 -q; \
	fi
#workflow
gate-check:
	bash scripts/check_gate.sh

tier3-branch:
	@if [ -z "$(NAME)" ]; then \
		echo "ERROR: Missing branch name. Usage: make tier3-branch NAME=p13-test-foundation"; \
		exit 1; \
	fi
	bash scripts/check_gate.sh tier3/$(NAME)
	git checkout -b tier3/$(NAME) refs/tags/tier2-complete

#docker features
docker-up:
	docker compose up --build

docker-test:
	docker compose --profile test run --rm test

docker-down:
	docker compose down

vendor-wheels:
	bash scripts/vendor_wheels.sh


clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	find . -type f -name "*$$py.class" -delete
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage





#debug
# make -n test-core   (dry run prints commands without executing)
# OFFLINE DOCKER TEST CASES:
# - make help lists every target.
# - make lint passes on a clean checkout of P0.
# - make test-tier3 exits 0 and prints the "Tier 3 not started" notice.
