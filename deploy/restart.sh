#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Restart all services
# =============================================================================

set -euo pipefail

log() { echo -e "\033[1;32m[restart]\033[0m $*"; }

# Restart only enabled units; covers both the codeprovenance-* and the
# integritydesk-* unit names.
UNITS=()
for u in codeprovenance-backend codeprovenance-celery codeprovenance-embedding codeprovenance-dashboard \
         integritydesk-backend integritydesk-worker integritydesk-analysis-worker integritydesk-embedding integritydesk-dashboard; do
    systemctl is-enabled --quiet "$u" 2>/dev/null && UNITS+=("$u")
done

[ "${#UNITS[@]}" -gt 0 ] || { echo "No IntegrityDesk services are enabled." >&2; exit 1; }

log "Restarting: ${UNITS[*]}"
systemctl restart "${UNITS[@]}" || true

sleep 2
log "Done. Status:"
systemctl --no-pager --full status "${UNITS[@]}" | grep -E "●|Loaded:|Active:" || true
