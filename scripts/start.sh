#!/bin/bash
# IntegrityDesk - Robust Startup Script
# Backend + Embedding Server + Celery Worker + Next.js Dashboard
#
# GPU backend (ARM/Blackwell hosts without a pip CUDA torch wheel):
#   BACKEND_GPU=1 ./scripts/start.sh    (image override: GPU_IMAGE=...)
#   EMBEDDING_GPU=1 ./scripts/start.sh  (same image, second holder)
# The celery worker always lives wherever the backend lives.

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
# Opt in with BACKEND_GPU=1 / EMBEDDING_GPU=1 (base image override: GPU_IMAGE=...).
# Deps bake into Dockerfile.gpu (rebuilt only when requirements.txt changes);
# holder containers are recreated automatically when the image moves on.
# BACKEND_GPU=0 / EMBEDDING_GPU=0 force the host venv services.
GPU_CONTAINER="integritydesk-backend-gpu"
EMB_GPU_CONTAINER="integritydesk-embedding-gpu"
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
# SERVICE CHECKS (Postgres, Redis, Ollama)
# ----------------------------
echo "Checking supporting services..."

# Postgres: fast TCP probe (never prints credentials, only host:port)
if [ -n "${DATABASE_URL:-}" ]; then
    read -r DB_HOST DB_PORT <<< "$("$VENV_PYTHON" -c "
import os
from urllib.parse import urlparse
u = urlparse(os.environ.get('DATABASE_URL', ''))
scheme = (u.scheme or '').lower()
port = u.port or ('5432' if 'postgres' in scheme else '')
print(u.hostname or '', port)
" 2>/dev/null)"
    if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ] \
        && "$VENV_PYTHON" -c "import socket, sys; s = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5); s.close()" "$DB_HOST" "$DB_PORT" 2>/dev/null; then
        echo "✔ Postgres reachable ($DB_HOST:$DB_PORT)"
    else
        echo "❌ Postgres NOT reachable (${DB_HOST:-unknown}:${DB_PORT:-?}) — jobs and settings cannot load until the database is up"
    fi
else
    echo "⚠️  DATABASE_URL is not set — skipping Postgres check"
fi

# Redis: real PING via the redis client (optional service — warn only)
if [ -n "${REDIS_URL:-}" ]; then
    REDIS_DISP="$("$VENV_PYTHON" -c "
