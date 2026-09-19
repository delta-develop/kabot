#!/usr/bin/env bash
# Runnable check for the port range registry. Run: ./.superset/ports_test.sh
set -uo pipefail

cd "$(dirname "$0")/.."

FAILURES=0

assert_eq() {
    if [ "$1" != "$2" ]; then
        echo "FAIL: $3 — expected '$2', got '$1'"
        FAILURES=$((FAILURES + 1))
    else
        echo "ok: $3"
    fi
}

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

export SUPERSET_ROOT_PATH="$SANDBOX/root"
mkdir -p "$SUPERSET_ROOT_PATH/.superset"
mkdir -p "$SANDBOX/wsA" "$SANDBOX/wsB"

. .superset/ports.sh

# The block numbers asserted below must not depend on what happens to be
# listening on this machine, so the host check is stubbed out for the test.
_port_is_taken_on_host() { return 1; }

SUPERSET_WORKSPACE_PATH="$SANDBOX/wsA"
A="$(reserve_port_base)"
assert_eq "$A" "8100" "first workspace gets the first block"

SUPERSET_WORKSPACE_PATH="$SANDBOX/wsB"
B="$(reserve_port_base)"
assert_eq "$B" "8110" "second workspace gets the next block"

SUPERSET_WORKSPACE_PATH="$SANDBOX/wsA"
A_AGAIN="$(reserve_port_base)"
assert_eq "$A_AGAIN" "8100" "re-running setup reuses the same block"

SUPERSET_WORKSPACE_PATH="$SANDBOX/wsA"
# Run in a subshell: _registry_lock sets a trap to guarantee release, and a
# bare (non-substituted) call would otherwise overwrite this script's own
# top-level EXIT trap that cleans up $SANDBOX.
(release_port_base)
rm -rf "$SANDBOX/wsB"
SUPERSET_WORKSPACE_PATH="$SANDBOX/wsC"
mkdir -p "$SANDBOX/wsC"
C="$(reserve_port_base)"
assert_eq "$C" "8100" "a released block is handed out again"

LEFT="$(wc -l < "$SUPERSET_ROOT_PATH/.superset/port-registry.local.json" | tr -d ' ')"
assert_eq "$LEFT" "1" "the deleted workspace's block was garbage-collected"

# A process that dies without reaching its explicit _registry_unlock call
# must still release the lock via the EXIT trap installed by _registry_lock
# (SIGTERM is a trappable signal, so it still triggers EXIT on the way out).
#
# This runs as a genuinely separate process — not a `(...)` subshell of this
# script — because bash 3.2 (macOS) has a trap-inheritance quirk: when the
# parent shell already has an EXIT trap (this script's own $SANDBOX cleanup,
# set above), a forked `(...)` subshell's own `trap ... EXIT` overwrite does
# not reliably arm for a signal-induced death — the process still dies, but
# the wrong trap (or none) runs instead of the child's own. A freshly exec'd
# process starts with a clean trap table and does not hit this; it is also
# what setup.sh/teardown.sh actually are in production, so this is the more
# faithful test.
KILL_VICTIM="$SANDBOX/kill_victim.sh"
cat > "$KILL_VICTIM" <<VEOF
#!/usr/bin/env bash
set -uo pipefail
. "$PWD/.superset/ports.sh"
_registry_lock
sleep 2
VEOF
chmod +x "$KILL_VICTIM"
"$KILL_VICTIM" &
KILL_PID=$!
sleep 0.3
kill -TERM "$KILL_PID" 2>/dev/null
wait "$KILL_PID" 2>/dev/null
if [ -d "$PORT_REGISTRY_LOCK" ]; then
    LOCK_AFTER_KILL="present"
else
    LOCK_AFTER_KILL="absent"
fi
assert_eq "$LOCK_AFTER_KILL" "absent" "a killed process releases the lock via its EXIT trap"

# A lock directory abandoned long enough (older than the 60s staleness
# threshold) must be broken and the reservation must still succeed, instead
# of failing forever. Backdated with touch -t so this does not need to sleep
# past the threshold. The lock must contain an owner file, the same shape
# _registry_lock actually leaves — a bare empty directory is not what a real
# holder produces, and rmdir (unlike rm -rf) cannot remove a non-empty one.
mkdir "$PORT_REGISTRY_LOCK"
echo "some-leaked-owner-token" > "$PORT_REGISTRY_LOCK/owner"
STALE_TS="$(date -v-90S +%Y%m%d%H%M.%S 2>/dev/null || date -d '90 seconds ago' +%Y%m%d%H%M.%S)"
touch -t "$STALE_TS" "$PORT_REGISTRY_LOCK"
SUPERSET_WORKSPACE_PATH="$SANDBOX/wsStale"
mkdir -p "$SUPERSET_WORKSPACE_PATH"
STALE="$(reserve_port_base)"
assert_eq "$STALE" "8110" "a stale lock is broken and the reservation still succeeds"

# A block must be rejected if any of its published offsets (not just the
# base) is already bound on the host.
_port_is_taken_on_host() { [ "$1" = "8125" ] && return 0 || return 1; }
SUPERSET_WORKSPACE_PATH="$SANDBOX/wsSkip"
mkdir -p "$SUPERSET_WORKSPACE_PATH"
SKIPPED="$(reserve_port_base)"
assert_eq "$SKIPPED" "8130" "a block with an occupied non-base offset (+5) is skipped"
_port_is_taken_on_host() { return 1; }

