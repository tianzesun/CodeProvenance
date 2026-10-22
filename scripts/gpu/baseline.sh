#!/usr/bin/env bash
# Freeze "what the shipped artifact scores on THIS host" as the gate's bar.
#
# The corpora are not identical between machines (kaggle_student_code is
# assembled locally rather than downloaded), so a bar measured elsewhere does
# not transfer. Run eval_real_tools.sh first with the shipped artifact in place,
# then this script: it keeps the newest report per corpus and writes a manifest
# with the corpus fingerprints and the artifact hash, so a later run can tell
# whether the bar still belongs to this host and this artifact.
#
#   bash scripts/gpu/baseline.sh
#   BASELINE_REPORT=reports/engine_evaluation_shipped bash scripts/gpu/train_equal.sh
#
# Set DRY_RUN=1 to print what it would do.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

SRC="${SRC:-$REPORT_ROOT/engine_evaluation}"
OUT="${OUT:-$REPORT_ROOT/engine_evaluation_shipped}"
export BASELINE_SRC="$SRC" BASELINE_OUT="$OUT" DATA_ROOTS REPORT_ROOT
export GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || true)}"

require_datasets

echo "== host baseline =="
echo "source: $SRC"
echo "output: $OUT"
echo

if [[ -n "${DRY_RUN:-}" ]]; then
  echo "would copy the newest ENGINE_EVAL_*.json per corpus and write BASELINE.json"
  exit 0
fi

"$PYTHON_BIN" - <<'PY'
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.backend.benchmark.corpus_fingerprint import (
    PRODUCT_CORPORA,
    corpus_fingerprints,
)
from src.backend.benchmark.gate import collect_scores
from src.backend.engines.scoring.learned_fusion import ARTIFACT_NAME, MODELS_DIR

source = Path(os.environ["BASELINE_SRC"])
output = Path(os.environ["BASELINE_OUT"])

scores, used = collect_scores([source])
if not scores:
    raise SystemExit(
        f"no engine-eval reports under {source}; run scripts/gpu/eval_real_tools.sh first"
    )
missing = sorted(set(PRODUCT_CORPORA) - set(scores))
if missing:
    raise SystemExit(
        "the baseline is incomplete, missing: "
        + ", ".join(missing)
        + f"\n  measure them first, then re-run this script (source: {source})"
    )

output.mkdir(parents=True, exist_ok=True)
for path in used:
    shutil.copy2(path, output / path.name)

artifact = MODELS_DIR / ARTIFACT_NAME
artifact_sha = (
    hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None
)

roots = os.environ["DATA_ROOTS"].split()
fingerprints = corpus_fingerprints(
    roots, PRODUCT_CORPORA, Path(os.environ["REPORT_ROOT"]) / "fusion_training" / "_setup_probe"
)

manifest = {
    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "commit": os.environ.get("GIT_COMMIT") or None,
    "artifact": str(artifact),
    "artifact_sha256": artifact_sha,
    "scores": scores,
    "reports": sorted(path.name for path in used),
    "corpus_fingerprints": fingerprints,
}
(output / "BASELINE.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)

print("dataset                 fused AUC   fingerprint")
print("-" * 48)
for dataset in PRODUCT_CORPORA:
    print(f"{dataset:22} {scores[dataset]:9.4f}   {fingerprints.get(dataset)}")
print()
print(f"artifact:  {artifact.name} sha256={(artifact_sha or 'missing')[:16]}")
print(f"manifest:  {output / 'BASELINE.json'}")
print()
print("This is now the default bar for scripts/gpu/train_equal.sh and")
print("eval_real_tools.sh. Refresh it after promoting a new artifact, or after")
print("changing a corpus.")
PY
