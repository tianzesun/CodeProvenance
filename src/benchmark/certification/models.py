"""Core data models for certification reporting.

Defines the canonical data structures used throughout the certification system.
All evaluation results are flattened into BenchmarkRecord for single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any, Dict, List, Optional


class CloneType(IntEnum):
    """Clone type classification (Type I-IV)."""
    TYPE_1 = 1  # Exact clones (textual copies)
    TYPE_2 = 2  # Renamed clones (variable/function names changed)
    TYPE_3 = 3  # Near-miss clones (statements added/removed/modified)
    TYPE_4 = 4  # Semantic clones (different implementation, same behavior)


class Difficulty(IntEnum):
    """Detection difficulty levels."""
    EASY = 1      # Simple, obvious clones
    HARD = 2      # Moderately obfuscated
    EXPERT = 3    # Heavily obfuscated, semantic changes


@dataclass(frozen=True)
class BenchmarkRecord:
    """Single benchmark evaluation record.

    This is the fundamental unit of evaluation data. All results are flattened
    into this structure for consistent analysis across engines and conditions.

    Attributes:
        pair_id: Unique identifier for the code pair.
        label: Ground truth label (1=clone, 0=not clone).
        engine: Name of the detection engine.
        score: Similarity score from engine (0.0 to 1.0).
        decision: Binary classification decision (threshold applied).
        clone_type: Type of clone (1-4) or 0 for non-clones.
        difficulty: Detection difficulty level.
        language: Programming language of the code pair.
        metadata: Additional metadata (file paths, timestamps, etc.).
    """
    pair_id: str
    label: int
    engine: str
    score: float
    decision: bool
    clone_type: int = 0
    difficulty: str = "EASY"
    language: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate record after initialization."""
        if self.label not in (0, 1):
            raise ValueError(f"Label must be 0 or 1, got {self.label}")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be in [0, 1], got {self.score}")
        if self.clone_type < 0 or self.clone_type > 4:
            raise ValueError(f"Clone type must be 0-4, got {self.clone_type}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkRecord:
        """Create from dictionary."""
        return cls(**data)

    @property
    def is_clone(self) -> bool:
        """Check if this is a clone pair."""
        return self.label == 1

    @property
    def is_correct(self) -> bool:
        """Check if decision matches label."""
        return self.decision == bool(self.label)


@dataclass(frozen=True)
class EngineMetrics:
    """Aggregated metrics for a single engine.

    Attributes:
        engine_name: Name of the engine.
        precision: Precision score.
        recall: Recall score.
        f1: F1 score.
        accuracy: Accuracy score.
        roc_auc: ROC-AUC score (if probabilities available).
        average_precision: Average precision score.
        n_samples: Number of evaluation samples.
        n_positive: Number of positive (clone) samples.
        n_negative: Number of negative (non-clone) samples.
        threshold: Decision threshold used.
        ci_precision: Confidence interval for precision (lower, upper).
        ci_recall: Confidence interval for recall (lower, upper).
        ci_f1: Confidence interval for F1 (lower, upper).
    """
    engine_name: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float = 0.0
    average_precision: float = 0.0
    n_samples: int = 0
    n_positive: int = 0
    n_negative: int = 0
    threshold: float = 0.5
    ci_precision: tuple[float, float] = (0.0, 0.0)
    ci_recall: tuple[float, float] = (0.0, 0.0)
    ci_f1: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_name": self.engine_name,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "roc_auc": self.roc_auc,
            "average_precision": self.average_precision,
            "n_samples": self.n_samples,
            "n_positive": self.n_positive,
            "n_negative": self.n_negative,
            "threshold": self.threshold,
            "ci_precision": list(self.ci_precision),
            "ci_recall": list(self.ci_recall),
            "ci_f1": list(self.ci_f1),
        }


