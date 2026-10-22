#!/usr/bin/env bash
# Train the equal-weight candidate and decide whether it may ship.
#
# Two properties this script is built around:
#   * it never writes the shipped artifact - the candidate goes to $OUT and a
#     human copies it only after the gate passes;
#   * feature extraction is cached in $CACHE, so a re-run after a crash or a
#     changed training mix costs the logistic fit, not the embeddings.
#
# Set DRY_RUN=1 to print the commands without running them.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

OUT="${OUT:-$REPORT_ROOT/fusion_training/equal}"
CACHE="${CACHE:-$REPORT_ROOT/fusion_training/.cache/features.jsonl}"
FOLDS="${FOLDS:-5}"
DATASETS="${DATASETS:-IR-Plag-Dataset conplag kaggle_student_code}"

require_datasets

read -r -a DATASET_ARRAY <<< "$DATASETS"
TRAIN_CMD=(
  "$PYTHON_BIN" -m src.backend.benchmark fusion-train-learned
  --datasets "${DATASET_ARRAY[@]}"
  --dataset-roots "${DATA_ROOT_ARRAY[@]}"
  --cv-folds "$FOLDS"
  --dataset-weighting equal
  --cache "$CACHE"
  --output "$OUT"
  --artifact "$OUT/model_equal.json"
)
GATE_CMD=("$PYTHON_BIN" -m src.backend.benchmark fusion-gate --report "$OUT")

echo "== learned fusion training (equal dataset weighting) =="
echo "output:   $OUT"
echo "cache:    $CACHE"
echo "datasets: $DATASETS"
echo "folds:    $FOLDS"
echo

if [[ -n "${DRY_RUN:-}" ]]; then
  printf 'would run:'; printf ' %q' "${TRAIN_CMD[@]}"; echo
  printf 'then:     '; printf ' %q' "${GATE_CMD[@]}"; echo
  exit 0
fi

mkdir -p "$OUT" "$(dirname "$CACHE")"
"${TRAIN_CMD[@]}"

echo
echo "== gate (per corpus, against the shipped artifact) =="
set +e
"${GATE_CMD[@]}"
GATE_STATUS=$?
set -e

echo
if [[ "$GATE_STATUS" -eq 0 ]]; then
  echo "Candidate passed. Promote it only with an explicit commit:"
  echo "  cp $OUT/model_equal.json src/backend/engines/similarity/models/learned_fusion_model.json"
  echo "  git add src/backend/engines/similarity/models/learned_fusion_model.json && git commit"
else
  echo "Candidate did not pass. Keep the shipped artifact:"
  echo "  git checkout -- src/backend/engines/similarity/models/learned_fusion_model.json"
fi
exit "$GATE_STATUS"
