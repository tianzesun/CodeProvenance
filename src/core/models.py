"""Core Data Models - Phase 1. Strict typed data objects."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass(frozen=True)
class CodePair:
    id: str
    a: str  # file path or content identifier
    b: str  # file path or content identifier
    label: int = -1  # -1=unknown, 0=not clone, 1=clone

@dataclass
class FeatureVector:
    pair_id: str
    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0

@dataclass
class SimilarityScore:
    pair_id: str
    features: FeatureVector
    final_score: float = 0.0

@dataclass
class Prediction:
    pair_id: str
    score: float
    pred: int = 0
    label: int = -1

@dataclass
class MetricsResult:
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

@dataclass
class EvaluationReport:
    metrics: MetricsResult
    predictions: List[Prediction] = field(default_factory=list)
    fp_pairs: List[str] = field(default_factory=list)
    fn_pairs: List[str] = field(default_factory=list)
    optimal_threshold: float = 0.5
