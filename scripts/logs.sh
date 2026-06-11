#!/bin/bash
# View live logs for running services
# Usage: ./scripts/logs.sh [backend|dashboard]

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_DIR="$PROJECT_DIR/logs"

case "${1:-all}" in
  backend)
    echo "Following backend API logs..."
    tail -f "$LOG_DIR/backend.log" 2>/dev/null || echo "Backend log file not found"
    ;;
  embedding)
    echo "Following embedding server logs..."
    tail -f "$LOG_DIR/embedding.log" 2>/dev/null || echo "Embedding log file not found"
    ;;
  dashboard)
    echo "Following dashboard logs..."
    tail -f "$LOG_DIR/dashboard.log" 2>/dev/null || echo "Dashboard log file not found"
    ;;
  *)
    echo "Usage: ./scripts/logs.sh [backend|embedding|dashboard]"
    echo ""
    ./scripts/status.sh
    ;;
esac
