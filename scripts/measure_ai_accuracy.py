"""Measure AI-detection accuracy on the locally available corpora.

Unlike ``measure_human_fp.py`` (false positives on human code only), this
script measures the *discrimination* of the detector: ROC-AUC, accuracy at the
shipped thresholds, and the operating points that matter for grading.

Corpora used (all local, no network):
  - ``aigcodeset/data/ai``    : labelled AI-generated Python
  - ``aigcodeset/data/human`` : labelled human Python
  - ``kaggle_student_code``   : real novice student submissions (human-only,
                                used as a false-positive check)

Usage:
    python scripts/measure_ai_accuracy.py --limit 400
    python scripts/measure_ai_accuracy.py --limit 400 --dump-scores out.json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DATASETS = REPO_ROOT / "data" / "datasets"


def _iter_python(directory: Path) -> list[tuple[str, str]]:
    """Return (name, code) for every readable .py file under ``directory``."""
    if not directory.is_dir():
        return []
    samples: list[tuple[str, str]] = []
    for path in sorted(directory.rglob("*.py")):
        try:
            code = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if code.strip():
            samples.append((str(path.relative_to(directory)), code))
    return samples


def _subsample(
    samples: list[tuple[str, str]], limit: int, seed: int
) -> list[tuple[str, str]]:
    """Deterministically subsample so runs are comparable across invocations."""
    if limit <= 0 or len(samples) <= limit:
        return samples
    rng = random.Random(seed)
    picked = rng.sample(range(len(samples)), limit)
    return [samples[i] for i in sorted(picked)]


def _roc_auc(positives: list[float], negatives: list[float]) -> float:
    """ROC-AUC via the rank (Mann-Whitney U) identity, ties averaged."""
    if not positives or not negatives:
        return float("nan")
    combined = [(v, 1) for v in positives] + [(v, 0) for v in negatives]
    combined.sort(key=lambda item: item[0])
    ranks: dict[int, float] = {}
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1
    rank_sum = sum(ranks[k] for k, (_, label) in enumerate(combined) if label == 1)
    n_pos, n_neg = len(positives), len(negatives)
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _rate_at(scores: list[float], threshold: float) -> float:
    """Fraction of ``scores`` at or above ``threshold``."""
    if not scores:
        return float("nan")
    return sum(1 for s in scores if s >= threshold) / len(scores)


def _summarize(scores: list[float]) -> dict[str, float]:
    """Descriptive statistics plus flag rates at the shipped thresholds."""
    if not scores:
        return {"count": 0}
    ordered = sorted(scores)

    def pct(p: float) -> float:
        idx = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
        return ordered[idx]

    return {
        "count": len(scores),
        "mean": round(statistics.fmean(scores), 4),
        "median": round(pct(0.5), 4),
        "p90": round(pct(0.9), 4),
        "max": round(ordered[-1], 4),
        "rate_at_0.40": round(_rate_at(scores, 0.40), 4),
        "rate_at_0.70": round(_rate_at(scores, 0.70), 4),
    }


def main() -> int:
    """Score both corpora and report discrimination and false-positive rates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", default=str(DEFAULT_DATASETS))
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Max samples per labelled class (0 = all).",
    )
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument(
        "--student-limit",
        type=int,
        default=0,
        help="Max Kaggle student files to score (0 = all, 174 by default).",
    )
    parser.add_argument("--dump-scores", default=None)
    parser.add_argument(
        "--dump-signals",
        default=None,
        help="Write per-file raw signals to JSON and exit. The expensive part "
        "(transformer perplexity + ML classifier) does not depend on the "
        "fusion strategy, so dumping once lets fusion variants be A/B "
        "compared offline without re-running inference.",
    )
    args = parser.parse_args()

    datasets = Path(args.datasets)
    ai = _subsample(
        _iter_python(datasets / "aigcodeset" / "data" / "ai"), args.limit, args.seed
    )
    human = _subsample(
        _iter_python(datasets / "aigcodeset" / "data" / "human"), args.limit, args.seed
    )
    students = _subsample(
        _iter_python(datasets / "kaggle_student_code"),
        args.student_limit or 10**9,
        args.seed,
    )

    if not ai or not human:
        print(
            f"ERROR: need both AIGCodeSet classes under {datasets}. "
            "Run data/datasets/download_datasets.sh first.",
            file=sys.stderr,
        )
        return 1

    from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

    detector = AIDetectionOrchestrator()

    def score_all(samples: list[tuple[str, str]]) -> list[float]:
        out: list[float] = []
        for _name, code in samples:
            try:
                result = detector.analyze(code, language="python")
                out.append(float(result.get("ai_probability", 0.0)))
            except Exception:  # pragma: no cover - defensive
                out.append(0.0)
        return out

    if args.dump_signals:
        from src.backend.engines.similarity.ai_detection import AIDetectionEngine

        engine = AIDetectionEngine()

        def collect(samples: list[tuple[str, str]]) -> dict[str, dict]:
            out: dict[str, dict] = {}
            for name, code in samples:
                try:
                    res = engine.analyze(code, "python")
                    out[name] = {
                        "signals": res.get("signals", {}),
                        "ai_probability": res.get("ai_probability", 0.0),
                        "n_lines": len([ln for ln in code.splitlines() if ln.strip()]),
                    }
                except Exception:  # pragma: no cover - defensive
                    out[name] = {"signals": {}, "ai_probability": 0.0, "n_lines": 0}
            return out

        payload = {
            "ai": collect(ai),
            "human": collect(human),
            "students": collect(students) if students else {},
        }
        Path(args.dump_signals).write_text(
            json.dumps(payload, indent=1), encoding="utf-8"
        )
        print(f"wrote signals to {args.dump_signals}")
        return 0

    ai_scores = score_all(ai)
    human_scores = score_all(human)
    student_scores = score_all(students) if students else []

    auc = _roc_auc(ai_scores, human_scores)
    report = {
        "ai": _summarize(ai_scores),
        "human": _summarize(human_scores),
        "student_human": _summarize(student_scores) if student_scores else {"count": 0},
        "roc_auc": round(auc, 4) if auc == auc else None,
        "derived": {
            "tpr_at_0.40": round(_rate_at(ai_scores, 0.40), 4),
            "fpr_at_0.40_on_human": round(_rate_at(human_scores, 0.40), 4),
            "tpr_at_0.70": round(_rate_at(ai_scores, 0.70), 4),
            "fpr_at_0.70_on_human": round(_rate_at(human_scores, 0.70), 4),
        },
    }

    print(json.dumps(report, indent=2))
    if args.dump_scores:
        Path(args.dump_scores).write_text(
            json.dumps(
                {
                    "ai": dict(ai),
                    "human": dict(human),
                    "students": dict(students) if students else {},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
