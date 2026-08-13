#!/bin/bash
# Download AIGCodeSet (AI-generated vs human-written Python code).
#
# Reference: Demirok, B. and Kutlu, M., "AIGCodeSet: A New Annotated Dataset
# for AI Generated Code Detection", IEEE SIU 2025. arXiv:2412.16594.
# License: CDLA Permissive v2.0. Hosted on Hugging Face.
#
# Usage: bash data/datasets/aigcodeset/download.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SCRIPT_DIR/raw"
mkdir -p "$RAW_DIR"

BASE_URL="https://huggingface.co/datasets/basakdemirok/AIGCodeSet/resolve/main/data"
AI_FILE="$RAW_DIR/ai.csv"
HUMAN_FILE="$RAW_DIR/human.csv"

echo "=== AIGCodeSet downloader ==="
echo ""

curl -fsSL --retry 3 -o "$AI_FILE" "$BASE_URL/created_dataset_with_llms.csv"
curl -fsSL --retry 3 -o "$HUMAN_FILE" "$BASE_URL/human_selected_dataset.csv"

python3 - "$RAW_DIR" <<'PY'
import csv
import sys
from pathlib import Path

raw = Path(sys.argv[1])
for name in ("ai.csv", "human.csv"):
    path = raw / name
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = sum(1 for _ in reader)
    mark = "OK" if rows else "FAIL"
    print(f"{mark} {name}: {rows} rows | columns: {', '.join(header[:6])}")
PY

echo ""
echo "Download complete. Materialise with:"
echo "  python -m src.backend.scripts.build_aigcodeset"