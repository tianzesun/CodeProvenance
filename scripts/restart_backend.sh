#!/bin/bash
# Restart the backend API and the Celery worker, leaving the dashboard and
# embedding server running. Use after pulling backend changes.
# Usage: ./scripts/restart_backend.sh [dashboard_port] [backend_port]
#
# The worker must restart together with the API: a worker left on old code
# imports the new files from disk per task and fails every job (seen as
# uploads stuck at "queued").

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BACKEND_PORT="${2:-8000}"
GPU_CONTAINER="integritydesk-backend-gpu"

echo "Stopping backend API and celery worker (port: $BACKEND_PORT)..."

pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -f "celery.*celery_app" 2>/dev/null || true

# BACKEND_GPU=1 runs both inside the GPU holder container. Stop the
# processes, not the container: start.sh reuses the running holder.
if command -v docker >/dev/null 2>&1 \
    && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$GPU_CONTAINER"; then
    echo "Stopping backend processes in GPU container $GPU_CONTAINER..."
    docker exec "$GPU_CONTAINER" pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
    docker exec "$GPU_CONTAINER" pkill -f "celery.*celery_app" 2>/dev/null || true
fi

# Wait for processes to terminate
sleep 2

# Force kill any survivors
pkill -9 -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
pkill -9 -f "celery.*celery_app" 2>/dev/null || true

if lsof -i :"$BACKEND_PORT" >/dev/null 2>&1; then
    echo "Force killing process on port $BACKEND_PORT..."
    lsof -ti :"$BACKEND_PORT" | xargs kill -9 2>/dev/null || true
fi

echo "Backend stopped."
echo ""

# start.sh skips services that are still running (embedding server) and
# brings the backend and worker back up the same way it would at boot.
SKIP_DASHBOARD=1 exec "$PROJECT_DIR/scripts/start.sh" "$@"
