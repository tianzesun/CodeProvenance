#!/bin/bash
# IntegrityDesk - Robust Startup Script
# Backend + Embedding Server + Next.js Dashboard
#
# GPU backend (ARM/Blackwell hosts without a pip CUDA torch wheel):
#   BACKEND_GPU=1 ./scripts/start.sh   (image override: GPU_IMAGE=...)

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/src/backend/.env.local"

# ----------------------------
# Load environment variables
# ----------------------------
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ''|\#*) continue ;;
        esac
        export "$line"
    done < "$ENV_FILE"
fi

# ----------------------------
# Config
# ----------------------------
DASHBOARD_PORT="${1:-${DASHBOARD_PORT:-3000}}"
BACKEND_PORT="${2:-${BACKEND_PORT:-8000}}"
EMBEDDING_PORT="${EMBEDDING_PORT:-8001}"

# GPU backend (NVIDIA ARM/Blackwell hosts where pip has no CUDA torch wheel).
# Opt in with BACKEND_GPU=1 (override the image with GPU_IMAGE=...).
# A container left over from a previous GPU run is reused automatically;
# BACKEND_GPU=0 forces the host venv backend.
GPU_CONTAINER="integritydesk-backend-gpu"
GPU_IMAGE="${GPU_IMAGE:-nvcr.io/nvidia/pytorch:25.02-py3}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
EMBEDDING_URL="http://${BACKEND_HOST}:${EMBEDDING_PORT}"

VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
DASHBOARD_DIR="$PROJECT_DIR/src/frontend"

BACKEND_LOG="$PROJECT_DIR/logs/backend.log"
EMBEDDING_LOG="$PROJECT_DIR/logs/embedding.log"

echo "============================================"
echo "  IntegrityDesk - Startup"
echo "============================================"
echo ""
echo "Backend API:    $BACKEND_URL"
echo "Embedding API:  $EMBEDDING_URL"
echo "Dashboard:      http://localhost:$DASHBOARD_PORT"
echo ""

# ----------------------------
# Ensure venv exists
# ----------------------------
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# ----------------------------
# Install backend deps if needed
# ----------------------------
echo "Ensuring Python dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip >/dev/null
"$VENV_PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt" >/dev/null

# ----------------------------
# Database init (hardened for remote DB flakiness)
# ----------------------------
if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
    echo "✔ Backend already running; skipping database init"
elif [ "${SKIP_DB_INIT:-}" = "1" ]; then
    echo "Skipping database init (SKIP_DB_INIT=1)"
else
    echo "Initializing database..."
    cd "$PROJECT_DIR"

    DB_INIT_ATTEMPTS=3
    DB_INIT_SUCCESS=0
    for attempt in $(seq 1 $DB_INIT_ATTEMPTS); do
        if "$VENV_PYTHON" -c "from src.backend.config.database import init_db; init_db(['src.backend.models.database'])" 2>&1; then
            DB_INIT_SUCCESS=1
            break
        else
            echo "  Database init attempt $attempt/$DB_INIT_ATTEMPTS failed"
            if [ $attempt -lt $DB_INIT_ATTEMPTS ]; then
                echo "  Retrying in 3s..."
                sleep 3
            fi
        fi
    done

    if [ $DB_INIT_SUCCESS -eq 1 ]; then
        echo "✔ Database initialized"
    else
        echo "⚠️  Database init failed after $DB_INIT_ATTEMPTS attempts (continuing anyway)"
        echo "    You can set SKIP_DB_INIT=1 to skip this step"
    fi
    echo ""
fi

# ----------------------------
# BACKEND START (host venv, or NVIDIA GPU container when requested)
# ----------------------------
mkdir -p "$PROJECT_DIR/logs"

GPU_WANTS_HOST=1
if [ "${BACKEND_GPU:-}" = "1" ]; then
    GPU_WANTS_HOST=0
elif [ "${BACKEND_GPU:-}" != "0" ] \
    && command -v docker >/dev/null 2>&1 \
    && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$GPU_CONTAINER"; then
    # A GPU backend container from a previous run: keep using it.
    GPU_WANTS_HOST=0
fi

if [ "$GPU_WANTS_HOST" = "1" ]; then
    # A stale GPU container would still hold the port: stop it for a clean start.
    if command -v docker >/dev/null 2>&1 \
        && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$GPU_CONTAINER"; then
        echo "Stopping GPU backend container (host backend requested)..."
        docker stop "$GPU_CONTAINER" >/dev/null
    fi
    echo "Starting backend..."
    if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
        echo "✔ Backend already running"
    else
        nohup "$VENV_PYTHON" -m uvicorn src.backend.api.server:app \
            --host 127.0.0.1 \
            --port "$BACKEND_PORT" \
            --log-level warning > "$BACKEND_LOG" 2>&1 &

        sleep 2
    fi
