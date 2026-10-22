#!/usr/bin/env bash
# Measure the product against real JPlag/Dolos on every labeled corpus.
#
# This is the accuracy measurement, not a training run: it scores the shipped
# artifact exactly as production does, next to the external tools, and gates
# the production `fused` AUC per corpus.
#
# Set DRY_RUN=1 to print the commands without running them.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

OUT="${OUT:-$REPORT_ROOT/engine_evaluation}"
TOOLS="${TOOLS:-jplag dolos}"
BATCH_SIZE="${BATCH_SIZE:-80}"

require_datasets

read -r -a TOOL_ARRAY <<< "$TOOLS"

echo "== engine evaluation (IntegrityDesk + $TOOLS) =="
echo "output: $OUT"
echo

for dataset in IR-Plag-Dataset conplag kaggle_student_code; do
  EVAL_CMD=(
    "$PYTHON_BIN" -m src.backend.benchmark engine-eval
    --dataset "$dataset"
    --dataset-roots "${DATA_ROOT_ARRAY[@]}"
    --external-batch-size "$BATCH_SIZE"
    --tools "${TOOL_ARRAY[@]}"
    --output "$OUT"
  )
  echo "-- $dataset"
  if [[ -n "${DRY_RUN:-}" ]]; then
    printf 'would run:'; printf ' %q' "${EVAL_CMD[@]}"; echo
    continue
  fi
  mkdir -p "$OUT"
  "${EVAL_CMD[@]}"
  echo
done

GATE_CMD=("$PYTHON_BIN" -m src.backend.benchmark fusion-gate --report "$OUT")
if [[ -n "${DRY_RUN:-}" ]]; then
  printf 'then:     '; printf ' %q' "${GATE_CMD[@]}"; echo
  exit 0
fi

echo "== gate (production fused score, per corpus) =="
set +e
"${GATE_CMD[@]}"
GATE_STATUS=$?
set -e

echo
if [[ "$GATE_STATUS" -ne 0 ]]; then
  echo "A corpus is below the shipped artifact. This is a measurement of the"
  echo "current state, not a regression caused by this run: check whether the"
  echo "report picked up a different build or corpus revision."
fi
exit "$GATE_STATUS"
