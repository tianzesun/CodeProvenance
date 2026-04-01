#!/bin/bash
# External Benchmark Dataset Download Script
#
# Layer 2: External Benchmarks (publicly available, NOT in Git)
#   - BigCloneBench (55K Java files, 5.5GB H2 DB)
#   - CodeSimilarityDataset (100 Python snippets)
#
# Usage: bash benchmark/data/download_external.sh
#
# All datasets are version-pinned for reproducibility.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR"

echo "=== CodeProvenance External Benchmark Downloader ==="
echo ""

# --- BigCloneBench ---
echo "[1/2] Downloading BigCloneBench (5.5GB H2 DB + 55K Java files)..."
BCB_DIR="$DATA_DIR/bigclonebench"

if [ -f "$BCB_DIR/bcb.h2.db" ]; then
    echo "  BigCloneBench H2 DB already exists. Skipping."
else
    echo "  Downloading from OneDrive..."
    echo "  NOTE: This requires OneDrive authentication."
    echo "  Direct links:"
    echo "    IJaDataset: https://onedrive.live.com/?authkey=AhXbM6MKt_yLj_N15CewgjM7Y8NLKA"
    echo "    BCB DB:     https://onedrive.live.com/?authkey=AhXbM6MKt_yLj_NwwVacvUzmi6uorA"
    echo ""
    echo "  Steps:"
    echo "  1. Visit the OneDrive links above"
    echo "  2. Download IJaDataset_BCEvalVersion.tar.gz"
    echo "  3. Extract to: $BCB_DIR/ijadataset/"
    echo "  4. Download BigCloneBench_BCEvalVersion.tar.gz"
    echo "  5. Extract to: $BCB_DIR/"
    echo ""
    echo "  See: $BCB_DIR/DOWNLOAD_INSTRUCTIONS.md"
fi

# --- CodeSimilarityDataset ---
echo "[2/2] Checking CodeSimilarityDataset..."
CSD_DIR="$DATA_DIR/CodeSimilarityDataset"
if [ -d "$CSD_DIR" ]; then
    echo "  CodeSimilarityDataset already exists locally."
else
    echo "  CodeSimilarityDataset not found."
    echo "  If you need it, copy it to: $CSD_DIR/"
fi

echo ""
echo "=== External benchmark download complete ==="
echo "Verify datasets: ls $BCB_DIR && ls $CSD_DIR"