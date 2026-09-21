#!/usr/bin/env bash
# Wipe every store and rebuild the demo subject from scratch.
#
# This is the "start over" button. It destroys the Postgres and Mongo volumes
# and everything Redis is holding, rebuilds the images so a `git pull` actually
# takes effect, brings the stack back up and re-seeds the demo subject.
#
# It does NOT touch .env and does NOT go through .superset/teardown.sh, so the
# reserved port block survives: the console stays on the port the runbook says
# it is on.
#
# Usage: ./examples/reset-demo.sh                 wipes everything, seeds `leo`
#        SUBJECT=demo ./examples/reset-demo.sh    seeds a different subject
#        SKIP_BUILD=1 ./examples/reset-demo.sh    faster, when no code changed
set -euo pipefail

cd "$(dirname "$0")/.."

SUBJECT="${SUBJECT:-leo}"
PORT="$(sed -n 's/^CORE_API_PORT=//p' .env 2>/dev/null | tail -1)"
API="http://localhost:${PORT:-8000}"
CONSOLE_PORT="$(sed -n 's/^CONSOLE_PORT=//p' .env 2>/dev/null | tail -1)"
READY_TIMEOUT=90

step() { printf '\n\033[1;36mreset: %s\033[0m\n' "$*"; }

if [ ! -f .env ]; then
    echo "reset: no .env here. Run 'make up' once first, or copy .env.example." >&2
    exit 1
fi

step "stopping the stack and deleting the volumes"
docker compose down -v --remove-orphans

if [ -n "${SKIP_BUILD:-}" ]; then
    step "starting the stack (build skipped)"
    docker compose up -d --wait
else
    # Rebuilding by default: the most common way this script gets run is right
    # after a `git pull`, and a source change that never reaches the image is
    # the failure it exists to prevent.
    step "rebuilding the images and starting the stack"
    docker compose up -d --build --wait
fi

step "waiting for the API"
waited=0
until curl -sSf -o /dev/null "${API}/author" 2>/dev/null; do
    if [ "$waited" -ge "$READY_TIMEOUT" ]; then
        echo "reset: ${API} never answered after ${READY_TIMEOUT}s." >&2
        echo "reset: docker compose logs core-api" >&2
        exit 1
    fi
    sleep 2
    waited=$((waited + 2))
done
echo "reset:   ${API} is up after ${waited}s"

step "seeding '${SUBJECT}' — this calls the model, it takes a few minutes"
SUBJECT="$SUBJECT" ./examples/seed-demo.sh

step "done"
echo "  console   http://localhost:${CONSOLE_PORT:-8003}"
echo "  subject   ${SUBJECT}"
echo
echo "  Hard-refresh the browser (Cmd+Shift+R) so it picks up the rebuilt bundle."
