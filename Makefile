# =============================================================================
# JudgeLoom — Makefile
# =============================================================================
# Common development commands.  Run `make` or `make help` to list them.
# =============================================================================

.DEFAULT_GOAL := help

# Detect the Python interpreter: prefer python3, fall back to python
PYTHON        := $(shell command -v python3 2>/dev/null || command -v python)
MANAGE        := $(PYTHON) manage.py
DC            := docker compose
DC_PROD       := docker compose -f docker-compose.yml -f docker-compose.prod.yml

# Colours for the help target
BOLD  := \033[1m
RESET := \033[0m
CYAN  := \033[36m

# ─── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "  $(BOLD)JudgeLoom — available make targets$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { \
		printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2 \
	}' $(MAKEFILE_LIST)
	@echo ""

# ─── Local development (no Docker) ───────────────────────────────────────────

.PHONY: install
install: ## Install development requirements
	pip install --upgrade pip wheel
	pip install -r requirements/development.txt

.PHONY: migrate
migrate: ## Apply database migrations
	$(MANAGE) migrate

.PHONY: makemigrations
makemigrations: ## Create new migrations
	$(MANAGE) makemigrations

.PHONY: run
run: ## Start the Django development server
	$(MANAGE) runserver 0.0.0.0:8000

.PHONY: shell
shell: ## Open an enhanced Django shell (shell_plus)
	$(MANAGE) shell_plus

.PHONY: superuser
superuser: ## Create a Django superuser
	$(MANAGE) createsuperuser

.PHONY: seed
seed: ## Run all management commands that seed initial data
	$(MANAGE) seed_tags
	$(MANAGE) seed_languages
	$(MANAGE) seed_problems

# ─── Testing ─────────────────────────────────────────────────────────────────

.PHONY: test
test: ## Run the test suite with pytest
	pytest

.PHONY: test-cov
test-cov: ## Run tests and output a coverage report
	pytest --cov --cov-report=term-missing

# ─── Code quality ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: ## Lint the codebase with ruff
	ruff check .

.PHONY: lint-fix
lint-fix: ## Lint and auto-fix issues with ruff
	ruff check --fix .

.PHONY: format
format: ## Format the codebase with ruff
	ruff format .

.PHONY: format-check
format-check: ## Check formatting without applying changes
	ruff format --check .

.PHONY: typecheck
typecheck: ## Run static type checks with mypy
	mypy .

.PHONY: check
check: lint typecheck test ## Run lint + typecheck + test (full CI gate)

# ─── Docker (development) ─────────────────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build development Docker images
	$(DC) build

.PHONY: docker-up
docker-up: ## Start the full development stack in the background
	$(DC) up -d

.PHONY: docker-down
docker-down: ## Stop and remove development containers
	$(DC) down

.PHONY: docker-logs
docker-logs: ## Tail logs from all development containers
	$(DC) logs -f

.PHONY: docker-ps
docker-ps: ## List running development containers
	$(DC) ps

.PHONY: docker-exec
docker-exec: ## Open a shell inside the running web container
	$(DC) exec web bash

.PHONY: docker-migrate
docker-migrate: ## Run migrations inside the Docker web container
	$(DC) exec web python manage.py migrate

.PHONY: docker-shell
docker-shell: ## Open Django shell_plus inside the Docker web container
	$(DC) exec web python manage.py shell_plus

# ─── Docker (production) ──────────────────────────────────────────────────────

.PHONY: docker-prod-build
docker-prod-build: ## Build production Docker images
	$(DC_PROD) build

.PHONY: docker-prod-up
docker-prod-up: ## Start the production stack in the background
	$(DC_PROD) up -d

.PHONY: docker-prod-down
docker-prod-down: ## Stop and remove production containers
	$(DC_PROD) down

.PHONY: docker-prod-logs
docker-prod-logs: ## Tail logs from production containers
	$(DC_PROD) logs -f

# ─── Maintenance ─────────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove Python bytecode and cache files
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	@echo "Cleaned bytecode and cache files."
