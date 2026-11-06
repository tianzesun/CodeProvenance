#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Restart all services
# =============================================================================

set -euo pipefail

# shellcheck source=units.sh
source "$(dirname "${BASH_SOURCE[0]}")/units.sh"

log() { echo -e "\033[1;32m[restart]\033[0m $*"; }

mapfile -t UNITS < <(enabled_units "${BACKEND_UNITS[@]}" "${DASHBOARD_UNITS[@]}")
[ "${#UNITS[@]}" -gt 0 ] || { echo "No IntegrityDesk services are enabled." >&2; exit 1; }

log "Restarting: ${UNITS[*]}"
systemctl restart "${UNITS[@]}" || true

sleep 2
log "Done. Status:"
systemctl --no-pager --full status "${UNITS[@]}" | grep -E "●|Loaded:|Active:" || true
