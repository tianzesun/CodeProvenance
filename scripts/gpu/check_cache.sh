#!/usr/bin/env bash
# Check that the cached feature rows still match live extraction.
#
# The feature cache is what makes a retrain cost seconds instead of minutes, so
# it is also what silently changes a retrain's result when it was written by a
# different extractor or embedding model. This re-extracts a few cached pairs
# and compares every feature. Non-zero exit means: delete the cache and
# re-extract before believing the training numbers.
#
# Overridable: CACHE=... SAMPLE=5 DATASETS="IR-Plag-Dataset conplag" SEED=0
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

CACHE="${CACHE:-$REPORT_ROOT/fusion_training/.cache/features.jsonl}"
SAMPLE="${SAMPLE:-5}"
DATASETS="${DATASETS:-IR-Plag-Dataset conplag kaggle_student_code}"
SEED="${SEED:-0}"

if [[ ! -f "$CACHE" ]]; then
  echo "no feature cache at $CACHE; nothing to check" >&2
  exit 2
fi

require_datasets

read -r -a DATASET_ARRAY <<< "$DATASETS"
CHECK_CMD=(
  "$PYTHON_BIN" -m src.backend.benchmark feature-cache-check
  --cache "$CACHE"
  --datasets "${DATASET_ARRAY[@]}"
  --dataset-roots "${DATA_ROOT_ARRAY[@]}"
  --sample "$SAMPLE"
  --seed "$SEED"
)

echo "== feature cache check =="
echo "cache:    $CACHE"
echo "datasets: $DATASETS"
echo "sample:   $SAMPLE pairs"
echo

if [[ -n "${DRY_RUN:-}" ]]; then
  printf 'would run:'; printf ' %q' "${CHECK_CMD[@]}"; echo
  exit 0
fi

set +e
"${CHECK_CMD[@]}"
STATUS=$?
set -e

echo
if [[ "$STATUS" -eq 0 ]]; then
  echo "Cache is trustworthy: retraining will reuse rows the current code reproduces."
else
  echo "Cache is stale. Re-extract before the next retrain:"
  echo "  rm $CACHE"
  echo "  bash scripts/gpu/train_equal.sh   # rebuilds the cache from scratch"
fi
exit "$STATUS"
