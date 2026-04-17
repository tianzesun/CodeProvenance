#!/bin/bash
# View live logs for running services
# Usage: ./scripts/logs.sh [backend|dashboard]

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-all}" in
  backend)
    echo "Following backend API logs..."
    journalctl -f _PID=$(pgrep -f "uvicorn src.backend.api.server:app" 2>/dev/null) 2>/dev/null || echo "Backend not running"
    ;;
  embedding)
    echo "Following embedding server logs..."
    journalctl -f _PID=$(pgrep -f "uvicorn embedding_server:app" 2>/dev/null) 2>/dev/null || echo "Embedding server not running"
    ;;
  dashboard)
    echo "Following dashboard logs..."
    journalctl -f _PID=$(pgrep -f "next dev" 2>/dev/null) 2>/dev/null || echo "Dashboard not running"
    ;;
  *)
    echo "Usage: ./scripts/logs.sh [backend|embedding|dashboard]"
    echo ""
    ./scripts/status.sh
    ;;
esac
