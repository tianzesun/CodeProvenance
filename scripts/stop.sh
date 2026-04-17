#!/bin/bash
# Robust stop script for IntegrityDesk

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "======================================"
echo "  Stopping IntegrityDesk Services"
echo "======================================"

# ----------------------------
# Function: kill by port safely
# ----------------------------
kill_port() {
    PORT=$1
    NAME=$2

    if lsof -i :"$PORT" >/dev/null 2>&1; then
        echo "Stopping $NAME on port $PORT..."

        PIDS=$(lsof -t -i :"$PORT")
        if [ ! -z "$PIDS" ]; then
            kill $PIDS 2>/dev/null || true
            sleep 1
            kill -9 $PIDS 2>/dev/null || true
        fi
    else
        echo "$NAME already stopped"
    fi
}

# ----------------------------
# Stop by ports (primary method)
# ----------------------------
kill_port 3000 "Dashboard"
kill_port 8000 "Backend API"
kill_port 8001 "Embedding API"

# ----------------------------
# Fallback cleanup (process names)
# ----------------------------
echo ""
echo "Cleaning remaining processes..."

pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -f "uvicorn embedding_server:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true

sleep 1

echo ""
echo "Verifying cleanup..."

# ----------------------------
# Verification
# ----------------------------
check_port() {
    if lsof -i :"$1" >/dev/null 2>&1; then
        echo "❌ Port $1 still in use"
    else
        echo "✔ Port $1 free"
    fi
}

check_port 3000
check_port 8000
check_port 8001

echo ""
echo "All IntegrityDesk services stopped ✔"