else
    echo "Starting backend in GPU container ($GPU_IMAGE)..."
    command -v docker >/dev/null 2>&1 || { echo "❌ BACKEND_GPU=1 needs the docker CLI"; exit 1; }
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$GPU_CONTAINER"; then
        docker start "$GPU_CONTAINER" >/dev/null
    else
        # --network host keeps every localhost URL (DB, embedding, Ollama)
        # and .env.local working unchanged inside the container (Linux only).
        docker pull "$GPU_IMAGE"
        docker run -d --name "$GPU_CONTAINER" --gpus all --network host \
            -v "$PROJECT_DIR:/app" -w /app "$GPU_IMAGE" sleep infinity
    fi
    # One interpreter for everything below: bare `pip` and `python3` can
    # resolve to different Pythons in these images (system python vs the
    # conda env that ships the CUDA torch). Prefer conda's python so the
    # backend runs with GPU torch.
    if docker exec "$GPU_CONTAINER" test -x /opt/conda/bin/python; then
        GPU_PY=/opt/conda/bin/python
    else
        GPU_PY=python3
    fi
    echo "Using container python: $GPU_PY"
    # Deps minus torch: the image ships its own CUDA torch for its arch, and
    # requirements.txt must never overwrite it with a CPU-only wheel.
    REQ_HASH_FILE="$PROJECT_DIR/logs/.backend-gpu-req.sha256"
    REQ_HASH="$GPU_PY $(sha256sum "$PROJECT_DIR/requirements.txt" | cut -d' ' -f1)"
    if [ ! -f "$REQ_HASH_FILE" ] || [ "$(cat "$REQ_HASH_FILE")" != "$REQ_HASH" ]; then
        echo "Installing backend deps inside GPU container (first run takes a few minutes)..."
        mapfile -t GPU_PKGS < <(grep -v -e '^torch==' -e '^--extra-index-url' -e '^#' -e '^[[:space:]]*$' "$PROJECT_DIR/requirements.txt")
        # Optional PyPI mirror for networks without direct PyPI access
        # (e.g. PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/).
        PIP_INDEX_ARGS=()
        if [ -n "${PIP_INDEX_URL:-}" ]; then PIP_INDEX_ARGS+=(--index-url "$PIP_INDEX_URL"); fi
        if [ -n "${PIP_TRUSTED_HOST:-}" ]; then PIP_INDEX_ARGS+=(--trusted-host "$PIP_TRUSTED_HOST"); fi
        docker exec "${PROXY_ARGS[@]}" "$GPU_CONTAINER" "$GPU_PY" -m pip install --break-system-packages --retries 10 --timeout 60 "${PIP_INDEX_ARGS[@]}" "${GPU_PKGS[@]}"
        printf '%s\n' "$REQ_HASH" > "$REQ_HASH_FILE"
    fi
    # Stop any previous uvicorn inside the container so the port is free.
    docker exec "$GPU_CONTAINER" pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
    sleep 1
    # Forward proxy settings: the container does not inherit the host shell's
    # proxy vars, and without them pip (and any external call) gets DNS errors
    # like "Name or service not known" on proxied networks.
    PROXY_ARGS=()
    for proxy_var in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do
        if [ -n "${!proxy_var:-}" ]; then PROXY_ARGS+=(-e "$proxy_var=${!proxy_var}"); fi
    done
    # Fail fast when the container has no network instead of printing pages
    # of pip retries for every package. Probe exactly what pip needs: HTTPS
    # to both the simple index and the file host. Any HTTP answer — even an
    # error status — proves DNS+TCP+TLS work; only connection-level failures
    # (DNS, refused, timeout, TLS) mean no network.
    if ! NET_ERR="$(docker exec "$GPU_CONTAINER" python3 -c "
import urllib.request, urllib.error
for url in ('https://pypi.org/simple/uvicorn/', 'https://files.pythonhosted.org/'):
    print('trying ' + url, flush=True)
    try:
        urllib.request.urlopen(url, timeout=10).read(1)
        print('ok ' + url, flush=True)
    except urllib.error.HTTPError as e:
        print('reachable %s (HTTP %s)' % (url, e.code), flush=True)
