#!/bin/bash
# Check status of all IntegrityDesk services
# Usage: ./scripts/status.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "IntegrityDesk Service Status"
echo "=============================="
echo ""

# Check backend API
BACKEND_PID=$(pgrep -f "uvicorn src.api.server:app" 2>/dev/null || echo "")
if [ -n "$BACKEND_PID" ]; then
    echo "✅ Backend API:     RUNNING (PID: $BACKEND_PID)"
    echo "                   Listening on http://localhost:8500"
else
    echo "❌ Backend API:     STOPPED"
fi

# Check dashboard
DASHBOARD_PID=$(pgrep -f "next dev" | grep -v "official-site" 2>/dev/null || echo "")
if [ -n "$DASHBOARD_PID" ]; then
    DASHBOARD_PORT=$(ss -tulpn | grep "$DASHBOARD_PID" | grep LISTEN | awk '{print $5}' | cut -d: -f2 | head -1)
    echo "✅ Dashboard:       RUNNING (PID: $DASHBOARD_PID)"
    if [ -n "$DASHBOARD_PORT" ]; then
        echo "                   Listening on http://localhost:$DASHBOARD_PORT"
    else
        echo "                   Listening on http://localhost:3000 / 3003"
    fi
else
    echo "❌ Dashboard:       STOPPED"
fi

# Check official website
WEBSITE_PID=$(pgrep -f "next dev" | grep "official-site" 2>/dev/null || echo "")
if [ -n "$WEBSITE_PID" ]; then
    WEBSITE_PORT=$(ss -tulpn | grep "$WEBSITE_PID" | grep LISTEN | awk '{print $5}' | cut -d: -f2 | head -1)
    echo "✅ Official Site:   RUNNING (PID: $WEBSITE_PID)"
    if [ -n "$WEBSITE_PORT" ]; then
        echo "                   Listening on http://localhost:$WEBSITE_PORT"
    else
        echo "                   Listening on http://localhost:3004"
    fi
else
    echo "❌ Official Site:   STOPPED"
fi

echo ""
echo "Open ports:"
ss -tulpn 2>/dev/null | grep -E "(8500|3000|3003|3004)" | awk '{print "  "$5}' | sort
echo ""
