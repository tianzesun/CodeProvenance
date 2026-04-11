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
    BACKEND_PORT=$(ss -tulpn | grep "$BACKEND_PID" | grep LISTEN | awk '{print $5}' | cut -d: -f2 | head -1)
    echo "✅ Backend API:     RUNNING (PID: $BACKEND_PID)"
    if [ -n "$BACKEND_PORT" ]; then
        echo "                   Listening on http://localhost:$BACKEND_PORT"
        echo "                   API docs: http://localhost:$BACKEND_PORT/docs"
    else
        echo "                   Listening on configured backend port"
    fi
else
    echo "❌ Backend API:     STOPPED"
fi

# Check dashboard
DASHBOARD_PID=$(pgrep -f "next dev" 2>/dev/null || echo "")
if [ -n "$DASHBOARD_PID" ]; then
    DASHBOARD_PORT=$(ss -tulpn | grep "$DASHBOARD_PID" | grep LISTEN | awk '{print $5}' | cut -d: -f2 | head -1)
    echo "✅ Dashboard:       RUNNING (PID: $DASHBOARD_PID)"
    if [ -n "$DASHBOARD_PORT" ]; then
        echo "                   Listening on http://localhost:$DASHBOARD_PORT"
    else
        echo "                   Listening on http://localhost:3000"
    fi
else
    echo "❌ Dashboard:       STOPPED"
fi

echo ""
echo "Open ports:"
for PID in $BACKEND_PID $DASHBOARD_PID; do
    if [ -n "$PID" ]; then
        ss -tulpn 2>/dev/null | grep "$PID" | grep LISTEN | awk '{print "  "$5}'
    fi
done | sort -u
echo ""
