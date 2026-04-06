#!/bin/bash
# Restart all IntegrityDesk services
# Usage: ./scripts/restart.sh [dashboard_port] [website_port]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Stopping all running IntegrityDesk services..."

# Kill all existing processes
pkill -f "uvicorn src.api.server:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

# Wait for processes to terminate
sleep 2

# Double check and force kill any remaining
pkill -9 -f "uvicorn src.api.server:app" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true

echo "All services stopped."
echo ""

# Start all services again
exec "$PROJECT_DIR/scripts/start.sh" "$@"