"""Offline sweep of the classifier/heuristic blend weight over dumped scores.

Usage:
    python scripts/sweep_ml_blend.py \\
        --fp-dump /tmp/opencode/G_codelm \\
        --ai-dump /tmp/opencode/G_codelm_ai.json \\
        --weights 0.5,0.65,0.8,1.0

``measure_human_fp.py --dump-scores`` and ``measure_ai_accuracy.py
--dump-scores`` record, per file, the fused score plus the blend internals
(``method``, ``ml_score``, ``heuristic_score``, ``lines``). Inference is the
expensive part of a corpus run and does not depend on the blend, so this script
replays the *real* ``blend_ml_heuristic`` for each candidate
``ml_base_weight`` instead of re-scoring — the whole trade-off curve costs
seconds.

Caveat: the dumped ``ai_probability`` also passed through
``apply_fp_safeguards`` (low-confidence damping contracts low scores toward
0.5), which the replay omits. Treat the table as a ranking of candidates and
confirm the winner with a real ``measure_*`` run.
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.backend.engines.ai.orchestrator import blend_ml_heuristic

THRESHOLDS = (0.40, 0.50, 0.70)


def _newest_report(target: Path) -> Path:
    """Resolve a dump argument to a file (a directory means its newest report)."""
    if target.is_file():
        return target
    candidates = sorted(glob.glob(str(target / "*.json")))
    if not candidates:
        raise SystemExit(f"No JSON dump found under {target}")
    return Path(candidates[-1])


def load_fp_rows(target: Path) -> list[dict[str, Any]]:
    """Per-file rows from a measure_human_fp.py report."""
    payload = json.loads(_newest_report(target).read_text(encoding="utf-8"))
    rows = payload.get("per_file")
    if not rows:
        raise SystemExit(f"{target} has no per_file rows; re-run with --dump-scores")
    return rows


def load_ai_rows(target: Path) -> dict[str, list[dict[str, Any]]]:
    """{ai, human, students} rows from a measure_ai_accuracy.py dump."""
    payload = json.loads(target.read_text(encoding="utf-8"))
    missing = [key for key in ("ai", "human") if not payload.get(key)]
    if missing:
        raise SystemExit(f"{target} is missing {missing}; re-run with --dump-scores")
    return payload


def replay(row: dict[str, Any], weight: float) -> tuple[float, bool]:
    """Score a dumped row with ``ml_base_weight`` overridden.

    Rows scored without the classifier (``ml_score`` is None) keep the dumped
    fused score: the blend never ran for them.
    """
    ml, heuristic = row.get("ml_score"), row.get("heuristic_score")
    lines = row.get("lines")
    if ml is None or heuristic is None or lines is None:
        return float(row["ai_probability"]), False
    score, capped = blend_ml_heuristic(
        float(ml), float(heuristic), int(lines), {"ml_base_weight": weight}
    )
    return round(score, 3), capped


def rate_at(scores: list[float], threshold: float) -> float:
    """Fraction of scores at or above ``threshold``."""
    return (
        sum(1 for score in scores if score >= threshold) / len(scores)
        if scores
        else 0.0
    )


def roc_auc(positives: list[float], negatives: list[float]) -> float:
    """ROC-AUC via the rank (Mann-Whitney U) identity, ties averaged."""
    if not positives or not negatives:
        return float("nan")
    combined = sorted([(v, 1) for v in positives] + [(v, 0) for v in negatives])
    ranks: dict[int, float] = {}
    index = 0
    while index < len(combined):
        end = index
        while end + 1 < len(combined) and combined[end + 1][0] == combined[index][0]:
            end += 1
        average_rank = (index + end) / 2.0 + 1
        for position in range(index, end + 1):
            ranks[position] = average_rank
        index = end + 1
    rank_sum = sum(ranks[i] for i, (_, label) in enumerate(combined) if label)
    n_pos, n_neg = len(positives), len(negatives)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def sweep(
    fp_rows: list[dict[str, Any]],
    ai_rows: dict[str, list[dict[str, Any]]],
    weights: list[float],
) -> list[dict[str, Any]]:
    """Metrics for each candidate weight (student FP and AI-vs-human ranking)."""
    results: list[dict[str, Any]] = []
    for weight in weights:
        students = [replay(row, weight)[0] for row in fp_rows]
        ai = [replay(row, weight)[0] for row in ai_rows["ai"]]
        human = [replay(row, weight)[0] for row in ai_rows["human"]]
        results.append(
            {
                "weight": weight,
                "flagged": {t: rate_at(students, t) for t in THRESHOLDS},
                "student_mean": statistics.fmean(students) if students else 0.0,
                "ai_rate_at_0.40": rate_at(ai, 0.40),
                "ai_rate_at_0.70": rate_at(ai, 0.70),
                "ai_mean": statistics.fmean(ai) if ai else 0.0,
                "auc": roc_auc(ai, human),
                "capped": sum(1 for row in fp_rows if replay(row, weight)[1]),
            }
        )
    return results


def _self_check(fp_rows: list[dict[str, Any]]) -> str | None:
    """Compare the replay at the shipped weight against the dump's own flags."""
    replayed = sum(1 for row in fp_rows if replay(row, 0.5)[1])
    dumped = sum(1 for row in fp_rows if row.get("disagreement_capped") is True)
    if replayed == dumped:
        return None
    return (
        f"replay capped {replayed} files vs dump {dumped}: the dump was written by a "
        "different blend config or line-count definition; re-run the measurement "
        "before trusting these numbers"
    )


def main() -> int:
    """Print the weight sweep table plus a replay self-check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fp-dump", type=Path, required=True, help="measure_human_fp --out"
    )
    parser.add_argument(
        "--ai-dump", type=Path, required=True, help="measure_ai_accuracy --dump-scores"
    )
    parser.add_argument("--weights", default="0.5,0.65,0.8,1.0")
    args = parser.parse_args()

    weights = [float(part) for part in args.weights.split(",") if part.strip()]
    fp_rows = load_fp_rows(args.fp_dump)
    ai_rows = load_ai_rows(args.ai_dump)
    results = sweep(fp_rows, ai_rows, weights)

    print(
        f"student corpus n={len(fp_rows)}  ai n={len(ai_rows['ai'])}  human n={len(ai_rows['human'])}"
    )
    header = (
        f"{'weight':>6} | {'FP@0.40':>7} {'FP@0.50':>7} {'FP@0.70':>7} {'stud mean':>9} "
        f"| {'AI@0.40':>7} {'AI@0.70':>7} {'AI mean':>7} {'AUC':>6} {'capped':>6}"
    )
    print(header)
    print("-" * len(header))
    for row in results:
        flagged = row["flagged"]
        print(
            f"{row['weight']:>6.2f} | {flagged[0.40]:>7.3f} {flagged[0.50]:>7.3f} "
            f"{flagged[0.70]:>7.3f} {row['student_mean']:>9.4f} "
            f"| {row['ai_rate_at_0.40']:>7.3f} {row['ai_rate_at_0.70']:>7.3f} "
            f"{row['ai_mean']:>7.4f} {row['auc']:>6.4f} {row['capped']:>6d}"
        )

    drift = _self_check(fp_rows)
    if drift:
        print(f"\nWARNING: {drift}", file=sys.stderr)
        return 2
    print("\nself-check ok: replay at the shipped weight reproduces the dumped caps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
