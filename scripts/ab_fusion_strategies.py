"""A/B compare fusion strategies over a pre-computed signal dump.

The expensive part of AI detection (transformer perplexity + ML classifier) is
independent of the fusion strategy, so ``measure_ai_accuracy.py --dump-signals``
captures it once. This script replays the raw signals through the old and new
fusion functions and reports the metrics that matter, so a fusion change can be
justified with numbers instead of intuition.

Usage:
    python scripts/ab_fusion_strategies.py --signals /tmp/signals.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from measure_ai_accuracy import _rate_at, _roc_auc  # noqa: E402

CORPUS_DIRS = {
    "ai": "aigcodeset/data/ai",
    "human": "aigcodeset/data/human",
    "students": "kaggle_student_code",
}


def _old_heuristic_fuse(signals: dict[str, float]) -> float:
    """The pre-change heuristic fusion: a fixed unweighted blend."""
    pattern = signals.get("pattern_library", 0.0)
    docstring = signals.get("docstring_density", 0.0)
    stylometry = signals.get("stylometry", 0.0)
    burstiness = signals.get("burstiness", 0.0)
    raw = 0.45 * pattern + 0.20 * docstring + 0.20 * stylometry + 0.15 * burstiness
    perplexity_signal = signals.get("perplexity", 0.0)
    corroborated = docstring >= 0.25 or stylometry >= 0.60 or perplexity_signal >= 0.80
    boost = 0.18 * pattern if (pattern >= 0.30 and corroborated) else 0.0
    return 1.0 / (1.0 + math.exp(-6.0 * ((raw + boost) - 0.5)))


def _old_weighted_fuse(
    signals: dict[str, float], layer_weights: dict[str, float]
) -> float:
    """The pre-change Binoculars-path fusion: unweighted average."""
    total = weight_sum = 0.0
    for name, weight in layer_weights.items():
        if name in signals:
            total += signals[name] * weight
            weight_sum += weight
    if weight_sum == 0:
        return 0.5
    return 1.0 / (1.0 + math.exp(-5.5 * ((total / weight_sum) - 0.5)))


def _reliability_weighted_heuristic(
    signals: dict[str, float], code: str, language: str = "python", floor: float = 0.10
) -> float:
    """Candidate variant: weight each blend term by its reliability.

    This is the approach that was tried and **rejected** on measurement
    (grouped 5-fold CV AUC 0.528 vs 0.599 for the shipped fusion). It is kept
    here so the negative result stays reproducible rather than living only in
    prose, and so a future attempt to revisit it starts from real numbers.
    """
    from src.backend.engines.ai.reliability import assess_signal_reliability

    components = {
        "pattern_library": (signals.get("pattern_library", 0.0), 0.45),
        "docstring_density": (signals.get("docstring_density", 0.0), 0.20),
        "stylometry": (signals.get("stylometry", 0.0), 0.20),
        "burstiness": (signals.get("burstiness", 0.0), 0.15),
    }
    total = weight_sum = 0.0
    for name, (value, base_weight) in components.items():
        reliability = assess_signal_reliability(name, code, language) if code else 1.0
        if reliability <= 0.0:
            continue
        weight = base_weight * max(reliability, floor)
        total += value * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.5
    raw = total / weight_sum
    pattern = signals.get("pattern_library", 0.0)
    docstring = signals.get("docstring_density", 0.0)
    stylometry = signals.get("stylometry", 0.0)
    perplexity = signals.get("perplexity", 0.0)
    corroborated = docstring >= 0.25 or stylometry >= 0.60 or perplexity >= 0.80
    boost = 0.18 * pattern if (pattern >= 0.30 and corroborated) else 0.0
    return 1.0 / (1.0 + math.exp(-6.0 * ((raw + boost) - 0.5)))


def main() -> int:
    """Replay both fusion strategies and print a side-by-side comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--datasets", default=str(REPO_ROOT / "data" / "datasets"))
    args = parser.parse_args()

    from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

    detector = AIDetectionOrchestrator()
    dump = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    datasets = Path(args.datasets)

    def read(group: str, name: str) -> str:
        path = datasets / CORPUS_DIRS[group] / name
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def score_one(strategy: str, signals: dict[str, float], code: str) -> float:
        """Fuse one file's signals with the named strategy."""
        if strategy == "shipped_heuristic":
            return detector._heuristic_fuse(signals)
        if strategy == "candidate_reliability":
            return _reliability_weighted_heuristic(signals, code)
        return detector._weighted_fuse(signals)

    def replay(strategy: str) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for group, files in dump.items():
            out[group] = [
                score_one(strategy, rec.get("signals", {}), read(group, name))
                for name, rec in files.items()
            ]
        return out

    def grouped_cv(strategy: str, folds: int = 5) -> float:
        """Mean held-out AUC across folds grouped by AIGCodeSet problem id.

        Grouping matters: without it the same assignment can appear in both
        train and test, which flatters any tuned variant.
        """
        grouped: dict[str, dict[str, list[float]]] = {}
        for group in ("ai", "human"):
            for name, rec in dump.get(group, {}).items():
                problem = name.split("__")[0]
                grouped.setdefault(problem, {}).setdefault(group, []).append(
                    score_one(strategy, rec.get("signals", {}), read(group, name))
                )
        usable = sorted(p for p, v in grouped.items() if v.get("ai") and v.get("human"))
        if len(usable) < folds:
            return float("nan")
        buckets = [usable[i::folds] for i in range(folds)]
        total = 0.0
        for test in buckets:
            ai: list[float] = []
            human: list[float] = []
            for problem in test:
                ai.extend(grouped[problem]["ai"])
                human.extend(grouped[problem]["human"])
            total += _roc_auc(ai, human)
        return total / folds

    for path_name, shipped, candidate in [
        (
            "heuristic (Binoculars unavailable - default deploy)",
            "shipped_heuristic",
            "candidate_reliability",
        ),
        ("weighted (Binoculars available)", "shipped_weighted", "shipped_weighted"),
    ]:
        b = replay(shipped)
        a = replay(candidate)
        print(f"\n===== {path_name} =====")
        print(f"  SHIPPED   = {shipped}")
        print(f"  CANDIDATE = {candidate}")
        print(f"\n{'metric':<28}{'SHIPPED':>10}{'CANDIDATE':>11}{'delta':>10}")
        rows = [
            ("grouped CV roc_auc", grouped_cv(shipped), grouped_cv(candidate)),
            (
                "whole-set roc_auc",
                _roc_auc(b["ai"], b["human"]),
                _roc_auc(a["ai"], a["human"]),
            ),
            ("tpr@0.40", _rate_at(b["ai"], 0.40), _rate_at(a["ai"], 0.40)),
            (
                "fpr@0.40 (human)",
                _rate_at(b["human"], 0.40),
                _rate_at(a["human"], 0.40),
            ),
            (
                "fpr@0.70 (human)",
                _rate_at(b["human"], 0.70),
                _rate_at(a["human"], 0.70),
            ),
            ("tpr@0.70", _rate_at(b["ai"], 0.70), _rate_at(a["ai"], 0.70)),
        ]
        if dump.get("students"):
            rows.append(
                (
                    "student FP@0.40",
                    _rate_at(b["students"], 0.40),
                    _rate_at(a["students"], 0.40),
                )
            )
        for label, bv, av in rows:
            if bv != bv or av != av:
                continue
            print(f"{label:<28}{bv:>10.4f}{av:>11.4f}{av - bv:>+10.4f}")
        print(
            f"\n  SHIPPED   human mean={statistics_mean(b['human']):.4f} "
            f"ai mean={statistics_mean(b['ai']):.4f}"
        )
        print(
            f"  CANDIDATE human mean={statistics_mean(a['human']):.4f} "
            f"ai mean={statistics_mean(a['ai']):.4f}"
        )
    return 0


def statistics_mean(values: list[float]) -> float:
    """Mean that tolerates an empty list."""
    return sum(values) / len(values) if values else float("nan")


if __name__ == "__main__":
    raise SystemExit(main())
