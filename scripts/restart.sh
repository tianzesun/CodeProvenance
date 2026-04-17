#!/bin/bash
# Restart all IntegrityDesk services
# Usage: ./scripts/restart.sh [dashboard_port] [website_port]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Stopping all running IntegrityDesk services..."

# Kill all existing processes
pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -f "uvicorn embedding_server:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true

# Wait for processes to terminate
sleep 2

# Double check and force kill any remaining
pkill -9 -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -9 -f "uvicorn embedding_server:app" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true
pkill -9 -f "next start" 2>/dev/null || true
pkill -9 -f "next-server" 2>/dev/null || true

# Additional cleanup - kill by port if processes still exist
if lsof -i :3000 >/dev/null 2>&1; then
    echo "Force killing process on port 3000..."
    lsof -ti :3000 | xargs kill -9 2>/dev/null || true
fi
if lsof -i :8000 >/dev/null 2>&1; then
    echo "Force killing process on port 8000..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
fi
if lsof -i :8001 >/dev/null 2>&1; then
    echo "Force killing process on port 8001..."
    lsof -ti :8001 | xargs kill -9 2>/dev/null || true
fi

echo "All services stopped."
echo ""

# Start all services again
exec "$PROJECT_DIR/scripts/start.sh" "$@"