" 2>&1)"; then
        DETECTED_PROXY="$(for v in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY; do if [ -n "${!v:-}" ]; then printf '%s ' "$v"; fi; done)"
        echo "❌ GPU container cannot reach PyPI (DNS or blocked network)."
        echo "   Proxy vars currently set here: ${DETECTED_PROXY:-none} (export http_proxy/https_proxy + no_proxy and re-run if this host is proxied)."
        echo "   No direct PyPI access? Point pip at a mirror instead:"
        echo "     PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ BACKEND_GPU=1 ./scripts/restart.sh"
        echo "--- underlying error + container DNS diagnostics ---"
        printf '%s\n' "$NET_ERR" | tail -8
        echo "--- container resolv.conf ---"
        docker exec "$GPU_CONTAINER" cat /etc/resolv.conf 2>/dev/null || echo "(unreadable)"
        echo "--- container getent ---"
        docker exec "$GPU_CONTAINER" getent hosts pypi.org 2>&1 || echo "(getent failed)"
        echo "--- host resolv.conf (first line) ---"
        head -1 /etc/resolv.conf 2>/dev/null || echo "(unreadable)"
        exit 1
    fi
    # .env.local is (re)passed on every start, so edits apply without rebuilds.
    ENV_ARGS=()
    if [ -f "$ENV_FILE" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            line="${line%$'\r'}"
            case "$line" in ''|\#*) continue ;; esac
            ENV_ARGS+=(-e "$line")
        done < "$ENV_FILE"
    fi
    docker exec -d "${PROXY_ARGS[@]}" "${ENV_ARGS[@]}" "$GPU_CONTAINER" bash -c "cd /app && exec $GPU_PY -m uvicorn src.backend.api.server:app --host 127.0.0.1 --port $BACKEND_PORT --log-level warning >> /app/logs/backend.log 2>&1"
    echo "Waiting for backend..."
    for i in {1..30}; do
        if curl -s "http://$BACKEND_HOST:$BACKEND_PORT/health" >/dev/null 2>&1; then
            echo "✔ Backend ready (GPU container)"
            echo "--- container torch ---"
            docker exec "$GPU_CONTAINER" "$GPU_PY" -c "import torch; print('torch', torch.__version__, '| CUDA build:', torch.version.cuda, '| cuda_available:', torch.cuda.is_available())" 2>&1 || echo "(torch probe failed — backend runs, but check GPU support)"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Backend failed to start in GPU container"
            echo "---- backend.log (exec'd uvicorn output) ----"
            tail -n 30 "$BACKEND_LOG" 2>/dev/null || echo "(no backend log yet)"
            echo "---- uvicorn process inside container ----"
            docker exec "$GPU_CONTAINER" pgrep -af "uvicorn src.backend.api.server:app" 2>/dev/null || echo "(no uvicorn process)"
            echo "---- container log tail (entrypoint/banner only) ----"
            docker logs --tail 5 "$GPU_CONTAINER" 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done
fi

# ----------------------------
# EMBEDDING START (FIXED)
# ----------------------------
echo "Starting embedding server..."

if lsof -i :$EMBEDDING_PORT >/dev/null 2>&1; then
    echo "✔ Embedding API already running"
else
    nohup "$VENV_PYTHON" -m uvicorn src.backend.services.embedding_server:app \
        --host 127.0.0.1 \
        --port "$EMBEDDING_PORT" \
        --log-level info > "$EMBEDDING_LOG" 2>&1 &

    echo "Waiting for embedding server to start..."

    for i in {1..30}; do
        if curl -s "http://$BACKEND_HOST:$EMBEDDING_PORT/health" >/dev/null 2>&1; then
            echo "✔ Embedding API ready (model loads on first request)"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Embedding API failed to start"
            echo "---- Last logs ----"
            tail -n 30 "$EMBEDDING_LOG"
            exit 1
        fi
        sleep 1
    done
fi

# ----------------------------
# DASHBOARD START
# ----------------------------
echo "Starting dashboard..."

cd "$DASHBOARD_DIR"

export PORT="$DASHBOARD_PORT"
export HOST="127.0.0.1"
export API_URL="$BACKEND_URL"
export NEXT_PUBLIC_API_URL="$BACKEND_URL"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
else
    # After React 19 upgrade, ensure we are not running on stale React 18 modules
    REACT_VERSION=$(node -e "console.log(require('react/package.json').version)" 2>/dev/null || echo "0.0.0")
    if [[ "$REACT_VERSION" == 18.* ]]; then
        echo "⚠️  Detected React $REACT_VERSION in node_modules (expected 19.x after upgrade)"
        echo "   Running clean install for React 19..."
        rm -rf node_modules package-lock.json
        npm install
    fi
fi

if [ "${DASHBOARD_MODE:-prod}" = "dev" ]; then
    echo "Running Next.js in DEV mode (Next 16 + React 19)..."
    nohup npx next dev --port "$DASHBOARD_PORT" --hostname 127.0.0.1 > "$PROJECT_DIR/logs/dashboard.log" 2>&1 &
else
    echo "Building Next.js..."
    npx next build

    echo "Running Next.js in PROD mode..."
    nohup npx next start --port "$DASHBOARD_PORT" --hostname 127.0.0.1 > "$PROJECT_DIR/logs/dashboard.log" 2>&1 &
fi

sleep 2

# ----------------------------
# FINAL CHECK
# ----------------------------
echo ""
echo "Services ready:"
echo "  Backend API:   $BACKEND_URL"
echo "  Embedding API: $EMBEDDING_URL"
echo "  Dashboard:     http://localhost:$DASHBOARD_PORT"
echo ""
echo "Logs:"
echo "  Backend:   $BACKEND_LOG"
echo "  Embedding: $EMBEDDING_LOG"
echo "  Dashboard:  $PROJECT_DIR/logs/dashboard.log"
echo ""
echo "Startup complete ✔"
