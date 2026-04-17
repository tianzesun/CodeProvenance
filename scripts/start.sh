#!/bin/bash
# IntegrityDesk - Robust Startup Script
# Backend + Embedding Server + Next.js Dashboard

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env.local"

# ----------------------------
# Load environment variables
# ----------------------------
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ''|\#*) continue ;;
        esac
        export "$line"
    done < "$ENV_FILE"
fi

# ----------------------------
# Config
# ----------------------------
DASHBOARD_PORT="${1:-${PORT:-3000}}"
BACKEND_PORT="${2:-${BACKEND_PORT:-8000}}"
EMBEDDING_PORT="${EMBEDDING_PORT:-8001}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
EMBEDDING_URL="http://${BACKEND_HOST}:${EMBEDDING_PORT}"

VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
DASHBOARD_DIR="$PROJECT_DIR/src/frontend"

BACKEND_LOG="$PROJECT_DIR/backend.log"
EMBEDDING_LOG="$PROJECT_DIR/embedding.log"

echo "============================================"
echo "  IntegrityDesk - Startup"
echo "============================================"
echo ""
echo "Backend API:    $BACKEND_URL"
echo "Embedding API:  $EMBEDDING_URL"
echo "Dashboard:      http://localhost:$DASHBOARD_PORT"
echo ""

# ----------------------------
# Ensure venv exists
# ----------------------------
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# ----------------------------
# Install backend deps if needed
# ----------------------------
echo "Ensuring Python dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip >/dev/null
"$VENV_PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt" >/dev/null

# ----------------------------
# Database init
# ----------------------------
echo "Initializing database..."
cd "$PROJECT_DIR"
"$VENV_PYTHON" -c "from src.backend.config.database import init_db; init_db()"
echo ""

# ----------------------------
# BACKEND START
# ----------------------------
echo "Starting backend..."

if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
    echo "✔ Backend already running"
else
    nohup "$VENV_PYTHON" -m uvicorn src.backend.api.server:app \
        --host 127.0.0.1 \
        --port "$BACKEND_PORT" \
        --log-level warning > "$BACKEND_LOG" 2>&1 &

    sleep 2
fi

# ----------------------------
# EMBEDDING START (FIXED)
# ----------------------------
echo "Starting embedding server..."

if lsof -i :$EMBEDDING_PORT >/dev/null 2>&1; then
    echo "✔ Embedding API already running"
else
    nohup "$VENV_PYTHON" -m uvicorn src.backend.services.embedding_server:app \
        --host 127.0.0.1 \
        --port "$EMBEDDING_PORT" \
        --log-level info > "$EMBEDDING_LOG" 2>&1 &

    echo "Waiting for embedding model to be ready..."

    for i in {1..30}; do
        if curl -s "http://$BACKEND_HOST:$EMBEDDING_PORT/health" | grep -q "healthy" && [ "$(lsof -i :$EMBEDDING_PORT >/dev/null 2>&1 && echo 1 || echo 0)" = "1" ]; then
            echo "✔ Embedding API ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Embedding API timed out during model load"
            echo "---- Last logs ----"
            tail -n 30 "$EMBEDDING_LOG"
            exit 1
        fi
        sleep 1
    done
fi

# ----------------------------
# DASHBOARD START
# ----------------------------
echo "Starting dashboard..."

cd "$DASHBOARD_DIR"

export PORT="$DASHBOARD_PORT"
export API_URL="$BACKEND_URL"
export NEXT_PUBLIC_API_URL="$BACKEND_URL"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

if [ "${DASHBOARD_MODE:-prod}" = "dev" ]; then
    echo "Running Next.js in DEV mode..."
    nohup npx next dev -p "$DASHBOARD_PORT" > "$PROJECT_DIR/dashboard.log" 2>&1 &
else
    echo "Building Next.js..."
    npx next build

    echo "Running Next.js in PROD mode..."
    nohup npx next start -p "$DASHBOARD_PORT" > "$PROJECT_DIR/dashboard.log" 2>&1 &
fi

sleep 2

# ----------------------------
# FINAL CHECK
# ----------------------------
echo ""
echo "Services ready:"
echo "  Backend API:   $BACKEND_URL"
echo "  Embedding API: $EMBEDDING_URL"
echo "  Dashboard:     http://localhost:$DASHBOARD_PORT"
echo ""
echo "Logs:"
echo "  Backend:   $BACKEND_LOG"
echo "  Embedding: $EMBEDDING_LOG"
echo "  Dashboard:  dashboard.log"
echo ""
echo "Startup complete ✔"