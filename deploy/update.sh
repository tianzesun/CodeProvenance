#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Update after git pull
# Reinstalls Python deps (if changed), rebuilds the frontend, and restarts
# the systemd services. Does NOT touch deploy.conf or .env.local.
#
#   sudo bash deploy/update.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

CONF_FILE="$SCRIPT_DIR/deploy.conf"

log() { echo -e "\033[1;32m[update]\033[0m $*"; }
warn() { echo -e "\033[1;33m[update WARN]\033[0m $*"; }
die() { echo -e "\033[1;31m[update ERROR]\033[0m $*" >&2; exit 1; }

[ -f "$CONF_FILE" ] || die "Missing $CONF_FILE. Run deploy/setup.sh first."

# shellcheck disable=SC1090
source "$CONF_FILE"

APP_DIR="${APP_DIR:-$REPO_DIR}"
RUN_USER="${RUN_USER:-${SUDO_USER:-$(whoami)}}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

APP_DIR="$(realpath -m "$APP_DIR")"

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy/update.sh"

log "Refreshing Python dependencies..."
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

log "Rebuilding frontend..."
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
(
    cd "$APP_DIR/src/frontend"
    npm install --no-audit --no-fund
    API_URL="$BACKEND_URL" NEXT_PUBLIC_API_URL="$BACKEND_URL" npm run build
)

log "Restarting services..."
systemctl restart integritydesk-backend integritydesk-dashboard integritydesk-worker || true
if systemctl list-unit-files integritydesk-embedding.service >/dev/null 2>&1; then
    systemctl restart integritydesk-embedding || true
fi

log "Update complete. Verify with: systemctl status integritydesk-{backend,dashboard,worker}"
