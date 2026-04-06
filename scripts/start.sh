#!/bin/bash
# Start IntegrityDesk - Backend API + Next.js Dashboard + Official Website
# Usage: ./scripts/start.sh [dashboard_port] [website_port]
# Default: Backend on 8500, Dashboard on 3003, Website on 3004

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_PORT="${1:-3003}"
WEBSITE_PORT="${2:-3004}"
BACKEND_PORT=8500

echo "============================================"
echo "  IntegrityDesk - Academic Integrity Platform"
echo "============================================"
echo ""
echo "Backend API:  http://localhost:${BACKEND_PORT}"
echo "Dashboard:    http://localhost:${DASHBOARD_PORT}"
echo "Website:      http://localhost:${WEBSITE_PORT}"
echo ""

# Install dashboard dependencies
DASHBOARD_DIR="$PROJECT_DIR/src/web/dashboard-ui"
if [ ! -d "$DASHBOARD_DIR/node_modules" ]; then
    echo "Installing dashboard dependencies..."
    cd "$DASHBOARD_DIR" && npm install
    echo ""
fi

# Install website dependencies
WEBSITE_DIR="$PROJECT_DIR/src/web/official-site"
if [ ! -d "$WEBSITE_DIR/node_modules" ]; then
    echo "Installing official website dependencies..."
    cd "$WEBSITE_DIR" && npm install
    echo ""
fi

echo "Starting backend API on port ${BACKEND_PORT}..."
cd "$PROJECT_DIR"
"$PROJECT_DIR/venv/bin/python" -m uvicorn src.api.server:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" --log-level warning &
BACKEND_PID=$!
sleep 2

echo "Starting Next.js dashboard on port ${DASHBOARD_PORT}..."
cd "$DASHBOARD_DIR"
npx next dev -p "$DASHBOARD_PORT" &
DASHBOARD_PID=$!
sleep 1

echo "Starting official product website on port ${WEBSITE_PORT}..."
cd "$WEBSITE_DIR"
npx next dev -p "$WEBSITE_PORT" &
WEBSITE_PID=$!

cleanup() {
    echo ""; echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $DASHBOARD_PID 2>/dev/null
    kill $WEBSITE_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

echo ""
echo "Services ready:"
echo "  Backend API: http://localhost:${BACKEND_PORT}"
echo "  Dashboard:   http://localhost:${DASHBOARD_PORT}"
echo "  Website:     http://localhost:${WEBSITE_PORT}"
echo ""
echo "Press Ctrl+C to stop"; echo ""
wait
