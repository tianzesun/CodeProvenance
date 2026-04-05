#!/bin/bash
# Start IntegrityDesk - Backend API + Next.js Dashboard
# Usage: ./scripts/start.sh [frontend_port]
# Default: Backend on 8500, Frontend on 3000

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_PORT="${1:-3000}"
BACKEND_PORT=8500

echo "============================================"
echo "  IntegrityDesk - Academic Integrity Platform"
echo "============================================"
echo ""
echo "Backend API:  http://localhost:${BACKEND_PORT}"
echo "Frontend UI:  http://localhost:${FRONTEND_PORT}"
echo ""

UI_DIR="$PROJECT_DIR/src/web/dashboard-ui"
if [ ! -d "$UI_DIR/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$UI_DIR" && npm install
    echo ""
fi

echo "Starting backend API on port ${BACKEND_PORT}..."
cd "$PROJECT_DIR"
"$PROJECT_DIR/venv/bin/python" -m uvicorn src.api.server:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" --log-level warning &
BACKEND_PID=$!
sleep 2

echo "Starting Next.js dashboard on port ${FRONTEND_PORT}..."
cd "$UI_DIR"
npx next dev -p "$FRONTEND_PORT" &
FRONTEND_PID=$!

cleanup() {
    echo ""; echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit 0
}
trap cleanup INT TERM

echo ""; echo "Dashboard ready at http://localhost:${FRONTEND_PORT}"
echo "Press Ctrl+C to stop"; echo ""
wait
