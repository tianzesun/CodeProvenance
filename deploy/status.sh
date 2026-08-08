#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Status of all services
# =============================================================================

set -uo pipefail

SERVICES="integritydesk-backend integritydesk-dashboard integritydesk-worker"

if systemctl list-unit-files integritydesk-embedding.service >/dev/null 2>&1; then
    SERVICES="$SERVICES integritydesk-embedding"
fi

echo "IntegrityDesk Service Status"
echo "============================"
echo ""

for svc in $SERVICES; do
    if systemctl is-active --quiet "$svc"; then
        port=""
        case "$svc" in
            *backend*)   port=":8000" ;;
            *dashboard*) port=":3000" ;;
            *worker*)    port="" ;;
            *embedding*) port=":8001" ;;
        esac
        echo "  ✅ $svc     ACTIVE (systemd)${port:+ -> $port}"
    else
        echo "  ❌ $svc     INACTIVE"
    fi
done

echo ""
echo "Recent failures (if any):"
journalctl -u integritydesk-backend --since "10 min ago" --no-pager -p err | tail -5 || true
echo ""
echo "web server: $(systemctl is-active apache2 2>/dev/null || systemctl is-active nginx 2>/dev/null || echo 'unknown')"
echo "redis: $(systemctl is-active redis-server)"
