#!/usr/bin/env bash
# Verify the GPU host before spending time on a run.
#
# This is read-only: it loads dataset labels (no model, no scoring) and prints
# what the training scripts will use. Run it first on a fresh machine.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

echo "== checkout =="
echo "root:    $REPO_ROOT"
echo "commit:  $(git rev-parse --short HEAD) $(git log -1 --format=%s)"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "warning: working tree is dirty; a measurement from it is not reproducible" >&2
fi

echo
echo "== python =="
echo "python:  $PYTHON_BIN"
"$PYTHON_BIN" --version
"$PYTHON_BIN" -c 'import src.backend.benchmark as m; print("module: ", m.__file__)'

echo
echo "== device =="
report_device

echo
echo "== checkout freshness =="
if "$PYTHON_BIN" -m src.backend.benchmark fusion-train-learned --help 2>/dev/null \
    | grep -q -- "--prewarm-embeddings\|--no-prewarm-embeddings"; then
  echo "learned training: has --no-prewarm-embeddings"
else
  echo "learned training: STALE checkout (no prewarm flag); git pull first" >&2
  exit 3
fi
if "$PYTHON_BIN" -m src.backend.benchmark fusion-gate --help >/dev/null 2>&1; then
  echo "gate: available (fusion-gate)"
else
  echo "gate: STALE checkout (no fusion-gate command); git pull first" >&2
  exit 3
fi

echo
echo "== corpora =="
require_datasets
export DATA_ROOTS="${DATA_ROOT_ARRAY[*]}"
"$PYTHON_BIN" - <<'PY'
import hashlib
import os
from pathlib import Path

from src.backend.benchmark.runners.learned_fusion_training_runner import (
    LearnedFusionTrainingRunner,
)

roots = [Path(part) for part in os.environ["DATA_ROOTS"].split()]
runner = LearnedFusionTrainingRunner(
    output_dir=Path(os.environ["REPORT_ROOT"]) / "fusion_training" / "_setup_probe",
    dataset_roots=roots,
)
print(f"roots: {', '.join(str(root) for root in roots)}")
for name in ("IR-Plag-Dataset", "conplag", "kaggle_student_code"):
    try:
        pairs = runner.load_pairs([name])
    except (FileNotFoundError, ValueError) as exc:
        print(f"  {name:22} UNUSABLE: {exc}")
        continue
    texts = {
        text.strip()
        for pair in pairs
        for text in (pair.code_a, pair.code_b)
        if len(text.split()) >= 5
    }
    # Fingerprint the labelled pairs, not the directory: two hosts can hold the
    # same file count and still disagree on labels or on which files are paired.
    # A mismatch here means a baseline measured on one host does not transfer.
    digest = hashlib.sha256()
    for pair in sorted(pairs, key=lambda item: item.pair_id):
        digest.update(
            f"{pair.pair_id}|{pair.label}|"
            f"{hashlib.sha256(pair.code_a.encode()).hexdigest()[:16]}|"
            f"{hashlib.sha256(pair.code_b.encode()).hexdigest()[:16]}\n".encode()
        )
    print(
        f"  {name:22} pairs={len(pairs):4} "
        f"distinct_texts={len(texts):4} "
        f"per_pair_encodings={2 * len(pairs):5} "
        f"fingerprint={digest.hexdigest()[:16]}"
    )
PY

echo
echo "== external tools (gitignored, copy them from a host that has them) =="
for tool in tools/external/JPlag/jplag.jar tools/external/dolos-cli; do
  if [[ -e "$tool" ]]; then
    echo "present: $tool"
  else
    echo "MISSING: $tool - eval_real_tools.sh will report the tool as unavailable"
  fi
done

echo
echo "== next =="
echo "  bash scripts/gpu/train_equal.sh      # equal-weight retrain + gate"
echo "  bash scripts/gpu/eval_real_tools.sh  # JPlag/Dolos comparison + gate"
echo
echo "If this host has a different copy of a corpus (compare fingerprint above),"
echo "measure the bar here first and pass it to the gate:"
echo "  BASELINE_REPORT=reports/engine_evaluation_shipped bash scripts/gpu/train_equal.sh"
