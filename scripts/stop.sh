#!/bin/bash
# Stop all IntegrityDesk services

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Stopping all IntegrityDesk services..."

# Graceful stop first
pkill -f "uvicorn src.api.server:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

# Wait for processes to exit
sleep 1

# Force kill any remaining
pkill -9 -f "uvicorn src.api.server:app" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true

echo "All IntegrityDesk services stopped."