"""EvalForge v2 - Production-grade benchmarking framework for plagiarism detection.

Core abstractions for evaluating detectors under controlled conditions.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum


class CloneType(Enum):
    """Canonical clone taxonomy (C0-C4)."""
    UNRELATED = 0          # No shared logic
    LOW_SIMILARITY = 1     # Shared syntax patterns only
    STRUCTURAL_CLONE = 2   # Same control flow, different naming
    SEMANTIC_CLONE = 3     # Same algorithm, different structure
    EXACT_CLONE = 4        # Copy or trivial edits


@dataclass
class DetectionResult:
    """Result of a detector's scoring of a code pair."""
    score: float  # 0.0-1.0 similarity score
    confidence: float  # 0.0-1.0 confidence in prediction
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseDetector(ABC):
    """Base class for all detectors. All tools must implement this interface."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this detector."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass
    
    @abstractmethod
    def score(self, code_a: str, code_b: str) -> DetectionResult:
        """Score similarity between two code snippets.
        
        Args:
            code_a: First code snippet
            code_b: Second code snippet
            
        Returns:
            DetectionResult with score and metadata
        """
        pass
    
    def batch_score(self, pairs: List[Tuple[str, str]]) -> List[DetectionResult]:
        """Batch scoring for efficiency. Override if detector supports batching."""
        return [self.score(a, b) for a, b in pairs]


@dataclass
class CodePair:
    """Labeled code pair with ground truth and transformation history."""
    id: str
    code_a: str
    code_b: str
    label: CloneType  # Ground truth label
    transform_path: List[str] = field(default_factory=list)  # Transformations applied
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_positive(self) -> bool:
        """Binary classification label: clone (>= C2) or not."""
        return self.label.value >= CloneType.STRUCTURAL_CLONE.value


@dataclass
class Transformer(ABC):
    """Semantic-preserving code transformer for robustness testing."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def apply(self, code: str) -> str:
        """Apply transformation to code while preserving semantics."""
        pass


@dataclass
class BenchmarkResult:
    """Result of a single detector on a single code pair."""
    pair_id: str
    detector_name: str
    score: float
    confidence: float
    label: int  # CloneType value
    transform_path: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_positive_label(self) -> bool:
        return self.label >= CloneType.STRUCTURAL_CLONE.value
    
    @property
    def prediction(self, threshold: float = 0.5) -> bool:
        return self.score >= threshold