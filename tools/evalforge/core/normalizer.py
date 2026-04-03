"""Score normalization."""
from __future__ import annotations
from typing import Callable, Dict, List, Optional


def normalize_percentile(scores, reference_scores=None):
    if not scores: return []
    ref = reference_scores or scores
    sorted_ref = sorted(ref)
    n = len(sorted_ref)
    result = []
    for s in scores:
        count_below = sum(1 for r in sorted_ref if r < s)
        result.append(count_below / max(n - 1, 1))
    return result


def normalize_minmax(scores):
    if not scores: return []
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s: return [0.5] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


def get_normalizer(method="percentile"):
    normalizers = {
        "percentile": normalize_percentile,
        "minmax": normalize_minmax,
        "identity": lambda scores, ref=None: scores,
    }
    return normalizers.get(method, normalize_percentile)
