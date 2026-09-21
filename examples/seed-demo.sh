#!/usr/bin/env bash
# Rebuilds the demo subject from scratch, by talking to the API like any other
# consumer would.
#
# The subject's memory lives in the mongo_data and pg_data volumes, and
# `.superset/teardown.sh` runs `docker compose down -v`, which destroys them. A
# demo that exists only in a volume is a demo a routine command erases; this
# script, not a volume backup, is the copy that survives — and it is also what
# makes "clone the repo and reach the same state" true.
#
# Usage: ./examples/seed-demo.sh          seeds `leo`
#        SUBJECT=throwaway ./examples/...  seeds any other subject
set -euo pipefail

cd "$(dirname "$0")/.."

SUBJECT="${SUBJECT:-leo}"
# The port comes from .env exactly as the Makefile reads it: workspaces each own
# a different block, so nothing here may hardcode one.
PORT="$(sed -n 's/^CORE_API_PORT=//p' .env 2>/dev/null | tail -1)"
API="http://localhost:${PORT:-8000}"
CONSOLIDATION_TIMEOUT=60

field() {
    python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1]) or "")' "$1"
}

message_payload() {
    python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1]}))' "$1"
}

wait_for_consolidation() {
    local session_id="$1" waited=0 status=''
    while [ "$waited" -lt "$CONSOLIDATION_TIMEOUT" ]; do
        status="$(curl -sS "${API}/sessions/${session_id}" | field status)"
        case "$status" in
            consolidated)
                echo "seed:   consolidated"
                return 0
                ;;
            failed)
                echo "seed: session ${session_id} came back 'failed'." >&2
                echo "seed: the consolidation worker gave up — docker compose logs consolidator" >&2
                return 1
                ;;
        esac
        sleep 2
        waited=$((waited + 2))
    done
    echo "seed: session ${session_id} was still '${status}' after ${CONSOLIDATION_TIMEOUT}s." >&2
    echo "seed: the consolidation worker is not draining the stream — docker compose logs consolidator" >&2
    return 1
}

seed_session() {
    local label="$1"
    shift
    echo "seed: ${label}"
    local session_id
    session_id="$(
        curl -sS -X POST "${API}/sessions" \
            -H 'content-type: application/json' \
            -d "$(python3 -c 'import json,sys; print(json.dumps({"subject_id": sys.argv[1]}))' "$SUBJECT")" |
            field session_id
    )"
    if [ -z "$session_id" ]; then
        echo "seed: ${API}/sessions did not return a session_id — is the stack up?" >&2
        return 1
    fi
    for message in "$@"; do
        echo "seed:   > ${message}"
        curl -sS -X POST "${API}/sessions/${session_id}/chat" \
            -H 'content-type: application/json' \
            -d "$(message_payload "$message")" >/dev/null
    done
    curl -sS -X POST "${API}/sessions/${session_id}/close" >/dev/null
    wait_for_consolidation "$session_id"
}

echo "seed: subject '${SUBJECT}' against ${API}"

# The memory that gets planted. Nobody ever fills in a "diet" field: the beef
# broth is mentioned once, in passing, inside a story about a restaurant.
seed_session "session 1 of 3 — the memory that gets planted" \
    "Hey, I'm Leo. Good to finally get this set up." \
    "Quick context about me: I've been vegetarian for about a year now." \
    "Last month some friends dragged me to that place in Roma Norte everyone raves about. It was a letdown, almost every dish had beef broth in it, so I ended up with a side salad and bread." \
    "Lesson learned. I should ask before going somewhere everyone's excited about."

# Two distractors, so recall has to discriminate instead of returning the only
# thing it holds.
seed_session "session 2 of 3 — distractor" \
    "I started swimming lessons on Tuesday mornings." \
    "First time in a pool since I was maybe ten." \
    "My instructor says my breathing is completely backwards." \
    "She has me doing drills with a kickboard for now."

seed_session "session 3 of 3 — distractor" \
    "I need to renew my passport before it expires in April." \
    "The appointment system is a nightmare, nothing until June." \
    "Someone told me there's an express office that takes walk-ins." \
    "I'll try that next week."

# Session 4 is not seeded: it is what gets typed live in the console.
echo "seed: done. '${SUBJECT}' remembers:"
curl -sS "${API}/subjects/${SUBJECT}/memory/facts"
echo