import os
from urllib.parse import urlparse
u = urlparse(os.environ.get('REDIS_URL', ''))
print(f\"{u.hostname or 'unknown'}:{u.port or 6379}\")
" 2>/dev/null)"
    if "$VENV_PYTHON" -c "import os, redis; redis.Redis.from_url(os.environ.get('REDIS_URL', ''), socket_connect_timeout=5).ping()" 2>/dev/null; then
        echo "✔ Redis reachable ($REDIS_DISP)"
    else
        echo "⚠️  Redis NOT reachable ($REDIS_DISP) — caching disabled, app continues without it"
    fi
else
    echo "⚠️  REDIS_URL is not set — Redis cache disabled"
fi

# Ollama: list pulled models (optional service — warn only)
OLLAMA_BASE="${OLLAMA_BASE_URL:-http://localhost:11434/v1}"
OLLAMA_ROOT="${OLLAMA_BASE%/}"
OLLAMA_ROOT="${OLLAMA_ROOT%/v1}"
TAGS_JSON="$(curl -s --max-time 5 "$OLLAMA_ROOT/api/tags" 2>/dev/null || true)"
if OLLAMA_INFO="$(printf '%s' "$TAGS_JSON" | "$VENV_PYTHON" -c "
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
models = data.get('models') or []
names = [str(m.get('name', '?')) for m in models if isinstance(m, dict)]
shown = ', '.join(names[:4]) + ('…' if len(names) > 4 else '')
print(f'{len(names)}|{shown}')
" 2>/dev/null)"; then
    OLLAMA_COUNT="${OLLAMA_INFO%%|*}"
    OLLAMA_NAMES="${OLLAMA_INFO#*|}"
    if [ "$OLLAMA_COUNT" -gt 0 ] 2>/dev/null; then
        echo "✔ Ollama up ($OLLAMA_ROOT) · $OLLAMA_COUNT model(s): $OLLAMA_NAMES"
    else
        echo "⚠️  Ollama reachable but no models pulled — run: ollama pull <model>"
    fi
else
    echo "⚠️  Ollama NOT reachable ($OLLAMA_ROOT/api/tags) — AI summaries fall back to heuristics"
fi
echo ""

# ----------------------------
# BACKEND START (host venv, or NVIDIA GPU container when requested)
# ----------------------------
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/.hf-cache"

# Shared GPU-image helpers: backend and embedding holders run from one image
# (Dockerfile.gpu) so there is a single build and a single torch.
GPU_IMG="integritydesk-backend-gpu-img"
GPU_DOCKERFILE="$PROJECT_DIR/Dockerfile.gpu"

require_docker() {
    command -v docker >/dev/null 2>&1 || { echo "❌ GPU mode needs the docker CLI"; exit 1; }
}

ensure_gpu_image() {
    # Wheelhouse first (host pip has the reliable network), then pull base,
    # probe, and (re)build. The build itself never touches an index.
    ensure_wheelhouse
    # Pull the base image, probe build-time network, and (re)build our image
    # when requirements.txt or the Dockerfile changed (layer cache makes a
    # no-change rebuild instant).
    [ -f "$GPU_DOCKERFILE" ] || { echo "❌ Missing $GPU_DOCKERFILE"; exit 1; }
    if ! docker image inspect "$GPU_IMAGE" >/dev/null 2>&1; then
        echo "Pulling base image..."
        docker pull "$GPU_IMAGE" || { echo "❌ Could not pull $GPU_IMAGE"; exit 1; }
    fi
    # Probe under the same conditions the build will use. Any HTTP answer —
    # even an error status — proves DNS+TCP+TLS work; only connection-level
    # failures (DNS, refused, timeout, TLS) mean no network.
    if ! NET_ERR="$(docker run --rm --network host "$GPU_IMAGE" python3 -c "
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
        echo "❌ No PyPI network for the GPU image build (DNS or blocked network)."
        echo "   Proxy vars currently set here: ${DETECTED_PROXY:-none} (export http_proxy/https_proxy + no_proxy and re-run if this host is proxied)."
        echo "   No direct PyPI access? Point the build at a PyPI mirror near you instead:"
        echo "     PIP_INDEX_URL=https://<your-regional-mirror>/simple/ BACKEND_GPU=1 ./scripts/restart.sh"
        echo "--- underlying error ---"
        printf '%s\n' "$NET_ERR" | tail -8
        echo "--- image resolv.conf ---"
        docker run --rm --network host "$GPU_IMAGE" cat /etc/resolv.conf 2>/dev/null || echo "(unreadable)"
        echo "--- host resolv.conf (first line) ---"
        head -1 /etc/resolv.conf 2>/dev/null || echo "(unreadable)"
        exit 1
    fi
    REQ_HASH="$(cat "$PROJECT_DIR/requirements.txt" "$GPU_DOCKERFILE" | sha256sum | cut -d' ' -f1)"
    BUILT_HASH="$(docker image inspect -f '{{index .Config.Labels "req-hash"}}' "$GPU_IMG" 2>/dev/null || true)"
    if [ "$BUILT_HASH" != "$REQ_HASH" ]; then
        echo "Building GPU backend image (deps bake in; first build takes a while)..."
        # Proxy build-args only when set: empty proxy vars in the build env
        # break some tools, so blank ones are never passed.
        PROXY_BUILD_ARGS=()
        for proxy_var in http_proxy https_proxy no_proxy; do
            if [ -n "${!proxy_var:-}" ]; then PROXY_BUILD_ARGS+=(--build-arg "$proxy_var=${!proxy_var}"); fi
        done
        DOCKER_BUILDKIT=1 docker build --network host -f "$GPU_DOCKERFILE" \
            --build-arg "BASE_IMAGE=$GPU_IMAGE" \
            --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL:-}" \
            --build-arg "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST:-}" \
            "${PROXY_BUILD_ARGS[@]}" \
            --label "req-hash=$REQ_HASH" \
            -t "$GPU_IMG" "$PROJECT_DIR" || { echo "❌ GPU image build failed"; exit 1; }
    fi
}