@dataclass(frozen=True)
class ComparisonResult:
    """Result of comparing two engines.

    Attributes:
        engine_a: Name of first engine.
        engine_b: Name of second engine.
        mcnemar_pvalue: P-value from McNemar's test.
        mcnemar_significant: Whether McNemar test is significant.
        wilcoxon_pvalue: P-value from Wilcoxon signed-rank test.
        wilcoxon_significant: Whether Wilcoxon test is significant.
        cohens_d: Cohen's d effect size.
        cliffs_delta: Cliff's delta effect size.
        effect_size_interpretation: Human-readable effect size interpretation.
        f1_diff: Difference in F1 scores (A - B).
        precision_diff: Difference in precision (A - B).
        recall_diff: Difference in recall (A - B).
        ci_f1_diff: Confidence interval for F1 difference.
    """
    engine_a: str
    engine_b: str
    mcnemar_pvalue: float
    mcnemar_significant: bool
    wilcoxon_pvalue: float
    wilcoxon_significant: bool
    cohens_d: float
    cliffs_delta: float
    effect_size_interpretation: str
    f1_diff: float
    precision_diff: float
    recall_diff: float
    ci_f1_diff: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_a": self.engine_a,
            "engine_b": self.engine_b,
            "mcnemar_pvalue": self.mcnemar_pvalue,
            "mcnemar_significant": self.mcnemar_significant,
            "wilcoxon_pvalue": self.wilcoxon_pvalue,
            "wilcoxon_significant": self.wilcoxon_significant,
            "cohens_d": self.cohens_d,
            "cliffs_delta": self.cliffs_delta,
            "effect_size_interpretation": self.effect_size_interpretation,
            "f1_diff": self.f1_diff,
            "precision_diff": self.precision_diff,
            "recall_diff": self.recall_diff,
            "ci_f1_diff": list(self.ci_f1_diff),
        }


def extract_labels_and_scores(
    records: List[BenchmarkRecord],
) -> tuple[List[int], List[float], List[bool]]:
    """Extract labels, scores, and decisions from records.

    Args:
        records: List of benchmark records.

    Returns:
        Tuple of (labels, scores, decisions) as lists.
    """
    labels = [r.label for r in records]
    scores = [r.score for r in records]
    decisions = [r.decision for r in records]
    return labels, scores, decisions


def records_to_arrays(
    records: List[BenchmarkRecord],
) -> tuple:
    """Convert records to numpy arrays for analysis.

    Args:
        records: List of benchmark records.

    Returns:
        Tuple of (labels, scores, decisions) as numpy arrays.
    """
    import numpy as np
    labels, scores, decisions = extract_labels_and_scores(records)
    return np.array(labels), np.array(scores), np.array(decisions)


def filter_records(
    records: List[BenchmarkRecord],
    engine: Optional[str] = None,
    clone_type: Optional[int] = None,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
) -> List[BenchmarkRecord]:
    """Filter records by specified criteria.

    Args:
        records: List of benchmark records.
        engine: Filter by engine name.
        clone_type: Filter by clone type (0-4).
        difficulty: Filter by difficulty level.
        language: Filter by programming language.

    Returns:
        Filtered list of records.
    """
    filtered = records

    if engine is not None:
        filtered = [r for r in filtered if r.engine == engine]

    if clone_type is not None:
        filtered = [r for r in filtered if r.clone_type == clone_type]

    if difficulty is not None:
        filtered = [r for r in filtered if r.difficulty == difficulty.upper()]

    if language is not None:
        filtered = [r for r in filtered if r.language.lower() == language.lower()]

    return filtered


def group_records_by_engine(
    records: List[BenchmarkRecord],
) -> Dict[str, List[BenchmarkRecord]]:
    """Group records by engine name.

    Args:
        records: List of benchmark records.

    Returns:
        Dictionary mapping engine names to their records.
    """
    groups: Dict[str, List[BenchmarkRecord]] = {}
    for record in records:
        if record.engine not in groups:
            groups[record.engine] = []
        groups[record.engine].append(record)
    return groups