# Makefile to manage the Kabot project with Docker Compose

# Variables
# Reads CORE_API_PORT from .env so open-api targets the port this workspace
# actually published; falls back to 8000 when there is no .env (installed
# make is 3.81 on macOS, so $(or ...) is unavailable — $(if ...) instead).
CORE_API_PORT_FROM_ENV := $(shell sed -n 's/^CORE_API_PORT=//p' .env 2>/dev/null)
API_URL := http://localhost:$(if $(CORE_API_PORT_FROM_ENV),$(CORE_API_PORT_FROM_ENV),8000)

# Commands to open URLs (tries to be compatible with Linux, macOS, and Windows)
OPEN_CMD := xdg-open
ifeq ($(shell uname -s),Darwin)
	OPEN_CMD := open
else ifeq ($(findstring Microsoft,$(shell uname -r)),Microsoft)
	OPEN_CMD := start
endif

.PHONY: help up down build build-app build-up open-api logs ps restart rebuild shell install test lint format typecheck coverage

# Materializes .env from the template on a plain clone; a Superset workspace
# already has one from .superset/setup.sh, so this rule is a no-op there.
.env: .env.example
	cp $< $@

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo "  up                Starts all services in the background."
	@echo "  down              Stops and removes all containers, networks, and (optionally) volumes."
	@echo "  build             Builds or rebuilds service images (especially 'core-api')."
	@echo "  build-app         Specifically builds the 'core-api' service image."
	@echo "  open-api          Opens the API URL (${API_URL}) in the default browser."
	@echo "  logs              Shows logs for all services."
	@echo "  logs-app          Shows logs for the 'core-api' service."
	@echo "  ps                Lists running containers."
	@echo "  restart           Restarts all services (down + up)."
	@echo "  rebuild           Rebuilds the 'core-api' image and restarts all services."
	@echo "  shell             Opens an interactive shell in the 'core-api' service container."
	@echo "  install           Syncs the uv workspace and installs the pre-commit hook."

# Start all services
up: .env
	@echo "Starting all services..."
	docker compose up -d --wait

# Stop all services
down: .env
	@echo "Stopping all services..."
	docker compose -f docker-compose.yml down

# Build all images (if changed)
build: .env build-app

# Build the Python application image
build-app: .env
	@echo "Building the 'core-api' service image..."
	docker compose -f docker-compose.yml build core-api

# Open API in browser
open-api:
	@echo "Opening API at ${API_URL}..."
	$(OPEN_CMD) ${API_URL}

# Additional useful commands
logs: .env
	docker compose -f docker-compose.yml logs -f

logs-app: .env
	docker compose -f docker-compose.yml logs -f core-api

ps: .env
	docker compose -f docker-compose.yml ps

restart: down up

rebuild: build-app down up

build-up: .env
	docker compose build && docker compose up -d

shell: .env
	docker compose exec core-api /bin/bash

psql: .env
	docker compose exec postgres psql -U kabot -d kavak

rebuild-app: .env
	docker compose build core-api
	docker compose up -d core-api

start: build-up

SERVICES := core-api agent memory

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
	@status=0; \
	for s in $(SERVICES); do \
		echo "== $$s =="; \
		(cd services/$$s && uv run --no-sync mypy app) || status=1; \
	done; \
	exit $$status
