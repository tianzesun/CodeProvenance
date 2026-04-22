"""Plan-aligned fusion weight tuning runner.

This module implements the workflow described in
``IntegrityDesk_WeightTuning_Plan_v2.docx`` for scored pair exports. It expects
each input pair to already contain per-engine scores and a binary label, then
produces the locked split, baseline, solo-engine, search, threshold, and final
evaluation artifacts from the plan.
"""

from __future__ import annotations

import csv
import itertools
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


ENGINE_NAMES: tuple[str, ...] = (
    "ast",
    "fingerprint",
    "embedding",
    "execution",
    "ngram",
)

ENGINE_ALIASES: dict[str, str] = {
    "ast_similarity": "ast",
    "token": "fingerprint",
    "token_similarity": "fingerprint",
    "winnowing": "fingerprint",
    "winnowing_similarity": "fingerprint",
    "semantic": "embedding",
    "unixcoder": "embedding",
    "unixcoder_similarity": "embedding",
    "embedding_similarity": "embedding",
    "execution_cfg": "execution",
    "execution_similarity": "execution",
    "gst": "ngram",
    "ngram_similarity": "ngram",
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "ast": 0.35,
    "fingerprint": 0.30,
    "embedding": 0.20,
    "execution": 0.10,
    "ngram": 0.05,
}


@dataclass(frozen=True)
class ScoredPair:
    """One labeled pair with per-engine scores."""

    pair_id: str
    file_a: str
    file_b: str
    label: int
    scores: dict[str, float]
    category: str = "overall"


@dataclass(frozen=True)
class BinaryMetrics:
    """Binary classification metrics for one threshold."""

    threshold: float
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    false_positive_rate: float


