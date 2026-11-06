#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Pull new commits and restart services (run by a systemd timer)
#
# Fetches origin/$BRANCH; if there are new commits it fast-forwards, refreshes
# Python deps / rebuilds the frontend only when those parts changed, and
# restarts the affected services. No-op when already up to date.
#
#   sudo bash deploy/auto-update.sh
#
# Git, pip and npm run as the repo owner; only systemctl runs as root.
# Never runs alembic migrations - it only warns when alembic/ changed.
# =============================================================================

set -euo pipefail

# The whole body is one { ... } block so bash parses it before running; the
# git merge below may rewrite this very file mid-run.
{
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BRANCH="${BRANCH:-main}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
RUN_USER="$(stat -c '%U' "$APP_DIR")"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

# shellcheck source=units.sh
source "$SCRIPT_DIR/units.sh"

log() { echo "[auto-update] $*"; }
warn() { echo "[auto-update WARN] $*" >&2; }
die() { echo "[auto-update ERROR] $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy/auto-update.sh"

as_user() { runuser -u "$RUN_USER" -- env HOME="$RUN_HOME" "$@"; }
git_() { as_user git -C "$APP_DIR" "$@"; }

# Only one run at a time (a frontend build can outlast the timer interval).
exec 9>"/run/integritydesk-auto-update.lock"
flock -n 9 || { log "Another update is running; skipping."; exit 0; }

git_ fetch --quiet origin "$BRANCH"
OLD="$(git_ rev-parse HEAD)"
NEW="$(git_ rev-parse "origin/$BRANCH")"
[ "$OLD" != "$NEW" ] || exit 0

[ "$(git_ rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || die "Checkout is not on $BRANCH; refusing to update."
git_ diff --quiet HEAD || die "Tracked files have local edits; refusing to update."

log "Updating ${OLD:0:8} -> ${NEW:0:8}"
git_ merge --ff-only --quiet "origin/$BRANCH" || die "Cannot fast-forward to origin/$BRANCH."

CHANGED="$(git_ diff --name-only "$OLD" "$NEW")"
changed() { grep -qE "$1" <<<"$CHANGED"; }

build_frontend() {
    as_user bash -c "cd '$APP_DIR/src/frontend' \
        && { [ \"\$1\" = 0 ] || npm ci --no-audit --no-fund; } \
        && API_URL='http://127.0.0.1:$BACKEND_PORT' NEXT_PUBLIC_API_URL='http://127.0.0.1:$BACKEND_PORT' npm run build" _ "$1"
}

rollback() {
    warn "$1 failed; rolling back to ${OLD:0:8} without restarting."
    git_ reset --keep --quiet "$OLD"
    if changed '^src/frontend/'; then
        build_frontend 1 || warn "Rebuild of ${OLD:0:8} also failed; dashboard may be broken."
    fi
    exit 1
}

if changed '^requirements\.txt$'; then
    log "requirements.txt changed; installing Python deps..."
    as_user "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt" || rollback "pip install"
fi

if changed '^src/frontend/'; then
    log "Frontend changed; rebuilding..."
    if changed '^src/frontend/package(-lock)?\.json$'; then
        build_frontend 1 || rollback "Frontend build"
    else
        build_frontend 0 || rollback "Frontend build"
    fi
fi

if changed '^alembic/'; then
    warn "alembic/ changed - review and run migrations manually (alembic upgrade head)."
fi

UNITS=()
if changed '^(src/backend/|src/[^/]*\.py$|requirements\.txt$)'; then
    mapfile -t -O "${#UNITS[@]}" UNITS < <(enabled_units "${BACKEND_UNITS[@]}")
fi
if changed '^src/frontend/'; then
    mapfile -t -O "${#UNITS[@]}" UNITS < <(enabled_units "${DASHBOARD_UNITS[@]}")
fi

if [ "${#UNITS[@]}" -gt 0 ]; then
    log "Restarting: ${UNITS[*]}"
    systemctl restart "${UNITS[@]}"
else
    log "No service-affecting changes; nothing to restart."
fi

log "Now at ${NEW:0:8}."
exit 0
}
