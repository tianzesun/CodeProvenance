#!/bin/bash
# Start IntegrityDesk Professor Dashboard
# Usage: ./scripts/start_professor_dashboard.sh [port]
# Default port: 8500

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-8500}"

echo "============================================"
echo "  IntegrityDesk Professor Dashboard"
echo "============================================"
echo ""
echo "Starting server on http://localhost:${PORT}"
echo "Press Ctrl+C to stop"
echo ""

if [ -d "$PROJECT_DIR/venv" ]; then
    "$PROJECT_DIR/venv/bin/python" -m uvicorn src.web.professor_dashboard:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --log-level info
else
    python3 -m uvicorn src.web.professor_dashboard:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --log-level info
fi
