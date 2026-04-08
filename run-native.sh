#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/venv"
DASHBOARD_DIR="${ROOT_DIR}/src/web/dashboard-ui"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
API_URL="${NEXT_PUBLIC_API_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"

backend_pid=""
frontend_pid=""

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

cleanup() {
  local exit_code=$?

  if [[ -n "${frontend_pid}" ]] && kill -0 "${frontend_pid}" >/dev/null 2>&1; then
    kill "${frontend_pid}" >/dev/null 2>&1 || true
  fi

  if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" >/dev/null 2>&1; then
    kill "${backend_pid}" >/dev/null 2>&1 || true
  fi

  wait >/dev/null 2>&1 || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

require_cmd python3
require_cmd npm

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "${VENV_DIR}"
fi

if [[ ! -x "${VENV_DIR}/bin/uvicorn" ]]; then
  echo "Installing Python dependencies..."
  "${VENV_DIR}/bin/pip" install -r "${ROOT_DIR}/requirements.txt"
fi

if [[ ! -x "${DASHBOARD_DIR}/node_modules/.bin/next" ]]; then
  echo "Installing dashboard dependencies..."
  (
    cd "${DASHBOARD_DIR}"
    npm install
  )
fi

echo "Starting backend at ${API_URL} ..."
(
  cd "${ROOT_DIR}"
  exec "${VENV_DIR}/bin/uvicorn" src.api.server:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --reload
) &
backend_pid=$!

echo "Starting dashboard at http://${FRONTEND_HOST}:${FRONTEND_PORT} ..."
(
  cd "${DASHBOARD_DIR}"
  NEXT_PUBLIC_API_URL="${API_URL}" \
  exec "${DASHBOARD_DIR}/node_modules/.bin/next" dev \
    --hostname "${FRONTEND_HOST}" \
    --port "${FRONTEND_PORT}"
) &
frontend_pid=$!

echo
echo "IntegrityDesk is starting up."
echo "Dashboard: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "API docs:   http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo "Press Ctrl+C to stop both services."
echo

wait -n "${backend_pid}" "${frontend_pid}"
