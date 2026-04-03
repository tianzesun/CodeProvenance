"""Evaluation engine — converts raw scores to metrics."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from benchmark.metrics import compute_classification_metrics


def optimize_threshold(
    scores: List[float],
    labels: List[int],
    strategy: str = "f1_max",
) -> Tuple[float, Dict[str, float]]:
    best_threshold, best_score = 0.5, 0.0
    best_metrics = {}
    for t_int in range(0, 101):
        t = t_int / 100.0
        tp = fp = tn = fn = 0
        for score, label in zip(scores, labels):
            pred = 1 if score >= t else 0
            if pred == 1 and label == 1: tp += 1
            elif pred == 1 and label == 0: fp += 1
            elif pred == 0 and label == 0: tn += 1
            else: fn += 1
        m = compute_classification_metrics(tp, fp, tn, fn)
        score = m["f1"] if strategy == "f1_max" else m["precision"]
        if score > best_score:
            best_score = score
            best_threshold = t
            best_metrics = m
    return best_threshold, best_metrics


def evaluate(scores: List[float], labels: List[int], threshold: float = 0.5) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    for score, label in zip(scores, labels):
        pred = 1 if score >= threshold else 0
        if pred == 1 and label == 1: tp += 1
        elif pred == 1 and label == 0: fp += 1
        elif pred == 0 and label == 0: tn += 1
        else: fn += 1
    m = compute_classification_metrics(tp, fp, tn, fn)
    m["threshold"] = threshold
    m["tp"], m["fp"], m["tn"], m["fn"] = tp, fp, tn, fn
    return m


def evaluate_by_clone_type(scores, labels, clone_types, threshold=0.5):
    type_names = {0: "non_clone", 1: "T1", 2: "T2", 3: "T3", 4: "T4"}
    results = {}
    for ctype, name in type_names.items():
        type_scores = [s for s, t in zip(scores, clone_types) if t == ctype]
        type_labels = [l for l, t in zip(labels, clone_types) if t == ctype]
        if type_scores:
            results[name] = evaluate(type_scores, type_labels, threshold)
    return results