# A workspace path containing a backslash must still match itself on the
# second reservation and be fully removed on release. `awk -v p="$me"` would
# escape-process the backslash, so `$2 == p` (and `$2 != p`) would never
# match the literal path stored in the registry — this is the exact
# regression the ENVIRON-based awk calls in reserve_port_base/release_port_base
# fix. Both reservation checks assert a literal expected block, not just
# equality with each other: comparing two empty strings (what a silently
# failed reservation would also produce) would print `ok:` for nothing.
WS_BACKSLASH="${SANDBOX}/ws\\bs"
mkdir -p "$WS_BACKSLASH"
SUPERSET_WORKSPACE_PATH="$WS_BACKSLASH"
BS_FIRST="$(reserve_port_base)"
assert_eq "$BS_FIRST" "8120" "a workspace path with a backslash gets a real block"
BS_SECOND="$(reserve_port_base)"
assert_eq "$BS_SECOND" "8120" "a workspace path with a backslash is matched idempotently"
(release_port_base)
BS_REMAINING="$(ME="$WS_BACKSLASH" awk -F'\t' 'BEGIN { p = ENVIRON["ME"] } $2 == p { print $1; exit }' "$SUPERSET_ROOT_PATH/.superset/port-registry.local.json")"
assert_eq "$BS_REMAINING" "" "release removes the backslash workspace's entry"

# NB-2 regression: releasing a lock must not destroy it once another owner
# has taken it over (exactly what the stale-break hands to a new owner while
# the original holder is still alive, just past the staleness threshold).
# Single shell, no timing dependency: acquire in a subshell (so the trap it
# sets only replaces that subshell's own copy) and capture the token it
# generated over stdout. `trap - EXIT` as the subshell's last act stops its
# own normal exit from releasing the lock we deliberately want to leave
# behind for the outer shell to manipulate.
_LOCK_TOKEN="$(_registry_lock; echo "$_LOCK_TOKEN"; trap - EXIT)"
echo "a-different-owners-token" > "$PORT_REGISTRY_LOCK/owner"
_registry_unlock
if [ -d "$PORT_REGISTRY_LOCK" ]; then
    NB2_LOCK_STATE="present"
else
    NB2_LOCK_STATE="absent"
fi
assert_eq "$NB2_LOCK_STATE" "present" "releasing a lock does not delete it once a new owner holds it"
rm -rf "$PORT_REGISTRY_LOCK"

# G3: production actually holds the lock inside `$(reserve_port_base)` (see
# setup.sh:27), never via a bare _registry_lock call like the kill-test
# above. Killing the outer exec'd process while that inner subshell still
# holds the lock leaks it — this is the documented ceiling on
# reserve_port_base (see its ponytail comment), not something this fixes. A
# host-check stub that sleeps keeps the holder inside the critical section
# long enough to signal it deterministically, no timing luck involved.
CS_VICTIM="$SANDBOX/cs_victim.sh"
CS_WORKSPACE="$SANDBOX/wsCS"
mkdir -p "$CS_WORKSPACE"
cat > "$CS_VICTIM" <<VEOF
#!/usr/bin/env bash
set -uo pipefail
export SUPERSET_ROOT_PATH="$SUPERSET_ROOT_PATH"
export SUPERSET_WORKSPACE_PATH="$CS_WORKSPACE"
. "$PWD/.superset/ports.sh"
_port_is_taken_on_host() { sleep 5; return 1; }
PORT_BASE="\$(reserve_port_base)"
echo "cs_victim: PORT_BASE=\$PORT_BASE" >> "$SANDBOX/cs_victim.log"
VEOF
chmod +x "$CS_VICTIM"
"$CS_VICTIM" &
CS_PID=$!
sleep 0.5
kill -TERM "$CS_PID" 2>/dev/null
wait "$CS_PID" 2>/dev/null
if [ -d "$PORT_REGISTRY_LOCK" ]; then
    CS_LEAKED="present"
else
    CS_LEAKED="absent"
fi
assert_eq "$CS_LEAKED" "present" "killing a \$(reserve_port_base) holder leaks the lock (documented ceiling)"

# The killed outer process leaves its inner $(reserve_port_base) subshell
# running as an orphan until its artificial sleep finishes — that orphan is
# the leak this test documents. Reap it by its unique sandbox path so it
# does not linger past this run (it would otherwise fail loudly a few
# seconds from now, referencing a $SANDBOX a later test run has deleted).
pkill -9 -f "$CS_VICTIM" 2>/dev/null || true

# The guarantee in place of preventing the leak: it self-heals on the next
# reservation once the lock is old enough to be considered abandoned.
CS_STALE_TS="$(date -v-90S +%Y%m%d%H%M.%S 2>/dev/null || date -d '90 seconds ago' +%Y%m%d%H%M.%S)"
touch -t "$CS_STALE_TS" "$PORT_REGISTRY_LOCK"
SUPERSET_WORKSPACE_PATH="$SANDBOX/wsCSRecover"
mkdir -p "$SUPERSET_WORKSPACE_PATH"
CS_RECOVERED="$(reserve_port_base)"
assert_eq "$CS_RECOVERED" "8120" "a lock leaked by a killed \$(reserve_port_base) holder self-heals via the stale-break"

if [ "$FAILURES" -gt 0 ]; then
    echo "$FAILURES check(s) failed"
    exit 1
fi
echo "all checks passed"
