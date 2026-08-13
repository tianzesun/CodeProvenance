#!/usr/bin/env python
"""Benchmark the AI-code classifier on AIGCodeSet with honest methodology.

Three evaluations are run:

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
   from ML is explicit.

Metrics: accuracy, precision, recall, F1, AUC (AI = positive class), plus the
existing server thresholds (medium risk 0.40 / high risk 0.70).

Usage::

    python -m src.backend.engines.ai.benchmark_classifier
    python -m src.backend.engines.ai.benchmark_classifier --limit 600 --out report.code_lm.json

Perplexity comes from :class:`PerplexityScorer`, which uses the statistical
model unless the ``AICODE_TRANSFORMER_MODEL`` env var names a locally cached
causal code LM; set that var to compare code-LM features directly.

Output: ``data/datasets/aigcodeset/benchmark_report.json`` and a printed table.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.backend.engines.ai.ast_features import TreeSitterASTExtractor  # noqa: E402
from src.backend.engines.ai.classifier import (  # noqa: E402
    AICodeClassifier,
    assemble_features,
)
from src.backend.engines.ai.perplexity import PerplexityScorer  # noqa: E402

logger = logging.getLogger(__name__)

DATASET_DIR = Path(__file__).resolve().parents[4] / "data" / "datasets" / "aigcodeset"
DATA_DIR = DATASET_DIR / "data"
REPORT_PATH = DATASET_DIR / "benchmark_report.json"

MIN_CODE_CHARS = 20


def _load_meta() -> List[Dict[str, Any]]:
    """Read the per-sample metadata index created by build_aigcodeset."""
    records = []
    for line in (DATA_DIR / "samples.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_dataset() -> Tuple[List[str], List[int], List[str], List[str]]:
    """Load codes, labels, problem_ids and LLMs from the materialised dataset."""
    codes: List[str] = []
    labels: List[int] = []
    problems: List[str] = []
    llms: List[str] = []
    for record in _load_meta():
        label_dir = "ai" if record["label"] == 1 else "human"
        code = (DATA_DIR / label_dir / record["file"]).read_text(encoding="utf-8")
        if len(code.strip()) < MIN_CODE_CHARS:
            continue
        codes.append(code)
        labels.append(int(record["label"]))
        problems.append(str(record["problem_id"]))
        llms.append(str(record["llm"]))
    return codes, labels, problems, llms


def build_feature_rows(codes: List[str]) -> List[Dict[str, float]]:
    """Compute classifier features for every sample (AST + stylometry + perplexity)."""
    ast_extractor = TreeSitterASTExtractor()
    perplexity = PerplexityScorer()
    from src.backend.engines.features.code_stylometry import StylometryExtractor

    stylometry_extractor = StylometryExtractor()
    rows: List[Dict[str, float]] = []
    for code in codes:
        ast_vector = ast_extractor.extract(code, "python")
        stylometry = stylometry_extractor.extract(code, doc_id="")
        perp = perplexity.score(code)
        rows.append(assemble_features(ast_vector, stylometry, perp))
    return rows


def _metrics(
    y_true: List[int], y_prob: List[float], threshold: float
) -> Dict[str, Any]:
    """Precision/recall/F1/accuracy/AUC at a given probability threshold."""
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    report = {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
    }
    try:
        report["auc"] = round(roc_auc_score(y_true, y_prob), 4)
    except ValueError:
        report["auc"] = None
    return report


def _heuristic_score(code: str) -> float:
    """Score code with the heuristic-only ensemble path (no classifier)."""
    from src.backend.engines.ai.ensemble import AIEnsembleConfig, AIEnsembleScorer

    config = AIEnsembleConfig()
    config._config["classification"] = {"enabled": False, "model_dir": None}
    scorer = AIEnsembleScorer(config=config)
    return float(scorer.score(code, language="python")["ai_probability"])


def _train_grouped(
    rows: List[Dict[str, float]],
    labels: List[int],
    problems: List[str],
    test_problems: set,
) -> Tuple[AICodeClassifier, List[float], List[int], List[int]]:
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
    )

    test_probs = [classifier.predict(rows[i]).ai_probability for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    return classifier, test_probs, test_labels, test_idx


def _threshold_metrics(
    test_labels: List[int], test_probs: List[float]
) -> Dict[str, Any]:
    """Metrics at the canonical 0.5 plus server thresholds 0.40 and 0.70."""
    return {
        "metrics": _metrics(test_labels, test_probs, 0.5),
        "metrics_at_040": _metrics(test_labels, test_probs, 0.40),
        "metrics_at_070": _metrics(test_labels, test_probs, 0.70),
    }


def main() -> None:
    """Run all benchmark evaluations and persist the report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    codes, labels, problems, llms = load_dataset()
    n_ai = sum(labels)
    logger.info(
        "Loaded %d samples (%d AI, %d human)", len(codes), n_ai, len(labels) - n_ai
    )

    # Optional subset for controlled comparisons (e.g. statistical vs code-LM
    # features). Always stratified by label so proportions stay representative.
    parser = argparse.ArgumentParser(description="Benchmark the AI-code classifier.")
    parser.add_argument("--limit", type=int, default=0, help="stratifed subset size")
    parser.add_argument("--out", type=str, default="", help="report path override")
    args = parser.parse_args()
    if args.limit:
        idx = list(range(len(codes)))
        random.Random(1).shuffle(idx)
        taken: List[int] = []
        for i in idx:
            if len(taken) >= args.limit:
                break
            chosen_in_class = sum(1 for j in taken if labels[j] == labels[i])
            total_in_class = sum(1 for label in labels if label == labels[i])
            if chosen_in_class < max(1, int(args.limit * total_in_class / len(codes))):
                taken.append(i)
        codes, labels, problems, llms = (
            [codes[i] for i in taken],
            [labels[i] for i in taken],
            [problems[i] for i in taken],
            [llms[i] for i in taken],
        )
        n_ai = sum(labels)
        logger.info(
            "Subset: %d samples (%d AI, %d human)", len(codes), n_ai, len(labels) - n_ai
        )

    rows = build_feature_rows(codes)
    logger.info("Computed features for %d samples", len(rows))

    from sklearn.model_selection import GroupShuffleSplit

    report: Dict[str, Any] = {"n_samples": len(codes), "n_ai": n_ai}

    # 1. Grouped holdout (leakage-free): 20% of problems held out.
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    _, test_idx = next(iter(split.split(rows, labels, problems)))
    test_problems = {problems[i] for i in test_idx}
    classifier, test_probs, test_labels, test_idx_out = _train_grouped(
        rows, labels, problems, test_problems
    )
    report["grouped_holdout"] = {
        "train_size": len(codes) - len(test_idx_out),
        "test_size": len(test_idx_out),
        **_threshold_metrics(test_labels, test_probs),
    }

    # 2. Per-generator sensitivity on the same unseen fold.
    per_llm: Dict[str, Any] = {}
    for generator in ["GEMINI", "LLAMA", "CODESTRAL"]:
        gen_idx = [i for i in test_idx_out if labels[i] == 1 and llms[i] == generator]
        if not gen_idx:
            continue
        human_idx = [i for i in test_idx_out if labels[i] == 0]
        eval_idx = gen_idx + human_idx
        eval_labels = [labels[i] for i in eval_idx]
        eval_probs = [test_probs[test_idx_out.index(i)] for i in eval_idx]
        per_llm[generator] = {
            "ai_samples": len(gen_idx),
            "metrics": _metrics(eval_labels, eval_probs, 0.5),
        }
    report["cross_llm"] = per_llm

    # 3. Heuristic vs ML on the grouped test fold.
    heuristic_probs = [_heuristic_score(codes[i]) for i in test_idx_out]
    report["heuristic_comparison"] = {
        "heuristic_only": _metrics(test_labels, heuristic_probs, 0.5),
        "ml_classifier": _metrics(test_labels, test_probs, 0.5),
    }

    report_path = Path(args.out) if args.out else REPORT_PATH
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logger.info("Report written to %s", report_path)

    def _fmt(m: Dict[str, Any]) -> str:
        auc = m.get("auc")
        auc_s = "n/a" if auc is None else f"{auc:.3f}"
        return (
            f"acc={m['accuracy']:.3f} P={m['precision']:.3f} R={m['recall']:.3f} "
            f"F1={m['f1']:.3f} AUC={auc_s}"
        )

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


if __name__ == "__main__":
    main()
