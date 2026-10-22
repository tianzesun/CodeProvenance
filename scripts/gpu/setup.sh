#!/usr/bin/env bash
# Verify the GPU host before spending time on a run.
#
# This is read-only against the repo: it loads dataset labels (no model, no
# scoring) and runs each external tool once on two toy files, so a broken tool
# fails in seconds here instead of after an hour of evaluation. Run it first on a
# fresh machine.
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
import os
from pathlib import Path

from src.backend.benchmark.corpus_fingerprint import pair_fingerprint
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
    print(
        f"  {name:22} pairs={len(pairs):4} "
        f"distinct_texts={len(texts):4} "
        f"per_pair_encodings={2 * len(pairs):5} "
        f"fingerprint={pair_fingerprint(pairs)}"
    )
PY

echo
echo "== external tools (gitignored, copy them from a host that has them) =="
"$PYTHON_BIN" - <<'PY'
"""Smoke-test each external tool on two toy files.

Presence is not availability: the Dolos CLI is a Node script whose native
parsers are compiled against one Node ABI, so a copied checkout starts fine
(``--help`` works) and then dies on the first real run with a
NODE_MODULE_VERSION mismatch. Only running it proves anything.
"""

import signal

JAVA_A = "public class A { int f(int x) { return x + 1; } }\n"
JAVA_B = "public class B { int f(int y) { return y + 1; } }\n"
PY_A = "def f(x):\n    return x + 1\n"
PY_B = "def f(y):\n    return y + 1\n"


def probe(tool_id: str, engine, submissions: dict, pair: tuple) -> None:
    """Run one tool on a trivial pair and print a verdict."""
    try:
        available = engine.is_available()
    except Exception as exc:  # noqa: BLE001 - a broken tool must not abort setup
        print(f"  {tool_id:8} BROKEN while checking availability: {exc}")
        return
    if not available:
        print(f"  {tool_id:8} MISSING binary; this corpus will report it unavailable")
        return

    def _timeout(signum, frame):  # pragma: no cover - environment specific
        raise TimeoutError

    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(300)
    try:
        payload = engine.run_batch(dict(submissions), [pair])
        scores = [item.get("score") for item in payload.get("pairs", [])]
        if not scores:
            print(f"  {tool_id:8} BROKEN: ran but returned no pair scores")
        else:
            print(f"  {tool_id:8} OK: scored a toy pair {scores[0]:.3f}")
    except Exception as exc:  # noqa: BLE001 - print the tool's own words
        detail = "\n".join(f"    {line}" for line in str(exc).splitlines()[:8])
        print(f"  {tool_id:8} BROKEN: {detail}")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


print("running each tool once on two toy files (this is the real check):")
try:
    from src.backend.benchmark.adapters.dolos_adapter import DolosBenchmarkEngine
    from src.backend.benchmark.adapters.jplag_adapter import JPlagAdapter
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"  cannot import the adapters: {exc}")

probe("jplag", JPlagAdapter(), {"A.java": JAVA_A, "B.java": JAVA_B}, ("A.java", "B.java"))
probe("dolos", DolosBenchmarkEngine(), {"a.py": PY_A, "b.py": PY_B}, ("a.py", "b.py"))
PY

echo
echo "== next =="
if [[ -f "$REPORT_ROOT/engine_evaluation_shipped/BASELINE.json" ]]; then
  echo "  bar:      $REPORT_ROOT/engine_evaluation_shipped (frozen on this host)"
else
  echo "  bar:      built-in constants; freeze this host's numbers first:"
  echo "              bash scripts/gpu/eval_real_tools.sh   # measure the shipped artifact"
  echo "              bash scripts/gpu/baseline.sh          # freeze them as the bar"
fi
echo "  bash scripts/gpu/train_equal.sh      # equal-weight retrain + gate"
echo "  bash scripts/gpu/eval_real_tools.sh  # JPlag/Dolos comparison + gate"
