#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - Status of all services
# =============================================================================

set -uo pipefail

# shellcheck source=units.sh
source "$(dirname "${BASH_SOURCE[0]}")/units.sh"

mapfile -t SERVICES < <(enabled_units "${BACKEND_UNITS[@]}" "${DASHBOARD_UNITS[@]}")

echo "IntegrityDesk Service Status"
echo "============================"
echo ""

[ "${#SERVICES[@]}" -gt 0 ] || echo "  No IntegrityDesk services are enabled."

for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc"; then
        port=""
        case "$svc" in
            *backend*)   port=":8000" ;;
            *dashboard*) port=":3000" ;;
            *worker*|*celery*) port="" ;;
            *embedding*) port=":8001" ;;
        esac
        echo "  ✅ $svc     ACTIVE (systemd)${port:+ -> $port}"
    else
        echo "  ❌ $svc     INACTIVE"
    fi
done

echo ""
echo "Recent failures (if any):"
for svc in "${SERVICES[@]}"; do
    case "$svc" in
        *-backend) journalctl -u "$svc" --since "10 min ago" --no-pager -p err | tail -5 || true ;;
    esac
done
echo ""
web="unknown"
for ws in apache2 nginx; do
    systemctl is-active --quiet "$ws" && { web="$ws active"; break; }
done
echo "web server: $web"
echo "redis: $(systemctl is-active redis-server)"
