"""Core Domain Models - system truth layer."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class CodePair:
    id: str
    a: str
    b: str
    label: int = -1

@dataclass
class FeatureVector:
    pair_id: str = ""
    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0

@dataclass
class SimilarityScore:
    pair_id: str = ""
    final_score: float = 0.0
    features: Optional[FeatureVector] = None

@dataclass
class DetectionResult:
    pair_id: str
    score: float
    decision: int
    confidence: float

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
    metrics: Optional[MetricsResult] = None
    predictions: List = field(default_factory=list)
    fp_pairs: List[str] = field(default_factory=list)
    fn_pairs: List[str] = field(default_factory=list)
