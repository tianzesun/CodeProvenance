#!/bin/bash
# Restart all IntegrityDesk services
# Usage: ./scripts/restart.sh [dashboard_port] [backend_port]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DASHBOARD_PORT="${1:-3000}"
BACKEND_PORT="${2:-8000}"
EMBEDDING_PORT="${EMBEDDING_PORT:-8001}"

echo "Stopping all running IntegrityDesk services (ports: $DASHBOARD_PORT, $BACKEND_PORT, $EMBEDDING_PORT)..."

# Kill by process name (Next.js 16 + React 19 compatible patterns)
pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -f "uvicorn src.backend.services.embedding_server:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true

# Wait for processes to terminate
sleep 2

# Force kill any survivors
pkill -9 -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -9 -f "uvicorn src.backend.services.embedding_server:app" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true
pkill -9 -f "next start" 2>/dev/null || true
pkill -9 -f "next-server" 2>/dev/null || true

# Kill by the actual ports being used (not hardcoded)
for port in "$DASHBOARD_PORT" "$BACKEND_PORT" "$EMBEDDING_PORT"; do
    if lsof -i :"$port" >/dev/null 2>&1; then
        echo "Force killing process on port $port..."
        lsof -ti :"$port" | xargs kill -9 2>/dev/null || true
    fi
done

echo "All services stopped."
echo ""

# Start all services again
exec "$PROJECT_DIR/scripts/start.sh" "$@"