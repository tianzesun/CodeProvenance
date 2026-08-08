#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Restart all services
# =============================================================================

set -euo pipefail

log() { echo -e "\033[1;32m[restart]\033[0m $*"; }

log "Restarting IntegrityDesk services..."
systemctl restart integritydesk-backend integritydesk-dashboard integritydesk-worker || true
if systemctl list-unit-files integritydesk-embedding.service >/dev/null 2>&1; then
    systemctl restart integritydesk-embedding || true
fi

sleep 2
log "Done. Status:"
systemctl --no-pager --full status integritydesk-backend integritydesk-dashboard integritydesk-worker \
    | grep -E "Loaded:|Active:" || true