ensure_gpu_holder() {
    # $1 = holder container name. Creates/starts the sleep-infinity holder on
    # the current image, recreating it when the image moved on (code and logs
    # live in the mounted repo, so a recreate loses nothing).
    local name="$1"
    local holder_img=""
    local current_img=""
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$name"; then
        holder_img="$(docker inspect -f '{{.Image}}' "$name")"
        current_img="$(docker inspect -f '{{.Id}}' "$GPU_IMG")"
        if [ "$holder_img" != "$current_img" ]; then
            echo "Backend image changed — recreating $name..."
            docker rm -f "$name" >/dev/null
        else
            docker start "$name" >/dev/null
        fi
    fi
    if ! docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$name"; then
        # --network host keeps every localhost URL (DB, embedding, Ollama)
        # and .env.local working unchanged inside the container (Linux only).
        docker run -d --name "$name" --gpus all --network host \
            -v "$PROJECT_DIR:/app" -w /app "$GPU_IMG" sleep infinity
    fi
}

detect_gpu_py() {
    # $1 = holder container name. Echoes the interpreter owning CUDA torch:
    # bare `pip` and `python3` can resolve to different Pythons in these
    # images (system python vs the conda env shipping CUDA torch).
    local name="$1"
    if docker exec "$name" test -x /opt/conda/bin/python; then
        echo /opt/conda/bin/python
    else
        echo python3
    fi
}

# Proxy vars never enter holders on their own; forward the host shell's so
# external calls (and any fallback pip) work on proxied networks.
PROXY_ARGS=()
for proxy_var in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do
    if [ -n "${!proxy_var:-}" ]; then PROXY_ARGS+=(-e "$proxy_var=${!proxy_var}"); fi
done

ensure_wheelhouse() {
    # Pre-download every GPU-image wheel with the host pip (proven reliable
    # on networks where container DNS flakes), so the image build installs
    # with --no-index from local files and never touches a package index.
    # torch wheels are pruned: the base image's CUDA torch is used as-is.
    local wheel_dir="$PROJECT_DIR/.wheels"
    local req_list="$wheel_dir/requirements-gpu.txt"
    local marker="$wheel_dir/.req.sha256"
    local want_hash
    want_hash="$(cat "$PROJECT_DIR/requirements.txt" | sha256sum | cut -d' ' -f1)"
    if [ -f "$marker" ] && [ "$(cat "$marker")" = "$want_hash" ] && [ -n "$(ls -A "$wheel_dir"/*.whl 2>/dev/null)" ]; then
        return 0
    fi
    echo "Downloading GPU image wheels on host (one-time per requirements change)..."
    mkdir -p "$wheel_dir"
    grep -v -e '^torch==' -e '^--extra-index-url' -e '^#' -e '^[[:space:]]*$' \
        -e '^pytest' -e '^black==' -e '^ruff==' -e '^flake8==' -e '^mypy==' \
        "$PROJECT_DIR/requirements.txt" | grep -v "^$" > "$req_list"
    "$VENV_PYTHON" -m pip download --retries 10 --timeout 60 -r "$req_list" -d "$wheel_dir" \
        || { echo "❌ Wheel download failed (host network needed once per requirements change)"; return 1; }
    rm -f "$wheel_dir"/torch-*.whl "$wheel_dir"/nvidia-*.whl "$wheel_dir"/triton-*.whl "$wheel_dir"/cuda-*.whl
    printf '%s\n' "$want_hash" > "$marker"
}

