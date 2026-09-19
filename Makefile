# Makefile to manage the Kabot project with Docker Compose

# Variables
API_URL := http://localhost:8000

# Commands to open URLs (tries to be compatible with Linux, macOS, and Windows)
OPEN_CMD := xdg-open
ifeq ($(shell uname -s),Darwin)
	OPEN_CMD := open
else ifeq ($(findstring Microsoft,$(shell uname -r)),Microsoft)
	OPEN_CMD := start
endif

.PHONY: help up down build build-app open-api logs ps restart rebuild setup shell install

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo "  up                Starts all services in the background."
	@echo "  down              Stops and removes all containers, networks, and (optionally) volumes."
	@echo "  build             Builds or rebuilds service images (especially 'app')."
	@echo "  build-app         Specifically builds the 'app' service image."
	@echo "  open-api          Opens the API URL (${API_URL}) in the default browser."
	@echo "  logs              Shows logs for all services."
	@echo "  logs-app          Shows logs for the 'app' service."
	@echo "  ps                Lists running containers."
	@echo "  restart           Restarts all services (down + up)."
	@echo "  rebuild           Rebuilds the 'app' image and restarts all services."
	@echo "  setup             Runs the setup script to initialize databases."
	@echo "  shell             Opens an interactive shell in the 'app' service container."
	@echo "  install           Syncs the uv workspace and installs the pre-commit hook."

# Start all services
up:
	@echo "Starting all services..."
	docker-compose -f docker-compose.yml up -d

# Stop all services
down:
	@echo "Stopping all services..."
	docker-compose -f docker-compose.yml down

# Build all images (if changed)
build: build-app

# Build the Python application image
build-app:
	@echo "Building the 'app' service image..."
	docker-compose -f docker-compose.yml build app

# Open API in browser
open-api:
	@echo "Opening API at ${API_URL}..."
	$(OPEN_CMD) ${API_URL}

# Additional useful commands
logs:
	docker-compose -f docker-compose.yml logs -f

logs-app:
	docker-compose -f docker-compose.yml logs -f app

ps:
	docker-compose -f docker-compose.yml ps

restart: down up

rebuild: build-app down up

build-up:
	docker-compose build && docker-compose up -d

# Run setup script to initialize databases
setup:
	@echo "Running setup script to initialize databases..."
	docker-compose exec app python3 -m app.setup

shell:
	docker-compose exec app /bin/bash
venv:
	@echo "Activating virtual environment..."
	. venv/bin/activate && exec $$SHELL

psql:
	docker-compose exec postgres psql -U kabot -d kavak

rebuild-app:
	docker-compose build app
	docker-compose up -d app

start: build-up

SERVICES := core-api

install:
	uv sync --all-packages
	uv run --no-sync pre-commit install --allow-missing-config

test: install
	@for s in $(SERVICES); do \
		echo "== $$s =="; \
		(cd services/$$s && uv run --no-sync pytest tests/ -q) || exit 1; \
	done

coverage: install
	cd services/core-api && uv run --no-sync coverage run -m pytest tests/ && uv run --no-sync coverage report -m

lint: install
	uv run --no-sync black --check .
	uv run --no-sync isort --check-only .

format: install
	uv run --no-sync black .
	uv run --no-sync isort .

typecheck: install
	@for s in $(SERVICES); do \
		echo "== $$s =="; \
		(cd services/$$s && uv run --no-sync mypy app) || exit 1; \
	done
