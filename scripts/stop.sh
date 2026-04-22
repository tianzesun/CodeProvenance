#!/bin/bash
#
# Robust IntegrityDesk Stop Script
# Hardened, reliable process cleanup for all service types
# Handles orphans, hung processes, process groups, and edge cases
#

set -uo pipefail
IFS=$'\n\t'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROJECT_DIR
readonly GRACE_PERIOD=3
readonly FORCE_WAIT=1

echo "======================================"
echo "  Stopping IntegrityDesk Services"
echo "======================================"

# -----------------------------------------------------------------------------
# Safely terminate processes with graceful fallback to kill -9
# -----------------------------------------------------------------------------
safe_kill() {
    local pids="$1"
    local name="$2"

    if [ -z "$pids" ]; then
        return 0
    fi

    echo "→ Terminating ${name} (pid: $pids)"

    # Send SIGTERM first (graceful shutdown)
    kill $pids 2>/dev/null || true

    # Wait for processes to exit cleanly
    for (( i=0; i<GRACE_PERIOD; i++ )); do
        alive=0
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                alive=1
                break
            fi
        done
        if [ "$alive" -eq 0 ]; then
            break
        fi
        sleep 0.5
    done

    # Send SIGKILL to any remaining hung processes
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  → Force killing unresponsive pid $pid"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done

    sleep $FORCE_WAIT
    return 0
}

# -----------------------------------------------------------------------------
# Kill all processes listening on a specific port
# -----------------------------------------------------------------------------
kill_port() {
    local port="$1"
    local name="$2"

    if ! command -v lsof >/dev/null 2>&1; then
        echo "⚠ lsof not found, skipping port detection"
        return 0
    fi

    local pids
    pids=$(lsof -t -i :"$port" 2>/dev/null | sort -u)

    if [ -z "$pids" ]; then
        echo "✔ $name (port $port) already stopped"
        return 0
    fi

    safe_kill "$pids" "$name"
}

# -----------------------------------------------------------------------------
# Kill process trees (entire process groups and children)
# -----------------------------------------------------------------------------
kill_process_tree() {
    local pattern="$1"
    local name="$2"

    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null | sort -u)

    if [ -z "$pids" ]; then
        return 0
    fi

    # Kill entire process groups to catch child processes, orphans, workers
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            local pgid
            pgid=$(ps -o pgid= "$pid" 2>/dev/null | tr -d ' ')
            if [ -n "$pgid" ] && [ "$pgid" -gt 1 ]; then
                kill -- "-$pgid" 2>/dev/null || true
            fi
        fi
    done

    safe_kill "$pids" "$name"
}

# -----------------------------------------------------------------------------
# Verify port is properly released
# -----------------------------------------------------------------------------
verify_port() {
    local port="$1"

    if lsof -i :"$port" >/dev/null 2>&1; then
        echo "❌ WARNING: Port $port still held by process"
        return 1
    else
        echo "✔ Port $port released"
        return 0
    fi
}

# -----------------------------------------------------------------------------
# Stop sequence
# -----------------------------------------------------------------------------
echo ""
echo "Stopping services by port:"
echo "--------------------------"

kill_port 3000 "Frontend Dashboard"
kill_port 8000 "Backend API Server"
kill_port 8001 "Embedding Server"

echo ""
echo "Cleaning up orphan processes:"
echo "-----------------------------"

kill_process_tree "uvicorn.*src.backend.api.server" "Backend Workers"
kill_process_tree "uvicorn.*embedding_server" "Embedding Workers"
kill_process_tree "next dev" "Next.js Dev Server"
kill_process_tree "next start" "Next.js Server"
kill_process_tree "next-server" "Next.js Workers"
kill_process_tree "python.*embedding_server" "Python Embedding Processes"

# Final cleanup for any stray python/uvicorn processes owned by this user
pkill -U "$UID" -x uvicorn 2>/dev/null || true
pkill -U "$UID" -f "python.*CodeProvenance" 2>/dev/null || true

sleep 1

echo ""
echo "Verification:"
echo "-------------"

exit_code=0
verify_port 3000 || exit_code=1
verify_port 8000 || exit_code=1
verify_port 8001 || exit_code=1

echo ""
if [ "$exit_code" -eq 0 ]; then
    echo "✅ All IntegrityDesk services stopped cleanly"
else
    echo "⚠ Some services may still be running. Run again for full cleanup."
fi

echo ""
echo "Done."
exit $exit_code