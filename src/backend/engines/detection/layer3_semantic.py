"""Layer 3: Semantic Detection — AI-generated code and deep paraphrase detection.

High-recall layer for catching meaning-level similarity. Deliberately capped
to prevent false-positive dominance. Must NEVER be the sole evidence for a
plagiarism verdict.

Engines:
  - embedding:      CodeBERT/UniXcoder embedding cosine similarity
  - transformer:    Transformer-based encoder scoring
  - concept_overlap: High-level concept/topic similarity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Layer3Result:
    """Structured output from the semantic detection layer."""

    embedding_similarity: float = 0.0
    transformer_score: float = 0.0
    concept_overlap_score: float = 0.0
    semantic_similarity_score: float = 0.0
    engine_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def max_signal(self) -> float:
        values = [v for v in self.engine_scores.values() if isinstance(v, (int, float))]
        return max(values) if values else 0.0

    @property
    def mean_signal(self) -> float:
        values = [
            v
            for v in self.engine_scores.values()
            if isinstance(v, (int, float)) and v > 0
        ]
        return sum(values) / len(values) if values else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "embedding_similarity": round(self.embedding_similarity, 4),
            "transformer_score": round(self.transformer_score, 4),
            "concept_overlap_score": round(self.concept_overlap_score, 4),
            "semantic_similarity_score": round(self.semantic_similarity_score, 4),
            "max_signal": round(self.max_signal, 4),
            "mean_signal": round(self.mean_signal, 4),
            "engine_scores": {k: round(v, 4) for k, v in self.engine_scores.items()},
        }


class Layer3Semantic:
    """Semantic detection layer — catches meaning-level similarity.

    Embedding similarity is deliberately NOT used as a standalone signal.
    It only contributes when corroborated by Layers 1 and 2.
    """

    # High baseline for embedding: UniXcoder sees "this is Python code"
    # for any two Python files at ~0.70 cosine similarity.
    EMBEDDING_BASELINE: float = 0.70
    TRANSFORMER_BASELINE: float = 0.65

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._embedding_cap = float(self.config.get("embedding_max_cap", 0.90))
        self._baseline_correction = bool(
            self.config.get("embedding_baseline_correction", True)
        )

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: Optional[Dict[str, float]] = None,
        engine_details: Optional[Dict[str, Any]] = None,
    ) -> Layer3Result:
        """Run semantic detection on a pair of code files.

        Args:
            code_a: Source code of first file.
            code_b: Source code of second file.
            engine_scores: Pre-computed engine scores (keys: embedding, etc.)
            engine_details: Optional full engine output for rich evidence.

        Returns:
            Layer3Result with semantic signals.
        """
        scores = engine_scores or {}
        details = engine_details or {}

        # --- Embedding similarity ---
        embedding_raw = float(scores.get("embedding", scores.get("semantic", 0.0)))

        # Apply baseline correction: subtract the "same language" noise floor
        if self._baseline_correction:
            embedding_corrected = max(0.0, embedding_raw - self.EMBEDDING_BASELINE)
            embedding_corrected /= max(0.01, 1.0 - self.EMBEDDING_BASELINE)
        else:
            embedding_corrected = embedding_raw

        # Apply hard cap — embedding alone can never exceed this threshold
        # This prevents semantic scores from single-handedly causing false positives
        embedding_score = min(embedding_corrected, self._embedding_cap)

        # --- Transformer score (if available) ---
        transformer_raw = float(
            scores.get(
                "transformer", scores.get("codebert", scores.get("unixcoder", 0.0))
            )
        )
        if self._baseline_correction:
            transformer_corrected = max(
                0.0, transformer_raw - self.TRANSFORMER_BASELINE
            )
            transformer_corrected /= max(0.01, 1.0 - self.TRANSFORMER_BASELINE)
        else:
            transformer_corrected = transformer_raw
        transformer_score = min(transformer_corrected, self._embedding_cap)

        # --- Concept overlap (from embedding + transformer) ---
        # High-level topic similarity: if both embedding and transformer
        # agree on semantic similarity, it's a stronger signal
        concept_overlap = (embedding_score + transformer_score) / 2.0

        # --- Combined semantic similarity ---
        # Weighted: embedding is primary, transformer supports
        semantic_similarity = embedding_score * 0.6 + transformer_score * 0.4

        engine_scores_out = {
            "embedding": embedding_raw,
            "embedding_corrected": embedding_score,
            "transformer": transformer_raw,
            "transformer_corrected": transformer_score,
            "concept_overlap": concept_overlap,
            "semantic_similarity": semantic_similarity,
        }

        return Layer3Result(
            embedding_similarity=round(embedding_score, 4),
            transformer_score=round(transformer_score, 4),
            concept_overlap_score=round(concept_overlap, 4),
            semantic_similarity_score=round(semantic_similarity, 4),
            engine_scores=engine_scores_out,
        )
