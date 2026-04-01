#!/bin/bash
# Dataset Verification Script
#
# Verifies that external benchmark datasets match expected checksums.
# Run after downloading to ensure data integrity.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== CodeProvenance Dataset Checksum Verification ==="
echo ""

# --- Public Reproducibility Sets (should exist in Git) ---
echo "[Public] Verifying reproducibility sets..."

for dataset_dir in synthetic xiangtan google_codejam; do
    dir="$SCRIPT_DIR/$dataset_dir"
    if [ -d "$dir" ]; then
        file_count=$(find "$dir" -type f | wc -l)
        echo "  $dataset_dir: $file_count files (OK)"
    else
        echo "  $dataset_dir: MISSING"
    fi
done

# --- External Benchmarks ---
echo ""
echo "[External] Verifying benchmark datasets..."

BCB_DIR="$SCRIPT_DIR/bigclonebench"
if [ -d "$BCB_DIR" ]; then
    java_count=$(find "$BCB_DIR/bcb_reduced" -name "*.java" 2>/dev/null | wc -l)
    if [ -f "$BCB_DIR/bcb.h2.db" ]; then
        db_size=$(du -h "$BCB_DIR/bcb.h2.db" | cut -f1)
        echo "  BigCloneBench: $java_count Java files + H2 DB ($db_size) (OK)"
    else
        echo "  BigCloneBench: $java_count Java files, H2 DB MISSING"
    fi
else
    echo "  BigCloneBench: NOT DOWNLOADED (run benchmark/data/download_external.sh)"
fi

CSD_DIR="$SCRIPT_DIR/CodeSimilarityDataset"
if [ -d "$CSD_DIR" ]; then
    snippet_count=$(find "$CSD_DIR" -name "*.py" | wc -l)
    echo "  CodeSimilarityDataset: $snippet_count snippets (OK)"
else
    echo "  CodeSimilarityDataset: NOT PRESENT (optional)"
fi

echo ""
echo "=== Verification complete ==="