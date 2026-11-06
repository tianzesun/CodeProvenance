#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Update after git pull
# Reinstalls Python deps (if changed), rebuilds the frontend, and restarts
# the systemd services. Does NOT touch deploy.conf or .env.local.
# deploy.conf is optional; without it the repo owner and default ports are used.
#
#   sudo bash deploy/update.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

CONF_FILE="$SCRIPT_DIR/deploy.conf"

# shellcheck source=units.sh
source "$SCRIPT_DIR/units.sh"

log() { echo -e "\033[1;32m[update]\033[0m $*"; }
warn() { echo -e "\033[1;33m[update WARN]\033[0m $*"; }
die() { echo -e "\033[1;31m[update ERROR]\033[0m $*" >&2; exit 1; }

if [ -f "$CONF_FILE" ]; then
    # shellcheck disable=SC1090
    source "$CONF_FILE"
else
    warn "No $CONF_FILE; using defaults."
fi

APP_DIR="${APP_DIR:-$REPO_DIR}"
RUN_USER="${RUN_USER:-$(stat -c '%U' "$REPO_DIR")}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

APP_DIR="$(realpath -m "$APP_DIR")"

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy/update.sh"

# pip/npm run as the service user so venv, node_modules and .next stay owned by it.
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
as_user() { runuser -u "$RUN_USER" -- env HOME="$RUN_HOME" "$@"; }

log "Refreshing Python dependencies..."
as_user "$APP_DIR/venv/bin/pip" install -q --upgrade pip
as_user "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

log "Rebuilding frontend..."
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
as_user bash -c "cd '$APP_DIR/src/frontend' \
    && npm install --no-audit --no-fund \
    && API_URL='$BACKEND_URL' NEXT_PUBLIC_API_URL='$BACKEND_URL' npm run build"

log "Restarting services..."
mapfile -t UNITS < <(enabled_units "${BACKEND_UNITS[@]}" "${DASHBOARD_UNITS[@]}")
if [ "${#UNITS[@]}" -gt 0 ]; then
    systemctl restart "${UNITS[@]}" || true
else
    warn "No IntegrityDesk services are enabled; nothing restarted."
fi

log "Update complete. Verify with: sudo bash deploy/status.sh"
