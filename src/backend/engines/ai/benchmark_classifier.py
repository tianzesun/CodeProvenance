#!/usr/bin/env python
"""Benchmark the AI-code classifier on AIGCodeSet with honest methodology.

Four evaluations are run:

1. **Grouped holdout (no leakage).** Samples are split by ``problem_id`` so the
   same programming problem never appears in both train and test. A random
   sample-level split would let the classifier memorise problem-specific style
   and overstate accuracy; grouping removes that shortcut.

2. **Per-generator sensitivity** on the same leakage-free fold. AIGCodeSet gives
   every problem solutions from three LLMs (GEMINI, LLAMA, CODESTRAL), so a
   "leave one LLM out" split cannot be problem-disjoint without discarding most
   data. Instead we report each generator's recall against the fold's human
   samples, on problems the model never trained on.

3. **Heuristic vs ML.** The same test fold is scored with the heuristic-only
   path (no classifier) and with the trained classifier, so the improvement
   from ML is explicit. "Heuristic only" is the PRODUCTION orchestrator with
   Binoculars and the classifier switched off, i.e. the path that actually ships
   when no model is present (it used to be the ensemble's own heuristic mode,
   which is a different formula and lacked the pattern-library signal).

4. **Safe-blend fusion.** The production orchestrator blend formula
   (:func:`src.backend.engines.ai.orchestrator.blend_ml_heuristic`) is applied
   to the same fold using the holdout-trained classifier probability as the
   ML input and the production heuristic score as the heuristic input, so the
   shipped fusion's accuracy/precision trade-off is measured, not assumed.
   (The live orchestrator feeds the ml-mode ensemble score rather than the
   raw classifier probability into the same formula — a documented
   approximation for this evaluation.)

Metrics: accuracy, precision, recall/TPR, FPR, F1, ROC-AUC and PR-AUC
(AI = positive class), plus the existing server thresholds (medium risk 0.40 /
high risk 0.70). TPR/FPR/AUC/PR-AUC are the §1 fields of
``docs/CODEPROVENANCE_BENCHMARK.md``.

Usage::

    python -m src.backend.engines.ai.benchmark_classifier
    python -m src.backend.engines.ai.benchmark_classifier --limit 600 --out report.code_lm.json

Perplexity features use the SAME configuration as production scoring
(``ai_ensemble_config.yaml``), so the benchmark measures what ships.

Output: ``data/datasets/aigcodeset/benchmark_report.json`` and a printed table.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.backend.engines.ai.classifier import (
    AICodeClassifier,
)
from src.backend.engines.ai.feature_rows import build_feature_rows

logger = logging.getLogger(__name__)

DATASET_DIR = Path(__file__).resolve().parents[4] / "data" / "datasets" / "aigcodeset"
DATA_DIR = DATASET_DIR / "data"
REPORT_PATH = DATASET_DIR / "benchmark_report.json"

MIN_CODE_CHARS = 20


def set_dataset_dir(dataset_dir: Path) -> None:
    """Point the benchmark at a different materialised dataset directory.

    Used to validate the ML classifier on a labelled student-code holdout (see
    ``build_student_dataset.py``) with the same grouped-holdout methodology as
    the AIGCodeSet run.
    """
    global DATA_DIR, REPORT_PATH
    DATA_DIR = dataset_dir / "data"
    REPORT_PATH = dataset_dir / "benchmark_report.json"


@dataclass
class Dataset:
    """A materialised labelled dataset."""

    codes: list[str]
    labels: list[int]
    problems: list[str]
    llms: list[str]
    languages: list[str]

    def __len__(self) -> int:
        return len(self.codes)

    def subset(self, indices: list[int]) -> Dataset:
        return Dataset(
            [self.codes[i] for i in indices],
            [self.labels[i] for i in indices],
            [self.problems[i] for i in indices],
            [self.llms[i] for i in indices],
            [self.languages[i] for i in indices],
        )


def _load_meta() -> list[dict[str, Any]]:
    """Read the per-sample metadata index created by build_aigcodeset."""
    records = []
    index = DATA_DIR / "samples.jsonl"
    if not index.exists():
        raise SystemExit(f"{index} not found - build the dataset first (build_aigcodeset / build_student_dataset)")
    for line in index.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_dataset_full() -> Dataset:
    """Load codes, labels, problem_ids, LLMs and languages from the materialised dataset."""
    data = Dataset([], [], [], [], [])
    for record in _load_meta():
        label_dir = "ai" if record["label"] == 1 else "human"
        code = (DATA_DIR / label_dir / record["file"]).read_text(encoding="utf-8")
        if len(code.strip()) < MIN_CODE_CHARS:
            continue
        data.codes.append(code)
        data.labels.append(int(record["label"]))
        data.problems.append(str(record["problem_id"]))
        data.llms.append(str(record["llm"]))
        data.languages.append(str(record.get("language") or "python"))
    return data


def load_dataset() -> tuple[list[str], list[int], list[str], list[str]]:
    """Load codes, labels, problem_ids and LLMs (kept for backward compatibility)."""
    data = load_dataset_full()
    return data.codes, data.labels, data.problems, data.llms


def build_feature_rows_for(codes: list[str], languages: list[str] | None = None, cache_path: Path | None = None):
    """Classifier features for every sample (see :func:`feature_rows.build_feature_rows`)."""
    return build_feature_rows(codes, languages, cache_path=cache_path)


def stratified_subset(labels: list[int], limit: int, seed: int = 1) -> list[int]:
    """Indices of a class-balanced-in-proportion random subset of size ~``limit``.

    The old loop recounted the class totals and the chosen items for every
    candidate (O(n^2)).
    """
    total_per_class = Counter(labels)
    quota = {c: max(1, int(limit * n / len(labels))) for c, n in total_per_class.items()}
    order = list(range(len(labels)))
    random.Random(seed).shuffle(order)
    taken: list[int] = []
    chosen: Counter = Counter()
    for i in order:
        if len(taken) >= limit:
            break
        if chosen[labels[i]] < quota[labels[i]]:
            taken.append(i)
            chosen[labels[i]] += 1
    return sorted(taken)


def compute_metrics(
    y_true: list[int], y_prob: list[float], threshold: float
) -> dict[str, Any]:
    """Precision/recall/F1/accuracy/FPR/AUC/PR-AUC at a probability threshold.

    Mirrors the benchmark taxonomy (``docs/CODEPROVENANCE_BENCHMARK.md`` §1):
    ``recall`` is the TPR, ``fpr`` is the share of human samples flagged at this
    threshold, and ``pr_auc`` (average precision) is reported alongside ROC-AUC
    because the AI/human split is imbalanced.
    """
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    report = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    report["tpr"] = report["recall"]
    report["fpr"] = round(float(fp / (fp + tn)), 4) if (fp + tn) else 0.0
    report["tp"] = int(tp)
    report["fp"] = int(fp)
    report["tn"] = int(tn)
    report["fn"] = int(fn)
    # AUC is undefined with a single class. Older scikit-learn raised ValueError;
    # current versions only warn and return NaN, which ``json.dumps`` writes as the
    # bare token ``NaN`` (not valid JSON). Both cases now yield None.
    report["auc"] = report["pr_auc"] = None
    if len(set(y_true)) == 2:
        report["auc"] = _finite_or_none(lambda: roc_auc_score(y_true, y_prob))
        report["pr_auc"] = _finite_or_none(lambda: average_precision_score(y_true, y_prob))
    return report


def _finite_or_none(compute) -> float | None:
    """Round a metric to 4 places, or None if it raises or is not a finite number."""
    try:
        value = float(compute())
    except ValueError:
        return None
    return round(value, 4) if value == value and value not in (float("inf"), float("-inf")) else None


_metrics = compute_metrics  # backward-compatible private name


_HEURISTIC_ORCHESTRATOR: Any = None


def _heuristic_orchestrator() -> Any:
    """The production orchestrator with Binoculars and the classifier switched off."""
    global _HEURISTIC_ORCHESTRATOR
    if _HEURISTIC_ORCHESTRATOR is None:
        os.environ["BINOCULARS_ENABLED"] = "0"
        from src.backend.engines.ai.ensemble import AIEnsembleConfig, AIEnsembleScorer
        from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

        orchestrator = AIDetectionOrchestrator()
        config = AIEnsembleConfig.get_instance().with_overrides(
            {"classification": {"enabled": False, "model_dir": None}}
        )
        orchestrator._ensemble = AIEnsembleScorer(config=config)
        orchestrator._ensemble_attempted = True
        _HEURISTIC_ORCHESTRATOR = orchestrator
    return _HEURISTIC_ORCHESTRATOR


def _heuristic_score(code: str, language: str = "python") -> float:
    """Score code with the production heuristic path (no classifier, no Binoculars)."""
    return float(_heuristic_orchestrator().analyze(code, language=language)["ai_probability"])


def _train_grouped(
    rows: list[dict[str, float]],
    labels: list[int],
    problems: list[str],
    test_problems: set,
    metadata: dict[str, Any] | None = None,
) -> tuple[AICodeClassifier, list[float], list[int], list[int]]:
    """Train on non-test problems, evaluate on test problems (no leakage).

    Returns (classifier, test_probabilities, test_labels, test_indices).
    """
    train_idx = [i for i, p in enumerate(problems) if p not in test_problems]
    test_idx = [i for i, p in enumerate(problems) if p in test_problems]

    classifier = AICodeClassifier()
    classifier.train(
        [rows[i] for i in train_idx],
        [labels[i] for i in train_idx],
        feature_names=AICodeClassifier.FEATURE_KEYS,
        metadata=metadata,
    )

    test_probs = [r.ai_probability for r in classifier.predict_many([rows[i] for i in test_idx])]
    test_labels = [labels[i] for i in test_idx]
    return classifier, test_probs, test_labels, test_idx


def _threshold_metrics(
    test_labels: list[int], test_probs: list[float]
) -> dict[str, Any]:
    """Metrics at the canonical 0.5 plus server thresholds 0.40 and 0.70."""
    return {
        "metrics": compute_metrics(test_labels, test_probs, 0.5),
        "metrics_at_040": compute_metrics(test_labels, test_probs, 0.40),
        "metrics_at_070": compute_metrics(test_labels, test_probs, 0.70),
    }


def _fmt(m: dict[str, Any]) -> str:
    def f(value: Any) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    return (
        f"acc={m['accuracy']:.3f} P={m['precision']:.3f} R={m['recall']:.3f} "
        f"F1={m['f1']:.3f} FPR={f(m.get('fpr'))} AUC={f(m.get('auc'))} PR-AUC={f(m.get('pr_auc'))}"
    )


def main() -> None:
    """Run all benchmark evaluations and persist the report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Benchmark the AI-code classifier.")
    parser.add_argument("--limit", type=int, default=0, help="stratified subset size")
    parser.add_argument("--out", type=str, default="", help="report path override")
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default="",
        help="materialised dataset dir (default: AIGCodeSet); must contain data/samples.jsonl",
    )
    parser.add_argument(
        "--feature-cache",
        type=str,
        default="",
        help="JSON file caching computed features (invalidated when extractor code changes)",
    )
    args = parser.parse_args()
    if args.dataset_dir:
        set_dataset_dir(Path(args.dataset_dir))

    data = load_dataset_full()
    n_ai = sum(data.labels)
    logger.info("Loaded %d samples (%d AI, %d human)", len(data), n_ai, len(data) - n_ai)

    if args.limit:
        data = data.subset(stratified_subset(data.labels, args.limit))
        n_ai = sum(data.labels)
        logger.info("Subset: %d samples (%d AI, %d human)", len(data), n_ai, len(data) - n_ai)

    if len(set(data.problems)) < 5:
        raise SystemExit(
            "Fewer than 5 distinct problem_ids: a grouped holdout is not meaningful. "
            "Provide problem ids (see build_student_dataset)."
        )

    cache = Path(args.feature_cache) if args.feature_cache else None
    build = build_feature_rows_for(data.codes, data.languages, cache)
    rows = build.rows
    logger.info("Computed features for %d samples (%d from cache)", len(rows), build.cache_hits)
    metadata = {"perplexity_model": build.perplexity_model}

    from sklearn.model_selection import GroupShuffleSplit

    report: dict[str, Any] = {
        "n_samples": len(data),
        "n_ai": n_ai,
        "n_problems": len(set(data.problems)),
        "perplexity_models": dict(build.perplexity_models),
    }

    # 1. Grouped holdout (leakage-free): 20% of problems held out.
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    _, held_out = next(iter(split.split(rows, data.labels, data.problems)))
    test_problems = {data.problems[i] for i in held_out}
    _classifier, test_probs, test_labels, test_idx = _train_grouped(
        rows, data.labels, data.problems, test_problems, metadata
    )
    report["grouped_holdout"] = {
        "train_size": len(data) - len(test_idx),
        "test_size": len(test_idx),
        **_threshold_metrics(test_labels, test_probs),
    }

    # 2. Per-generator sensitivity on the same unseen fold. The generator list comes
    # from the data (it was hard-coded to three LLM names, so any other dataset
    # reported nothing).
    position = {sample: pos for pos, sample in enumerate(test_idx)}  # was list.index(): O(n^2)
    human_idx = [i for i in test_idx if data.labels[i] == 0]
    per_llm: dict[str, Any] = {}
    for generator in sorted({data.llms[i] for i in test_idx if data.labels[i] == 1}):
        gen_idx = [i for i in test_idx if data.labels[i] == 1 and data.llms[i] == generator]
        eval_idx = gen_idx + human_idx
        per_llm[generator] = {
            "ai_samples": len(gen_idx),
            "metrics": compute_metrics(
                [data.labels[i] for i in eval_idx],
                [test_probs[position[i]] for i in eval_idx],
                0.5,
            ),
        }
    report["cross_llm"] = per_llm

    # 3. Heuristic vs ML on the grouped test fold (production heuristic path).
    heuristic_probs = [_heuristic_score(data.codes[i], data.languages[i]) for i in test_idx]
    report["heuristic_comparison"] = {
        "heuristic_only": compute_metrics(test_labels, heuristic_probs, 0.5),
        "ml_classifier": compute_metrics(test_labels, test_probs, 0.5),
    }

    # 4. Safe-blend fusion (production formula) on the same fold.
    from src.backend.engines.ai.ensemble import AIEnsembleConfig
    from src.backend.engines.ai.orchestrator import blend_ml_heuristic

    blend_config = AIEnsembleConfig.get_instance().orchestrator_config()
    blended_probs: list[float] = []
    capped_count = 0
    for pos, i in enumerate(test_idx):
        blended, capped = blend_ml_heuristic(
            test_probs[pos],
            heuristic_probs[pos],
            len(data.codes[i].splitlines()),
            blend_config,
        )
        blended_probs.append(blended)
        capped_count += 1 if capped else 0
    report["safe_blend_comparison"] = {
        "heuristic_only": compute_metrics(test_labels, heuristic_probs, 0.5),
        "ml_classifier": compute_metrics(test_labels, test_probs, 0.5),
        "safe_blend": compute_metrics(test_labels, blended_probs, 0.5),
        "safe_blend_at_040": compute_metrics(test_labels, blended_probs, 0.40),
        "safe_blend_at_070": compute_metrics(test_labels, blended_probs, 0.70),
        "disagreement_capped_samples": capped_count,
    }

    report_path = Path(args.out) if args.out else REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logger.info("Report written to %s", report_path)

    print("\n=== Grouped holdout (no leakage) ===")
    print(" ", _fmt(report["grouped_holdout"]["metrics"]))
    print("  at 0.40 threshold:", _fmt(report["grouped_holdout"]["metrics_at_040"]))
    print("  at 0.70 threshold:", _fmt(report["grouped_holdout"]["metrics_at_070"]))
    print("\n=== Per-generator sensitivity (unseen problems) ===")
    for generator, r in report["cross_llm"].items():
        print(f"  {generator:9}:", _fmt(r["metrics"]))
    print("\n=== Heuristic vs ML (same test fold) ===")
    print("  heuristic only:", _fmt(report["heuristic_comparison"]["heuristic_only"]))
    print("  ML classifier :", _fmt(report["heuristic_comparison"]["ml_classifier"]))
    print("\n=== Safe-blend fusion (production formula, same fold) ===")
    blend = report["safe_blend_comparison"]
    print("  heuristic only:", _fmt(blend["heuristic_only"]))
    print("  ML classifier :", _fmt(blend["ml_classifier"]))
    print("  safe blend    :", _fmt(blend["safe_blend"]))
    print("  at 0.40       :", _fmt(blend["safe_blend_at_040"]))
    print("  at 0.70       :", _fmt(blend["safe_blend_at_070"]))
    print(f"  disagreement-capped samples: {blend['disagreement_capped_samples']}")


if __name__ == "__main__":
    main()
