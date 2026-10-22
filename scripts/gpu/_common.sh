#!/usr/bin/env bash
# Shared environment for the GPU benchmark scripts.
#
# Source this file; do not execute it. Everything is overrideable from the
# environment, so the same checkout can point at whatever paths the GPU host
# uses:
#
#   PYTHON_BIN=/opt/conda/bin/python \
#   DATA_ROOTS="/data/corpora /data/more" \
#   REPORT_ROOT=/data/reports \
#   bash scripts/gpu/train_equal.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif [[ -x "$REPO_ROOT/venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_ROOT/venv/bin/python"
elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

DATA_ROOTS="${DATA_ROOTS:-$REPO_ROOT/data/datasets $REPO_ROOT/data/bigger_datasets}"
REPORT_ROOT="${REPORT_ROOT:-$REPO_ROOT/reports}"

read -r -a DATA_ROOT_ARRAY <<< "$DATA_ROOTS"
export PYTHON_BIN DATA_ROOTS REPORT_ROOT

# A host-measured bar, when one exists. Two hosts can hold different copies of a
# corpus (kaggle_student_code is assembled locally), so the shipped-artifact
# constants do not transfer; scripts/gpu/baseline.sh freezes this host's numbers
# next to the reports they came from.
if [[ -z "${BASELINE_REPORT:-}" \
    && -f "$REPORT_ROOT/engine_evaluation_shipped/BASELINE.json" ]]; then
  BASELINE_REPORT="$REPORT_ROOT/engine_evaluation_shipped"
fi
export BASELINE_REPORT="${BASELINE_REPORT:-}"

# The corpora are gitignored, so a fresh clone has code but no data. Fail with
# the path a human can fix instead of a stack trace from deep in a loader.
require_datasets() {
  local existing=()
  for root in "${DATA_ROOT_ARRAY[@]}"; do
    if [[ -d "$root" ]]; then
      existing+=("$root")
    else
      echo "note: dataset root does not exist, skipping: $root" >&2
    fi
  done
  if [[ "${#existing[@]}" -eq 0 ]]; then
    echo "" >&2
    echo "No dataset root exists. Copy the corpora from the machine that has them:" >&2
    echo "  rsync -av --info=progress2 other-host:CodeProvenance/data/datasets/ data/datasets/" >&2
    echo "Then re-run this script, or set DATA_ROOTS to wherever they landed." >&2
    exit 2
  fi
  DATA_ROOT_ARRAY=("${existing[@]}")
}

# Report the device the run will actually use. A CPU-only torch build on a GPU
# host is the failure this catches: the job would finish correctly but take
# hours instead of minutes.
report_device() {
  "$PYTHON_BIN" - <<'PY'
import sys

try:
    import torch
except Exception as exc:  # pragma: no cover - environment specific
    print(f"torch: NOT IMPORTABLE ({exc})")
    print("prewarm: will be skipped; scores still correct, run slower")
    sys.exit(0)

print(f"torch: {torch.__version__}")
if torch.cuda.is_available():
    print(f"cuda: available, {torch.cuda.get_device_name(0)}")
    print(f"cuda: {torch.cuda.device_count()} device(s), torch built with {torch.version.cuda}")
else:
    print("cuda: NOT AVAILABLE - this host will run the embedding on CPU")
    print("prewarm: local; expect CPU timings, not GPU timings")
PY
}
