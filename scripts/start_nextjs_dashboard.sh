#!/bin/bash
# Start IntegrityDesk Next.js Professor Dashboard
# Usage: ./scripts/start_nextjs_dashboard.sh [port]
# Default port: 3000
# Requires: npm install (first time only)

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$PROJECT_DIR/src/web/dashboard-ui"
PORT="${1:-3000}"

echo "============================================"
echo "  IntegrityDesk Professor Dashboard (Next.js)"
echo "============================================"
echo ""

if [ ! -d "$UI_DIR/node_modules" ]; then
    echo "Installing dependencies..."
    cd "$UI_DIR" && npm install
    echo ""
fi

echo "Starting Next.js dev server on http://localhost:${PORT}"
echo "Backend API: http://localhost:8500"
echo "Press Ctrl+C to stop"
echo ""

cd "$UI_DIR"
PORT="$PORT" npx next dev -p "$PORT"
