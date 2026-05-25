#!/bin/bash
# IntegrityDesk - Robust Startup Script
# Backend + Embedding Server + Next.js Dashboard

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/src/backend/.env.local"

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
DASHBOARD_PORT="${1:-${DASHBOARD_PORT:-3000}}"
BACKEND_PORT="${2:-${BACKEND_PORT:-8000}}"
EMBEDDING_PORT="${EMBEDDING_PORT:-8001}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
EMBEDDING_URL="http://${BACKEND_HOST}:${EMBEDDING_PORT}"

VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
DASHBOARD_DIR="$PROJECT_DIR/src/frontend"

BACKEND_LOG="$PROJECT_DIR/logs/backend.log"
EMBEDDING_LOG="$PROJECT_DIR/logs/embedding.log"

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
# Database init (hardened for remote DB flakiness)
# ----------------------------
if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
    echo "✔ Backend already running; skipping database init"
elif [ "${SKIP_DB_INIT:-}" = "1" ]; then
    echo "Skipping database init (SKIP_DB_INIT=1)"
else
    echo "Initializing database..."
    cd "$PROJECT_DIR"

    DB_INIT_ATTEMPTS=3
    DB_INIT_SUCCESS=0
    for attempt in $(seq 1 $DB_INIT_ATTEMPTS); do
        if "$VENV_PYTHON" -c "from src.backend.config.database import init_db; init_db()" 2>&1; then
            DB_INIT_SUCCESS=1
            break
        else
            echo "  Database init attempt $attempt/$DB_INIT_ATTEMPTS failed"
            if [ $attempt -lt $DB_INIT_ATTEMPTS ]; then
                echo "  Retrying in 3s..."
                sleep 3
            fi
        fi
    done

    if [ $DB_INIT_SUCCESS -eq 1 ]; then
        echo "✔ Database initialized"
    else
        echo "⚠️  Database init failed after $DB_INIT_ATTEMPTS attempts (continuing anyway)"
        echo "    You can set SKIP_DB_INIT=1 to skip this step"
    fi
    echo ""
fi

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

    echo "Waiting for embedding server to start..."

    for i in {1..30}; do
        if curl -s "http://$BACKEND_HOST:$EMBEDDING_PORT/health" >/dev/null 2>&1; then
            echo "✔ Embedding API ready (model loads on first request)"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Embedding API failed to start"
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
export HOST="127.0.0.1"
export API_URL="$BACKEND_URL"
export NEXT_PUBLIC_API_URL="$BACKEND_URL"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
else
    # After React 19 upgrade, ensure we are not running on stale React 18 modules
    REACT_VERSION=$(node -e "console.log(require('react/package.json').version)" 2>/dev/null || echo "0.0.0")
    if [[ "$REACT_VERSION" == 18.* ]]; then
        echo "⚠️  Detected React $REACT_VERSION in node_modules (expected 19.x after upgrade)"
        echo "   Running clean install for React 19..."
        rm -rf node_modules package-lock.json
        npm install
    fi
fi

if [ "${DASHBOARD_MODE:-prod}" = "dev" ]; then
    echo "Running Next.js in DEV mode (Next 16 + React 19)..."
    nohup npx next dev --port "$DASHBOARD_PORT" --hostname 127.0.0.1 > "$PROJECT_DIR/logs/dashboard.log" 2>&1 &
else
    echo "Building Next.js..."
    npx next build

    echo "Running Next.js in PROD mode..."
    nohup npx next start --port "$DASHBOARD_PORT" --hostname 127.0.0.1 > "$PROJECT_DIR/logs/dashboard.log" 2>&1 &
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
echo "  Dashboard:  $PROJECT_DIR/logs/dashboard.log"
echo ""
echo "Startup complete ✔"
