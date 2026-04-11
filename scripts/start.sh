#!/bin/bash
# Start IntegrityDesk - Backend API + Next.js Dashboard
# Usage: ./scripts/start.sh [dashboard_port]
# Default: Backend on 8500, Dashboard on 3003

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_PORT="${1:-3003}"
BACKEND_PORT=8500
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
DATABASE_URL="${DATABASE_URL:-sqlite:///./codeprovenance.db}"

echo "============================================"
echo "  IntegrityDesk - Academic Integrity Platform"
echo "============================================"
echo ""
echo "Backend API:  http://localhost:${BACKEND_PORT}"
echo "Dashboard:    http://localhost:${DASHBOARD_PORT}"
echo ""

# Install dashboard dependencies
DASHBOARD_DIR="$PROJECT_DIR/src/web/dashboard-ui"
if [ ! -d "$DASHBOARD_DIR/node_modules" ]; then
    echo "Installing dashboard dependencies..."
    cd "$DASHBOARD_DIR" && npm install
    echo ""
fi

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
    echo "Installing Python dependencies..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt"
    echo ""
fi

echo "Initializing database schema..."
cd "$PROJECT_DIR"
DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" -c "import src.models.database; from src.config.database import init_db; init_db()"
echo ""

echo "Starting backend API on port ${BACKEND_PORT}..."
cd "$PROJECT_DIR"
DATABASE_URL="$DATABASE_URL" "$VENV_PYTHON" -m uvicorn src.api.server:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" --log-level warning &
BACKEND_PID=$!
sleep 2

echo "Starting Next.js dashboard on port ${DASHBOARD_PORT}..."
cd "$DASHBOARD_DIR"
npx next dev -p "$DASHBOARD_PORT" &
DASHBOARD_PID=$!

cleanup() {
    echo ""; echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $DASHBOARD_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

echo ""
echo "Services ready:"
echo "  Backend API: http://localhost:${BACKEND_PORT}"
echo "  Dashboard:   http://localhost:${DASHBOARD_PORT}"
echo ""
echo "Press Ctrl+C to stop"; echo ""
wait
