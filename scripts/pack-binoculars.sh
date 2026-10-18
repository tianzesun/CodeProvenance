#!/usr/bin/env bash
# Package the Binoculars dependencies (pip wheel + Qwen models) for offline
# transfer to a server that cannot reach GitHub or huggingface.co.
#
# Run on THIS machine (which has them available):
#   bash scripts/pack-binoculars.sh [output-dir]
#
# Then copy the output directory to the target server and follow the
# printed instructions.
set -euo pipefail

OUT="${1:-/tmp/binoculars-bundle}"
HF_DIR="${HF_HOME:-$HOME/.cache/huggingface}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$OUT"

echo "=== 1. Building binoculars pip wheel ==="
# --no-deps: the target server already has torch/transformers; we only ship
# the detector package itself.
if [ -d "$REPO_DIR/venv" ]; then
    # Build from the local venv's pip so the wheel matches its Python version.
    "$REPO_DIR/venv/bin/pip" wheel --no-deps \
        "git+https://github.com/ahans30/Binoculars.git" \
        -w "$OUT" 2>&1 | tail -2
else
    pip wheel --no-deps \
        "git+https://github.com/ahans30/Binoculars.git" \
        -w "$OUT" 2>&1 | tail -2
fi

echo ""
echo "=== 2. Packing Qwen models from $HF_DIR/hub ==="
if [ -d "$HF_DIR/hub/models--Qwen--Qwen2.5-0.5B" ]; then
    tar czf "$OUT/qwen-models.tar.gz" -C "$HF_DIR/hub" \
        models--Qwen--Qwen2.5-0.5B \
        models--Qwen--Qwen2.5-0.5B-Instruct
    echo "  packed: $(du -sh "$OUT/qwen-models.tar.gz" | cut -f1)"
else
    echo "  WARNING: Qwen models not found in $HF_DIR/hub — model pack skipped."
fi

echo ""
echo "Bundle ready: $OUT ($(du -sh "$OUT" | cut -f1))"
echo ""
echo "On the target server, run:"
echo "  pip install --no-deps $OUT/binoculars-*.whl"
if [ -f "$OUT/qwen-models.tar.gz" ]; then
    echo "  mkdir -p ~/.cache/huggingface/hub"
    echo "  tar xzf $OUT/qwen-models.tar.gz -C ~/.cache/huggingface/hub"
fi
echo "  bash scripts/check-binoculars.sh   # verify the load"