build_env_args() {
    # Emit .env.local as docker -e args (one per line) so edits apply on
    # every start without rebuilds.
    if [ -f "$ENV_FILE" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            line="${line%$'\r'}"
            case "$line" in ''|\#*) continue ;; esac
            printf '%s\n' "-e"
            printf '%s\n' "$line"
        done < "$ENV_FILE"
    fi
}

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
    echo "Starting backend in GPU container (image: $GPU_IMG from $GPU_IMAGE)..."
    require_docker
    ensure_gpu_image
    ensure_gpu_holder "$GPU_CONTAINER"
    GPU_PY="$(detect_gpu_py "$GPU_CONTAINER")"
    echo "Using container python: $GPU_PY"
    # Deps are baked into the image at build time (torch excluded — the base
    # image's own CUDA torch is never overwritten). Nothing to install here.
    # Stop any previous uvicorn inside the container so the port is free.
    docker exec "$GPU_CONTAINER" pkill -f "uvicorn src.backend.api.server:app" 2>/dev/null || true
    sleep 1
    mapfile -t ENV_ARGS < <(build_env_args)
    # HF weights (Binoculars pair etc.) persist in the mounted repo so holder
    # recreates skip re-downloads over flaky links. Respects an explicit
    # HF_HOME in .env.local when present.
    if ! grep -q "^HF_HOME=" "$ENV_FILE" 2>/dev/null; then
        ENV_ARGS+=(-e HF_HOME=/app/.hf-cache)
    fi
    docker exec -d "${PROXY_ARGS[@]}" "${ENV_ARGS[@]}" "$GPU_CONTAINER" bash -c "cd /app && exec $GPU_PY -m uvicorn src.backend.api.server:app --host 127.0.0.1 --port $BACKEND_PORT --log-level warning >> /app/logs/backend.log 2>&1"
    echo "Waiting for backend (first boot imports torch/transformers — can take minutes on ARM)..."
    for i in $(seq 1 120); do
        if curl -s "http://$BACKEND_HOST:$BACKEND_PORT/health" >/dev/null 2>&1; then
            echo "✔ Backend ready (GPU container)"
            echo "--- container torch ---"
            TORCH_INFO="$(docker exec "$GPU_CONTAINER" "$GPU_PY" -c "import torch; print('torch', torch.__version__, '| CUDA build:', torch.version.cuda, '| cuda_available:', torch.cuda.is_available())" 2>&1)" || TORCH_INFO="torch probe failed"
            printf '%s\n' "$TORCH_INFO"
            if printf '%s' "$TORCH_INFO" | grep -q "cuda_available: False" \
                && docker exec "$GPU_CONTAINER" nvidia-smi -L 2>/dev/null | grep -qi "gb10\|blackwell"; then
                echo "⚠️  GB10/Blackwell GPU detected but this image's torch has no CUDA:"
                echo "   the base image predates GB10 support. Re-run with the newest"
                echo "   NGC PyTorch py3 tag from the NGC catalog, e.g.:"
                echo "     GPU_IMAGE=nvcr.io/nvidia/pytorch:<newest-tag>-py3 BACKEND_GPU=1 ./scripts/restart.sh"
                echo "   (confirm the tag pulls first: docker pull <same image>)"
            elif printf '%s' "$TORCH_INFO" | grep -q "cuda_available: False"; then
                echo "⚠️  Container torch has no CUDA — check the image's CUDA build with: docker exec $GPU_CONTAINER $GPU_PY -c \"import torch; print(torch.version.cuda)\""
            fi
            break
        fi
        if [ "$i" -eq 120 ]; then
            echo "❌ Backend failed to start in GPU container"
            echo "---- backend.log (exec'd uvicorn output) ----"
            tail -n 30 "$BACKEND_LOG" 2>/dev/null || echo "(no backend log yet)"
            echo "---- uvicorn process inside container ----"
            docker exec "$GPU_CONTAINER" pgrep -af "uvicorn src.backend.api.server:app" 2>/dev/null || echo "(no uvicorn process)"
            echo "---- container log tail (entrypoint/banner only) ----"
            docker logs --tail 5 "$GPU_CONTAINER" 2>/dev/null || true
            exit 1
        fi
        if [ $((i % 30)) -eq 0 ]; then
            echo "  …still waiting ($i s)"
        fi
        sleep 1
    done
fi

# ----------------------------
# EMBEDDING START (host venv, or shared GPU image when requested)
# ----------------------------
echo "Starting embedding server..."

EMB_WANTS_HOST=1
if [ "${EMBEDDING_GPU:-}" = "1" ]; then
    EMB_WANTS_HOST=0
elif [ "${EMBEDDING_GPU:-}" != "0" ] \
    && command -v docker >/dev/null 2>&1 \
    && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$EMB_GPU_CONTAINER"; then
    # An embedding holder from a previous GPU run: keep using it.
    EMB_WANTS_HOST=0
fi

if [ "$EMB_WANTS_HOST" = "1" ]; then
    if command -v docker >/dev/null 2>&1 \
        && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$EMB_GPU_CONTAINER"; then
        echo "Stopping GPU embedding container (host embedding requested)..."
        docker stop "$EMB_GPU_CONTAINER" >/dev/null
    fi
    if lsof -i :$EMBEDDING_PORT >/dev/null 2>&1; then
        echo "✔ Embedding API already running"
    else
        nohup "$VENV_PYTHON" -m uvicorn src.backend.services.embedding_server:app \
            --host 127.0.0.1 \
            --port "$EMBEDDING_PORT" \
            --log-level info > "$EMBEDDING_LOG" 2>&1 &
    fi
else
    require_docker
    ensure_gpu_image
    ensure_gpu_holder "$EMB_GPU_CONTAINER"
    EMB_PY="$(detect_gpu_py "$EMB_GPU_CONTAINER")"
    echo "Using container python: $EMB_PY"
    docker exec "$EMB_GPU_CONTAINER" pkill -f "uvicorn src.backend.services.embedding_server:app" 2>/dev/null || true
    sleep 1
    mapfile -t ENV_ARGS < <(build_env_args)
    # Default to CUDA inside the GPU holder; an explicit EMBEDDING_DEVICE in
    # .env.local wins (checked, not appended twice).
    if ! grep -q "^EMBEDDING_DEVICE=" "$ENV_FILE" 2>/dev/null; then
        ENV_ARGS=(-e EMBEDDING_DEVICE=cuda "${ENV_ARGS[@]}")
    fi
    # HF weights persist in the mounted repo so recreates skip re-downloads.
    ENV_ARGS+=(-e HF_HOME=/app/.hf-cache)
    echo "Starting embedding server in GPU container..."
    docker exec -d "${PROXY_ARGS[@]}" "${ENV_ARGS[@]}" "$EMB_GPU_CONTAINER" bash -c "cd /app && exec $EMB_PY -m uvicorn src.backend.services.embedding_server:app --host 127.0.0.1 --port $EMBEDDING_PORT --log-level info >> /app/logs/embedding.log 2>&1"
fi

echo "Waiting for embedding server to start..."

for i in {1..30}; do
    if curl -s "http://$BACKEND_HOST:$EMBEDDING_PORT/health" >/dev/null 2>&1; then
        echo "✔ Embedding API ready (model loads on first request)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Embedding API failed to start"
        echo "---- Last logs ----"
        if [ "$EMB_WANTS_HOST" = "1" ]; then
            tail -n 30 "$EMBEDDING_LOG"
        else
            tail -n 30 "$EMBEDDING_LOG" 2>/dev/null || docker logs --tail 30 "$EMB_GPU_CONTAINER"
        fi
        exit 1
    fi
    sleep 1
done

# ----------------------------
# CELERY WORKER (drains the analysis queue)
# ----------------------------
# Uploads go to Celery whenever Redis is reachable; without a worker those
# jobs sit "Queued for analysis" forever. The worker lives wherever the
# backend lives (GPU holder when BACKEND_GPU=1, else host venv) so analysis
# always runs with the same interpreter and libraries.
echo "Starting celery worker..."

redis_reachable() {
    [ -n "${REDIS_URL:-}" ] || return 1
    "$VENV_PYTHON" -c "
import os, socket, sys
from urllib.parse import urlparse
u = urlparse(os.environ.get('REDIS_URL', ''))
try:
    s = socket.create_connection((u.hostname or '127.0.0.1', u.port or 6379), timeout=3)
    s.close()
except OSError:
    sys.exit(1)
" 2>/dev/null
}

CELERY_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
CELERY_LOG="$PROJECT_DIR/logs/celery.log"

start_celery_host() {
    cd "$PROJECT_DIR"
    nohup "$VENV_PYTHON" -m celery -A src.backend.workers.celery_app:celery_app worker \
        -Q analysis --concurrency="$CELERY_CONCURRENCY" --loglevel=info > "$CELERY_LOG" 2>&1 &
}

if ! redis_reachable; then
    echo "⚠️  Redis unreachable — uploads run in-process; skipping Celery worker"
elif [ "$GPU_WANTS_HOST" = "1" ]; then
    if pgrep -f "celery.*celery_app" >/dev/null 2>&1; then
        echo "✔ Celery worker already running"
    else
        start_celery_host
        sleep 2
    fi
else
    require_docker
    ensure_gpu_holder "$GPU_CONTAINER"
    EMB_PY_WORKER="$(detect_gpu_py "$GPU_CONTAINER")"
    if docker exec "$GPU_CONTAINER" pgrep -f "celery.*celery_app" >/dev/null 2>&1; then
        echo "✔ Celery worker already running (GPU container)"
    else
        echo "Starting celery worker in GPU container (threads pool: CUDA contexts cannot survive fork)..."
        mapfile -t ENV_ARGS < <(build_env_args)
        docker exec -d "${PROXY_ARGS[@]}" "${ENV_ARGS[@]}" "$GPU_CONTAINER" bash -c "cd /app && exec $EMB_PY_WORKER -m celery -A src.backend.workers.celery_app:celery_app worker -Q analysis --pool=threads --concurrency=\"$CELERY_CONCURRENCY\" --loglevel=info >> /app/logs/celery.log 2>&1"
        sleep 2
    fi
fi

if redis_reachable; then
    echo "Waiting for celery worker..."
    CELERY_INSPECT="src.backend.workers.celery_app:celery_app"
    if [ "$GPU_WANTS_HOST" != "1" ]; then
        mapfile -t ENV_ARGS < <(build_env_args)
        CELERY_PY="$(detect_gpu_py "$GPU_CONTAINER")"
    fi
    for i in {1..30}; do
        if [ "$GPU_WANTS_HOST" = "1" ]; then
            PONG="$(cd "$PROJECT_DIR" && timeout 10 "$VENV_PYTHON" -m celery -A "$CELERY_INSPECT" inspect ping 2>/dev/null | grep -ci pong || true)"
        else
            PONG="$(docker exec "${ENV_ARGS[@]}" "$GPU_CONTAINER" timeout 10 bash -c "cd /app && exec $CELERY_PY -m celery -A $CELERY_INSPECT inspect ping" 2>/dev/null | grep -ci pong || true)"
        fi
        if [ "${PONG:-0}" -gt 0 ] 2>/dev/null; then
            echo "✔ Celery worker ready — queued jobs will drain"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Celery worker did not answer (queued jobs would stall)"
            echo "---- Last logs ----"
            tail -n 30 "$CELERY_LOG" 2>/dev/null || docker logs --tail 30 "$GPU_CONTAINER"
            exit 1
        fi
        sleep 1
    done
fi

# ----------------------------
# DASHBOARD START
# ----------------------------
# SKIP_DASHBOARD=1 leaves a running dashboard alone (scripts/restart_backend.sh).
if [ "${SKIP_DASHBOARD:-}" = "1" ]; then
    echo "Skipping dashboard (SKIP_DASHBOARD=1)"
else
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

    echo "Waiting for dashboard..."
    for i in {1..30}; do
        if curl -s "http://localhost:$DASHBOARD_PORT/" >/dev/null 2>&1; then
            echo "✔ Dashboard ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Dashboard failed to start"
            echo "---- Last logs ----"
            tail -n 30 "$PROJECT_DIR/logs/dashboard.log"
            exit 1
        fi
        sleep 1
    done
fi

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
echo "  Celery:    $CELERY_LOG"
echo "  Dashboard:  $PROJECT_DIR/logs/dashboard.log"
echo ""
echo "Startup complete ✔"