def load_scored_pairs(path: Path) -> list[ScoredPair]:
    """Load scored pairs from JSON or CSV."""
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("pairs", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError(
                "JSON input must be a list or an object with a 'pairs' list"
            )
        return [_coerce_pair(row, index) for index, row in enumerate(rows)]

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [
                _coerce_pair(row, index)
                for index, row in enumerate(csv.DictReader(handle))
            ]

    raise ValueError(f"Unsupported scored pair format: {path.suffix}")


def run_weight_tuning_plan(
    scored_pairs_path: Path,
    output_dir: Path = Path("results/weight_tuning"),
    train_ratio: float = 0.70,
    seed: int = 42,
    threshold: float = 0.50,
    grid_step: float = 0.05,
    fpr_limit: float = 0.03,
    fpr_penalty: float = 10.0,
    max_grid_runs: int | None = None,
) -> dict[str, Any]:
    """Run phases 1-6 of the weight tuning plan on a scored pair export."""
    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs = load_scored_pairs(scored_pairs_path)
    train_pairs, test_pairs = stratified_split(
        pairs, train_ratio=train_ratio, seed=seed
    )

    _write_json(output_dir / "train_pairs.json", [asdict(pair) for pair in train_pairs])
    _write_json(output_dir / "test_pairs.json", [asdict(pair) for pair in test_pairs])
    _write_dataset_stats(
        output_dir / "dataset_stats.txt", pairs, train_pairs, test_pairs, seed
    )

    baseline = evaluate_run(
        "baseline",
        train_pairs,
        DEFAULT_WEIGHTS,
        threshold=threshold,
        dataset="train_pairs.json",
        notes="Default weights baseline - do not delete",
    )
    _write_json(output_dir / "baseline.json", baseline)

    solo_results: dict[str, dict[str, Any]] = {}
    for engine_name in ENGINE_NAMES:
        weights = {name: 1.0 if name == engine_name else 0.0 for name in ENGINE_NAMES}
        result = evaluate_run(
            f"solo_{engine_name}",
            train_pairs,
            weights,
            threshold=threshold,
            dataset="train_pairs.json",
            notes=f"Solo {engine_name} evaluation",
        )
        solo_results[engine_name] = result
        _write_json(output_dir / f"solo_{engine_name}.json", result)
    _write_solo_summary(output_dir / "solo_summary.csv", solo_results)

    best_search = search_weights(
        train_pairs,
        solo_results,
        output_dir / "search_log.csv",
        threshold=threshold,
        grid_step=grid_step,
        fpr_limit=fpr_limit,
        fpr_penalty=fpr_penalty,
        max_grid_runs=max_grid_runs,
    )
    _write_json(output_dir / "best_weights_search.json", best_search)

    threshold_result = sweep_thresholds(
        train_pairs,
        best_search["weights"],
        output_dir / "threshold_sweep.csv",
        fpr_limit=fpr_limit,
    )
    _write_json(output_dir / "best_threshold.json", threshold_result)

    final_evaluation = evaluate_run(
        "final_evaluation",
        test_pairs,
        best_search["weights"],
        threshold=threshold_result["threshold"],
        dataset="test_pairs.json",
        notes="One-shot held-out test-set evaluation",
    )
    final_evaluation["best_weights"] = best_search["weights"]
    final_evaluation["best_threshold"] = threshold_result["threshold"]
    final_evaluation["training_f1"] = best_search["f1"]
    final_evaluation["baseline_f1"] = baseline["f1"]
    final_evaluation["delta_f1"] = round(final_evaluation["f1"] - baseline["f1"], 6)
    final_evaluation["overfit_gap"] = round(
        best_search["f1"] - final_evaluation["f1"], 6
    )
    _write_json(output_dir / "final_evaluation.json", final_evaluation)

    summary = {
        "output_dir": str(output_dir),
        "pair_count": len(pairs),
        "train_pair_count": len(train_pairs),
        "test_pair_count": len(test_pairs),
        "baseline_f1": baseline["f1"],
        "best_training_f1": best_search["f1"],
        "final_test_f1": final_evaluation["f1"],
        "final_precision": final_evaluation["precision"],
        "final_recall": final_evaluation["recall"],
        "final_false_positive_rate": final_evaluation["false_positive_rate"],
        "best_threshold": threshold_result["threshold"],
        "runtime_seconds": round(time.time() - started, 3),
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def stratified_split(
    pairs: Sequence[ScoredPair],
    train_ratio: float,
    seed: int,
) -> tuple[list[ScoredPair], list[ScoredPair]]:
    """Split pairs by label so train/test keep the same class balance."""
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1")

    rng = random.Random(seed)
    by_label: dict[int, list[ScoredPair]] = {0: [], 1: []}
    for pair in pairs:
        by_label.setdefault(pair.label, []).append(pair)

    train_pairs: list[ScoredPair] = []
    test_pairs: list[ScoredPair] = []
    for label_pairs in by_label.values():
        shuffled = list(label_pairs)
        rng.shuffle(shuffled)
        split_index = max(1, min(len(shuffled) - 1, round(len(shuffled) * train_ratio)))
        if len(shuffled) == 1:
            train_pairs.extend(shuffled)
            continue
        train_pairs.extend(shuffled[:split_index])
        test_pairs.extend(shuffled[split_index:])

    rng.shuffle(train_pairs)
    rng.shuffle(test_pairs)
    return train_pairs, test_pairs


def evaluate_run(
    run_id: str,
    pairs: Sequence[ScoredPair],
    weights: dict[str, float],
    threshold: float,
    dataset: str,
    notes: str,
) -> dict[str, Any]:
    """Evaluate one weight vector at one threshold."""
    normalized_weights = normalize_weights(weights)
    scores = [weighted_score(pair, normalized_weights) for pair in pairs]
    metrics = metrics_at_threshold(scores, [pair.label for pair in pairs], threshold)
    payload = {
        "run_id": run_id,
        "weights": normalized_weights,
        "threshold": threshold,
        **asdict(metrics),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "notes": notes,
    }
    return payload


def search_weights(
    pairs: Sequence[ScoredPair],
    solo_results: dict[str, dict[str, Any]],
    log_path: Path,
    threshold: float,
    grid_step: float,
    fpr_limit: float,
    fpr_penalty: float,
    max_grid_runs: int | None,
) -> dict[str, Any]:
    """Run bounded grid search and append every evaluation to CSV immediately."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    bounds = _search_bounds_from_solo_results(solo_results)
    labels = [pair.label for pair in pairs]
    best: dict[str, Any] | None = None

    existing_rows = _count_csv_data_rows(log_path)
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "run_number",
            *ENGINE_NAMES,
            "precision",
            "recall",
            "f1",
            "fpr",
            "objective_score",
            "timestamp",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if existing_rows == 0:
            writer.writeheader()

        for run_number, weights in enumerate(
            generate_grid_weights(grid_step=grid_step, bounds=bounds),
            start=existing_rows + 1,
        ):
            scores = [weighted_score(pair, weights) for pair in pairs]
            metrics = metrics_at_threshold(scores, labels, threshold)
            objective_score = penalized_objective(
                metrics.f1,
                metrics.false_positive_rate,
                fpr_limit=fpr_limit,
                fpr_penalty=fpr_penalty,
            )
            row = {
                "run_number": run_number,
                **weights,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
                "fpr": metrics.false_positive_rate,
                "objective_score": objective_score,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            writer.writerow(row)
            handle.flush()

            if best is None or _is_better_candidate(row, best):
                best = dict(row)

            new_rows = run_number - existing_rows
            if max_grid_runs is not None and new_rows >= max_grid_runs:
                break

    if best is None:
        raise RuntimeError("No valid weight combinations were generated")

    best_weights = {
        engine_name: float(best[engine_name]) for engine_name in ENGINE_NAMES
    }
    return {
        "run_id": "best_weights_search",
        "weights": best_weights,
        "threshold": threshold,
        "precision": float(best["precision"]),
        "recall": float(best["recall"]),
        "f1": float(best["f1"]),
        "false_positive_rate": float(best["fpr"]),
        "objective_score": float(best["objective_score"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "train_pairs.json",
        "notes": "Best weight vector from training-set search",
    }


def generate_grid_weights(
    grid_step: float,
    bounds: dict[str, tuple[float, float]],
) -> Iterable[dict[str, float]]:
    """Yield normalized weight combinations on a bounded simplex grid."""
    if not 0.0 < grid_step <= 1.0:
        raise ValueError("grid_step must be in (0, 1]")

    units = round(1.0 / grid_step)
    for raw_units in itertools.product(range(units + 1), repeat=len(ENGINE_NAMES)):
        if sum(raw_units) != units:
            continue
        weights = {
            engine_name: round(raw_units[index] * grid_step, 10)
            for index, engine_name in enumerate(ENGINE_NAMES)
        }
        if all(
            bounds[engine_name][0] <= weights[engine_name] <= bounds[engine_name][1]
            for engine_name in ENGINE_NAMES
        ):
            yield weights


def sweep_thresholds(
    pairs: Sequence[ScoredPair],
    weights: dict[str, float],
    output_path: Path,
    fpr_limit: float,
) -> dict[str, Any]:
    """Sweep thresholds from 0.30 to 0.90 and pick the best valid threshold."""
    scores = [weighted_score(pair, weights) for pair in pairs]
    labels = [pair.label for pair in pairs]
    candidates: list[dict[str, Any]] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["threshold", "precision", "recall", "f1", "fpr"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(31):
            threshold = round(0.30 + index * 0.02, 2)
            metrics = metrics_at_threshold(scores, labels, threshold)
            row = {
                "threshold": threshold,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
                "fpr": metrics.false_positive_rate,
            }
            writer.writerow(row)
            candidates.append(row)

    valid = [
        candidate for candidate in candidates if float(candidate["fpr"]) <= fpr_limit
    ]
    pool = valid or candidates
    chosen = max(
        pool,
        key=lambda item: (
            float(item["f1"]),
            float(item["precision"]),
            -float(item["threshold"]),
        ),
    )
    return {
        "threshold": float(chosen["threshold"]),
        "precision": float(chosen["precision"]),
        "recall": float(chosen["recall"]),
        "f1": float(chosen["f1"]),
        "false_positive_rate": float(chosen["fpr"]),
        "fpr_limit": fpr_limit,
        "justification": (
            "Highest F1 among thresholds at or below the false-positive-rate limit; "
            "ties prefer higher precision."
            if valid
            else "No threshold met the false-positive-rate limit; selected highest F1 fallback."
        ),
    }


def weighted_score(pair: ScoredPair, weights: dict[str, float]) -> float:
    """Compute normalized weighted score for one pair."""
    normalized_weights = normalize_weights(weights)
    score = sum(
        normalized_weights[engine_name] * pair.scores.get(engine_name, 0.0)
        for engine_name in ENGINE_NAMES
    )
    return max(0.0, min(1.0, score))


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize known engine weights to sum to one."""
    raw = {
        engine_name: max(float(weights.get(engine_name, 0.0)), 0.0)
        for engine_name in ENGINE_NAMES
    }
    total = sum(raw.values())
    if total <= 0.0:
        return dict(DEFAULT_WEIGHTS)
    return {engine_name: raw[engine_name] / total for engine_name in ENGINE_NAMES}


def metrics_at_threshold(
    scores: Sequence[float],
    labels: Sequence[int],
    threshold: float,
) -> BinaryMetrics:
    """Compute binary precision/recall/F1/confusion metrics."""
    tp = fp = tn = fn = 0
    for score, label in zip(scores, labels):
        prediction = 1 if score >= threshold else 0
        if prediction == 1 and label == 1:
            tp += 1
        elif prediction == 1 and label == 0:
            fp += 1
        elif prediction == 0 and label == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    )
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return BinaryMetrics(
        threshold=threshold,
        precision=round(precision, 6),
        recall=round(recall, 6),
        f1=round(f1, 6),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        false_positive_rate=round(fpr, 6),
    )


def penalized_objective(
    f1: float,
    false_positive_rate: float,
    fpr_limit: float,
    fpr_penalty: float,
) -> float:
    """Precision-sensitive objective from the plan."""
    return round(f1 - max(0.0, false_positive_rate - fpr_limit) * fpr_penalty, 6)


def _coerce_pair(row: dict[str, Any], index: int) -> ScoredPair:
    """Normalize a row from CSV or JSON into a scored pair."""
    if not isinstance(row, dict):
        raise ValueError(f"Pair row {index} must be an object")

    raw_scores = row.get("scores") if isinstance(row.get("scores"), dict) else row
    scores = {engine_name: 0.0 for engine_name in ENGINE_NAMES}
    for raw_name, raw_value in raw_scores.items():
        engine_name = ENGINE_ALIASES.get(str(raw_name), str(raw_name))
        if engine_name in scores:
            scores[engine_name] = _coerce_float(raw_value)

    file_a = str(row.get("file_a") or row.get("left") or row.get("path_a") or "")
    file_b = str(row.get("file_b") or row.get("right") or row.get("path_b") or "")
    pair_id = str(row.get("pair_id") or row.get("id") or f"pair_{index}")
    label = int(_coerce_float(row.get("label", row.get("ground_truth", 0))))
    if label not in {0, 1}:
        raise ValueError(f"Pair {pair_id} has non-binary label {label}")

    return ScoredPair(
        pair_id=pair_id,
        file_a=file_a,
        file_b=file_b,
        label=label,
        scores=scores,
        category=str(row.get("category") or "overall"),
    )


def _coerce_float(value: Any) -> float:
    """Convert common scalar values to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _search_bounds_from_solo_results(
    solo_results: dict[str, dict[str, Any]],
) -> dict[str, tuple[float, float]]:
    """Cap weak solo engines according to the plan."""
    bounds: dict[str, tuple[float, float]] = {}
    for engine_name in ENGINE_NAMES:
        solo_f1 = float(solo_results.get(engine_name, {}).get("f1", 0.0))
        upper = 0.15 if solo_f1 < 0.60 else 0.70
        bounds[engine_name] = (0.0, upper)
    return bounds


def _is_better_candidate(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """Compare search rows by objective, F1, then precision."""
    return (
        float(candidate["objective_score"]),
        float(candidate["f1"]),
        float(candidate["precision"]),
    ) > (
        float(current["objective_score"]),
        float(current["f1"]),
        float(current["precision"]),
    )


def _write_json(path: Path, payload: Any) -> None:
    """Write pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_dataset_stats(
    path: Path,
    pairs: Sequence[ScoredPair],
    train_pairs: Sequence[ScoredPair],
    test_pairs: Sequence[ScoredPair],
    seed: int,
) -> None:
    """Write dataset split metadata."""
    positives = sum(pair.label for pair in pairs)
    negatives = len(pairs) - positives
    lines = [
        f"created_at={datetime.now(timezone.utc).isoformat()}",
        f"seed={seed}",
        f"total_pairs={len(pairs)}",
        f"plagiarized_pairs={positives}",
        f"original_pairs={negatives}",
        f"train_pairs={len(train_pairs)}",
        f"test_pairs={len(test_pairs)}",
        f"train_positive_pairs={sum(pair.label for pair in train_pairs)}",
        f"test_positive_pairs={sum(pair.label for pair in test_pairs)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_solo_summary(path: Path, solo_results: dict[str, dict[str, Any]]) -> None:
    """Write one-row-per-engine solo metrics."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["engine", "solo_f1", "solo_precision", "solo_recall"],
        )
        writer.writeheader()
        for engine_name in ENGINE_NAMES:
            result = solo_results[engine_name]
            writer.writerow(
                {
                    "engine": engine_name,
                    "solo_f1": result["f1"],
                    "solo_precision": result["precision"],
                    "solo_recall": result["recall"],
                }
            )


def _count_csv_data_rows(path: Path) -> int:
    """Count data rows in an existing CSV file."""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)
