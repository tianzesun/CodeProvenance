# =============================================================================
# IntegrityDesk - systemd unit names (sourced by the other deploy scripts)
#
# Servers use either the integritydesk-* units from deploy/systemd/ or the
# older codeprovenance-* units; only enabled units are acted on.
# =============================================================================

BACKEND_UNITS=(
    codeprovenance-backend codeprovenance-celery codeprovenance-embedding
    integritydesk-backend integritydesk-worker integritydesk-analysis-worker integritydesk-embedding
)
DASHBOARD_UNITS=(codeprovenance-dashboard integritydesk-dashboard)

# Print the enabled units among the given names, one per line.
enabled_units() {
    local u
    for u in "$@"; do
        systemctl is-enabled --quiet "$u" 2>/dev/null && echo "$u"
    done
    return 0
}
