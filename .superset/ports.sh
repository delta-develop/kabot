#!/usr/bin/env bash
# Shared registry of host port blocks, one block of ten per workspace.
#
# Superset does not allocate ports (docs.superset.sh/ports); it only discovers
# ports already in use. Its documentation points at exactly this approach:
# reserving a range in a file shared by every worktree of the project.

PORT_REGISTRY="${SUPERSET_ROOT_PATH:-$PWD}/.superset/port-registry.local.json"
PORT_REGISTRY_LOCK="${PORT_REGISTRY}.lock"
PORT_RANGE_START=8100
PORT_RANGE_END=8990
PORT_RANGE_STEP=10
# Offsets published by write_port_vars below; the host probe must check all
# of them, not just the base, or a foreign process on a non-zero offset goes
# undetected until `docker compose up` fails.
PORT_OFFSETS="0 1 2 5 6 7"
# ponytail: 60s is a guessed ceiling for "abandoned lock", not measured
# against any real critical-section duration here; upgrade to a configurable
# threshold or a heartbeat-refreshed lock if legitimate holders start taking
# longer than this.
LOCK_STALE_SECONDS=60

if [ -z "${SUPERSET_ROOT_PATH:-}" ]; then
    echo "ports: SUPERSET_ROOT_PATH is not set, falling back to a workspace-local registry at $PORT_REGISTRY — every workspace will collide on the same blocks" >&2
fi

_lock_mtime_epoch() {
    stat -f %m "$PORT_REGISTRY_LOCK" 2>/dev/null || stat -c %Y "$PORT_REGISTRY_LOCK" 2>/dev/null
}

# A lock older than this has outlived any real critical section here; treat
# it as abandoned by a process that died without running its EXIT trap.
_lock_is_stale() {
    local mtime now
    mtime="$(_lock_mtime_epoch)" || return 1
    [ -n "$mtime" ] || return 1
    now="$(date +%s)"
    [ $((now - mtime)) -gt "$LOCK_STALE_SECONDS" ]
}

# mkdir is atomic in POSIX, unlike a sentinel file checked with `test -f` and
# created with `touch`, which races between the two calls.
#
# This function installs an EXIT trap by overwrite, replacing whatever trap
# the caller's own shell already had for EXIT. Callers MUST invoke any
# function that reaches this one (reserve_port_base, release_port_base)
# inside a subshell — e.g. `x="$(reserve_port_base)"` or `(release_port_base)`
# — never bare in their own top-level shell, or that shell's own EXIT trap is
# silently replaced and lost.
_registry_lock() {
    local waited=0
    until mkdir "$PORT_REGISTRY_LOCK" 2>/dev/null; do
        waited=$((waited + 1))
        if [ "$waited" -gt 50 ]; then
            if _lock_is_stale && rm -rf "$PORT_REGISTRY_LOCK" \
                && mkdir "$PORT_REGISTRY_LOCK" 2>/dev/null; then
                break
            fi
            echo "ports: registry locked by another process for 5s, giving up" >&2
            echo "ports: if you are sure it is stale, remove it with: rm -rf '$PORT_REGISTRY_LOCK'" >&2
            return 1
        fi
        sleep 0.1
    done
    # An ownership token — not just the directory's existence — decides who
    # may remove the lock: the stale-break above can hand the directory to a
    # new owner while the original holder is still alive (past the staleness
    # threshold but not actually dead), and that original holder's own
    # eventual release must not delete the new owner's lock.
    _LOCK_TOKEN="$RANDOM$RANDOM$(date +%s)"
    echo "$_LOCK_TOKEN" > "$PORT_REGISTRY_LOCK/owner"
    # Release on any exit, not just the normal return path below, so a
    # `set -e` abort or death by a trappable signal (e.g. SIGTERM) does not
    # leave the lock directory on disk forever. EXIT only, deliberately: a
    # bare `trap ... TERM` runs the handler and then RESUMES execution inside
    # the critical section instead of dying, which defeats the lock. EXIT
    # alone still fires when the process is killed by a trappable signal, and
    # it lets the process actually die afterward. _registry_unlock is
    # idempotent, so it firing again from the explicit call further down is
    # harmless.
    trap '_registry_unlock' EXIT
}

_registry_unlock() {
    local owner
    owner="$(cat "$PORT_REGISTRY_LOCK/owner" 2>/dev/null)" || return 0
    [ "$owner" = "${_LOCK_TOKEN:-}" ] || return 0
    rm -f "$PORT_REGISTRY_LOCK/owner"
    rmdir "$PORT_REGISTRY_LOCK" 2>/dev/null || true
}

_workspace_path() {
    echo "${SUPERSET_WORKSPACE_PATH:-$PWD}"
}

