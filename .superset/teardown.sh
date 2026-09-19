#!/usr/bin/env bash
# Superset workspace teardown: drop the stack and release the port block.
set -uo pipefail

cd "$(dirname "$0")/.."
. .superset/ports.sh

if [ -f .env ]; then
    if ! docker compose down -v --remove-orphans; then
        echo "teardown: docker compose down failed, keeping the port block" >&2
        echo "teardown: it will be collected once the worktree is removed" >&2
        exit 1
    fi
fi

if (release_port_base); then
    echo "teardown: port block released"
else
    echo "teardown: failed to release the port block, registry may be locked" >&2
    exit 1
fi
