#!/bin/bash
# Start CodeProvenance Benchmark Dashboard

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$PROJECT_DIR/scripts"
cd "$SCRIPT_DIR"

PORT="${1:-5000}"

echo "Starting CodeProvenance Benchmark Dashboard..."
echo "Dashboard: http://localhost:${PORT}"
echo ""

if [ -d "$PROJECT_DIR/venv" ]; then
    "$PROJECT_DIR/venv/bin/python" web_dashboard.py --port "$PORT" --debug
else
    python3 web_dashboard.py --port "$PORT" --debug
fi