# Drops entries whose worktree directory no longer exists, so a workspace
# deleted without running teardown does not leak its block forever.
# ponytail: a transiently missing directory (an unmounted drive, a race
# during workspace deletion) reads the same as a deleted workspace and frees
# a block still in use; upgrade to requiring N consecutive misses or a
# recorded last-seen timestamp if this false positive shows up in practice.
_registry_collect() {
    local kept
    kept="$(mktemp)"
    while IFS="$(printf '\t')" read -r port path; do
        [ -n "$port" ] || continue
        [ -d "$path" ] && printf '%s\t%s\n' "$port" "$path" >> "$kept"
    done < "$PORT_REGISTRY"
    mv "$kept" "$PORT_REGISTRY"
}

_port_is_taken_on_host() {
    command -v nc >/dev/null 2>&1 || return 1
    nc -z 127.0.0.1 "$1" >/dev/null 2>&1
}

# A block is unusable if any of its published offsets is already bound on
# the host, not just the base port.
_block_is_taken_on_host() {
    local base="$1" offset
    for offset in $PORT_OFFSETS; do
        _port_is_taken_on_host "$((base + offset))" && return 0
    done
    return 1
}

# Echoes the base port of this workspace's block. Idempotent: a workspace that
# already holds a block gets the same one back.
# ponytail: every real caller holds this lock inside a `$(reserve_port_base)`
# command substitution (see setup.sh), which forks a subshell to run this
# function's body. If that subshell is killed by a signal while it holds the
# lock, bash does not run the subshell's own EXIT trap, so the lock leaks —
# the killed holder never reaches its explicit _registry_unlock call either.
# This is a documented, self-healing ceiling, not a bug: the leaked lock
# costs one failed reservation and is recovered by the next caller via the
# staleness break in _registry_lock once LOCK_STALE_SECONDS passes. Upgrade
# path if this ceiling stops being acceptable: have this function set a
# variable instead of echoing its result, so the caller's own top-level shell
# holds the lock directly and its own EXIT trap fires reliably on signal
# death.
reserve_port_base() {
    mkdir -p "$(dirname "$PORT_REGISTRY")"
    _registry_lock || return 1
    touch "$PORT_REGISTRY"
    _registry_collect

    local mine me
    me="$(_workspace_path)"
    mine="$(ME="$me" awk -F'\t' 'BEGIN { p = ENVIRON["ME"] } $2 == p { print $1; exit }' "$PORT_REGISTRY")"
    if [ -n "$mine" ]; then
        _registry_unlock
        echo "$mine"
        return 0
    fi

    local base="$PORT_RANGE_START"
    while [ "$base" -le "$PORT_RANGE_END" ]; do
        if ! grep -q "^${base}$(printf '\t')" "$PORT_REGISTRY" \
            && ! _block_is_taken_on_host "$base"; then
            printf '%s\t%s\n' "$base" "$me" >> "$PORT_REGISTRY"
            _registry_unlock
            echo "$base"
            return 0
        fi
        base=$((base + PORT_RANGE_STEP))
    done

    _registry_unlock
    echo "ports: no free block between $PORT_RANGE_START and $PORT_RANGE_END" >&2
    return 1
}

release_port_base() {
    _registry_lock || return 1
    if [ ! -f "$PORT_REGISTRY" ]; then
        _registry_unlock
        return 0
    fi
    local kept me
    kept="$(mktemp)"
    me="$(_workspace_path)"
    ME="$me" awk -F'\t' 'BEGIN { p = ENVIRON["ME"] } $2 != p' "$PORT_REGISTRY" > "$kept"
    mv "$kept" "$PORT_REGISTRY"
    _registry_unlock
}

_set_env_var() {
    local key="$1" value="$2" kept
    if [ -s .env ] && [ "$(tail -c 1 .env)" != "" ]; then
        printf '\n' >> .env
    fi
    if grep -q "^${key}=" .env 2>/dev/null; then
        kept="$(mktemp)"
        awk -F= -v k="$key" -v v="$value" \
            '$1 == k { print k "=" v; next } { print }' .env > "$kept"
        mv "$kept" .env
    else
        printf '%s=%s\n' "$key" "$value" >> .env
    fi
}

write_port_vars() {
    local base="$1"
    _set_env_var PORT_BASE "$base"
    _set_env_var CORE_API_PORT "$((base + 0))"
    _set_env_var AGENT_PORT "$((base + 1))"
    _set_env_var MEMORY_PORT "$((base + 2))"
    _set_env_var POSTGRES_PORT "$((base + 5))"
    _set_env_var MONGO_PORT "$((base + 6))"
    _set_env_var REDIS_PORT "$((base + 7))"
}
