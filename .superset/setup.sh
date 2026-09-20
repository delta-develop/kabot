#!/usr/bin/env bash
# Superset workspace setup: materialize env, reserve host ports, install deps.
set -euo pipefail

# .env carries live secrets (OPENAI_API_KEY); do not let
# the default umask make it world- or group-readable.
umask 077

cd "$(dirname "$0")/.."
. .superset/ports.sh

command -v uv >/dev/null 2>&1 || {
    echo "setup: uv is not installed — run 'brew install uv'" >&2
    exit 1
}

if [ ! -f .env ]; then
    if [ -n "${SUPERSET_ROOT_PATH:-}" ] && [ -f "$SUPERSET_ROOT_PATH/.env" ]; then
        cp "$SUPERSET_ROOT_PATH/.env" .env
        echo "setup: .env copied from the main checkout"
    else
        cp .env.example .env
        echo "setup: .env created from .env.example"
    fi
fi

PORT_BASE="$(reserve_port_base)"
write_port_vars "$PORT_BASE"
echo "setup: host ports $PORT_BASE-$((PORT_BASE + 9)) reserved"

uv sync --all-packages --frozen
uv run pre-commit install --allow-missing-config

echo "setup: ready. 'make up' starts the stack:"
echo "  core-api  http://localhost:$((PORT_BASE + 0))"
echo "  agent     http://localhost:$((PORT_BASE + 1))"
echo "  memory    http://localhost:$((PORT_BASE + 2))"
