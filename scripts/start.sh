#!/bin/bash
# Start IntegrityDesk - Backend API + Next.js Dashboard
# Usage: ./scripts/start.sh [dashboard_port] [backend_port]
# Default: Backend on 8000, Dashboard on 3000
# Set DASHBOARD_MODE=dev to use Next.js development mode.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env.local"

if [ -f "$ENV_FILE" ]; then
    # Load dotenv-style entries without shell-evaluating special characters in values.
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ''|\#*)
                continue
                ;;
        esac
        export "$line"
    done < "$ENV_FILE"
fi

DASHBOARD_PORT="${1:-${PORT:-3000}}"
BACKEND_PORT="${2:-${BACKEND_PORT:-8000}}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_URL="${BACKEND_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
DATABASE_URL="${DATABASE_URL:-sqlite:///./codeprovenance.db}"

echo "============================================"
echo "  IntegrityDesk - Academic Integrity Platform"
echo "============================================"
echo ""
echo "Backend API:  ${BACKEND_URL}"
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

cd "$DASHBOARD_DIR"
export PORT="$DASHBOARD_PORT"
export BACKEND_URL
export API_URL="$BACKEND_URL"
export NEXT_PUBLIC_API_URL="$BACKEND_URL"
DASHBOARD_MODE="${DASHBOARD_MODE:-prod}"

if [ "$DASHBOARD_MODE" = "dev" ]; then
    echo "Starting Next.js dashboard in development mode on port ${DASHBOARD_PORT}..."
    npx next dev -p "$DASHBOARD_PORT" &
else
    echo "Building Next.js dashboard for stable startup..."
    npx next build
    echo "Starting Next.js dashboard in production mode on port ${DASHBOARD_PORT}..."
    npx next start -p "$DASHBOARD_PORT" &
fi
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
echo "  Backend API: ${BACKEND_URL}"
echo "  Dashboard:   http://localhost:${DASHBOARD_PORT}"
echo ""
echo "Press Ctrl+C to stop"; echo ""
wait
