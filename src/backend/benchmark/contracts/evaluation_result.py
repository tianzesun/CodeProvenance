"""Canonical evaluation result contract.

This is the INVARIANT: every system MUST output this schema.
Without this, benchmark is scientifically weak.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class EvaluationResult:
    """Canonical evaluation result - every adapter must output this.

    Attributes:
        pair_id: Unique identifier for the code pair.
        score: Similarity score in [0.0, 1.0].
        decision: Binary decision (True=clone, False=non-clone).
        confidence: Confidence in [0.0, 1.0] of the decision.
        engine: Name of the engine that produced this result.
        metadata: Additional metadata (obfuscation level, language, etc.).
    """
    pair_id: str
    score: float
    decision: bool
    confidence: float
    engine: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if not self.pair_id:
            raise ValueError("pair_id must not be empty")
        if not self.engine:
            raise ValueError("engine must not be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pair_id": self.pair_id,
            "score": self.score,
            "decision": self.decision,
            "confidence": self.confidence,
            "engine": self.engine,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvaluationResult:
        """Create from dictionary.

        Args:
            data: Dictionary with required fields.

        Returns:
            EvaluationResult instance.
        """
        return cls(
            pair_id=data["pair_id"],
            score=float(data["score"]),
            decision=bool(data["decision"]),
            confidence=float(data["confidence"]),
            engine=data["engine"],
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class EnrichedPair:
    """Pair-level enriched schema - no hidden metadata.

    Every attribute is explicit per evaluation row.
    This is essential for scientific rigor and stratified analysis.
    """
    pair_id: str
    id_a: str
    id_b: str
    code_a: str
    code_b: str
    label: int  # 1=clone, 0=non-clone
    clone_type: int  # 0=non-clone, 1-4=clone types
    difficulty: str  # EASY, MEDIUM, HARD, EXPERT
    language: str  # python, java, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if self.label not in (0, 1):
            raise ValueError(f"label must be 0 or 1, got {self.label}")
        if self.clone_type not in (0, 1, 2, 3, 4):
            raise ValueError(f"clone_type must be 0-4, got {self.clone_type}")
        if self.difficulty not in ("EASY", "MEDIUM", "HARD", "EXPERT"):
            raise ValueError(f"difficulty must be EASY/MEDIUM/HARD/EXPERT, got {self.difficulty}")
        if not self.pair_id:
            raise ValueError("pair_id must not be empty")
        if not self.language:
            raise ValueError("language must not be empty")

    @property
    def is_clone(self) -> bool:
        """Check if this pair is a clone."""
        return self.label == 1

    @property
    def clone_type_name(self) -> str:
        """Get human-readable clone type name."""
        names = {0: "non-clone", 1: "type-1", 2: "type-2", 3: "type-3", 4: "type-4"}
        return names[self.clone_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pair_id": self.pair_id,
            "id_a": self.id_a,
            "id_b": self.id_b,
            "code_a": self.code_a,
            "code_b": self.code_b,
            "label": self.label,
            "clone_type": self.clone_type,
            "difficulty": self.difficulty,
            "language": self.language,
            "metadata": self.metadata,
        }

    @classmethod
    def from_code_pair(
        cls,
        code_pair: Any,  # CodePair from schema.py
        difficulty: str,
        language: str,
    ) -> EnrichedPair:
        """Create from CodePair with metadata.

        Args:
            code_pair: CodePair instance.
            difficulty: Difficulty level.
            language: Programming language.

        Returns:
            EnrichedPair instance.
        """
        pair_id = f"{code_pair.id_a}__{code_pair.id_b}"
        return cls(
            pair_id=pair_id,
            id_a=code_pair.id_a,
            id_b=code_pair.id_b,
            code_a=code_pair.code_a,
            code_b=code_pair.code_b,
            label=code_pair.label,
            clone_type=code_pair.clone_type,
            difficulty=difficulty,
            language=language,
        )