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

# An IntegrityDesk-only run is not the comparison this script exists for.
# tools/external is gitignored, so a fresh GPU host has the corpora but no
# JPlag/Dolos until they are copied over; without this check the script would
# print a green gate and look like a successful external comparison.
if [[ -z "${ALLOW_MISSING_TOOLS:-}" ]]; then
  "$PYTHON_BIN" - "$OUT" "${TOOL_ARRAY[@]}" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
tools = sys.argv[2:]
newest: dict[str, Path] = {}
for path in out.rglob("ENGINE_EVAL_*.json"):
    try:
        dataset = json.loads(path.read_text(encoding="utf-8")).get("dataset_name")
    except (OSError, json.JSONDecodeError):
        continue
    if not dataset:
        continue
    previous = newest.get(dataset)
    if previous is None or path.stat().st_mtime > previous.stat().st_mtime:
        newest[dataset] = path
if not newest:
    sys.exit(f"ERROR: no ENGINE_EVAL_*.json under {out}")

missing: dict[str, list[str]] = {tool: [] for tool in tools}
for dataset, path in sorted(newest.items()):
    available = {
        entry.get("name")
        for entry in json.loads(path.read_text(encoding="utf-8")).get("scorers", [])
        if entry.get("available")
    }
    for tool in tools:
        if tool not in available:
            missing[tool].append(dataset)

if all(len(datasets) == len(newest) for datasets in missing.values()):
    print(
        "ERROR: none of the requested external tools produced any score:",
        ", ".join(tools),
        file=sys.stderr,
    )
    print(
        "tools/external/ is gitignored, so this host has no JPlag/Dolos yet.\n"
        "Copy them and re-run:\n"
        "  rsync -av --info=progress2 other-host:CodeProvenance/tools/external/ tools/external/\n"
        "  java -jar tools/external/JPlag/jplag.jar --help   # JPlag needs a JDK\n"
        "Set ALLOW_MISSING_TOOLS=1 to gate IntegrityDesk alone.",
        file=sys.stderr,
    )
    sys.exit(2)

for tool, datasets in missing.items():
    if datasets:
        print(f"warning: {tool} produced no scores for {', '.join(datasets)}")
PY
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
