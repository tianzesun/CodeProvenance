#!/usr/bin/env bash
# Package the Qwen Binoculars models for offline transfer to the GPU server.
# Run on THIS machine (which has them cached): bash scripts/pack-binoculars.sh
# Then copy the output tar to the GB10 and extract it there.
set -euo pipefail

HF_DIR="${HF_HOME:-$HOME/.cache/huggingface}"
OUT="${1:-/tmp/binoculars-models.tar.gz}"

echo "Packaging models from $HF_DIR/hub ..."
tar czf "$OUT" -C "$HF_DIR/hub" \
    models--Qwen--Qwen2.5-0.5B \
    models--Qwen--Qwen2.5-0.5B-Instruct

echo "Done: $OUT ($(du -sh "$OUT" | cut -f1))"
echo ""
echo "On the GPU server, run:"
echo "  mkdir -p ~/.cache/huggingface/hub"
echo "  tar xzf $(basename "$OUT") -C ~/.cache/huggingface/hub"
echo ""
echo "Then restart the backend and check for 'BinocularsDetector loaded' in the log."
