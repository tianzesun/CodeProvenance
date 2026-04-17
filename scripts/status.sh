#!/bin/bash
# Check status of all IntegrityDesk services
# Usage: ./scripts/status.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "IntegrityDesk Service Status"
echo "=============================="
echo ""

# Check backend API
BACKEND_PID=$(pgrep -f "uvicorn src.backend.api.server:app" 2>/dev/null || echo "")
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

# Check embedding server
EMBEDDING_PID=$(pgrep -f "uvicorn embedding_server:app" 2>/dev/null || echo "")
if [ -n "$EMBEDDING_PID" ]; then
    EMBEDDING_PORT=$(ss -tulpn | grep "$EMBEDDING_PID" | grep LISTEN | awk '{print $5}' | cut -d: -f2 | head -1)
    echo "✅ Embedding API:   RUNNING (PID: $EMBEDDING_PID)"
    if [ -n "$EMBEDDING_PORT" ]; then
        echo "                   Listening on http://localhost:$EMBEDDING_PORT"
        echo "                   Health: http://localhost:$EMBEDDING_PORT/health"
    else
        echo "                   Listening on configured embedding port"
    fi
else
    echo "❌ Embedding API:   STOPPED"
fi

# Check dashboard
DASHBOARD_PID=$(pgrep -f "next-server" 2>/dev/null | head -1 || echo "")
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
for PID in $BACKEND_PID $EMBEDDING_PID $DASHBOARD_PID; do
    if [ -n "$PID" ]; then
        ss -tulpn 2>/dev/null | grep "$PID" | grep LISTEN | awk '{print "  "$5}'
    fi
done | sort -u
echo ""
