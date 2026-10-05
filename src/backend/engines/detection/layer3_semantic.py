"""Layer 3: Semantic Detection - AI-generated code and deep paraphrase detection.

High-recall layer for meaning-level similarity. Deliberately capped; it must NEVER be the sole
evidence for a plagiarism verdict (the decision engines enforce that).

Engines:
  - embedding:       CodeBERT/UniXcoder embedding cosine similarity
  - transformer:     Transformer-based encoder scoring
  - concept_overlap: High-level concept/topic similarity

Changes: an engine that did not report is UNAVAILABLE, not 0.0 (a missing transformer used to
halve ``concept_overlap`` and take 40% off ``semantic_similarity``); the combined scores are
renormalised over the engines that are present; ``max_signal`` / ``mean_signal`` use the corrected
signals (they included the RAW embedding, which sits near 0.70 for any two files); scores are read
defensively (None / NaN); baselines are configurable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ._text import first_score

logger = logging.getLogger(__name__)

#: engine_scores keys that carry corrected (decision-grade) signals
_SIGNAL_KEYS = ("embedding_corrected", "transformer_corrected", "concept_overlap", "semantic_similarity")


@dataclass
class Layer3Result:
    """Structured output from the semantic detection layer."""

    embedding_similarity: float = 0.0
    transformer_score: float = 0.0
    concept_overlap_score: float = 0.0
    semantic_similarity_score: float = 0.0
    engine_scores: dict[str, float] = field(default_factory=dict)

    @property
    def max_signal(self) -> float:
        values = [self.engine_scores[k] for k in _SIGNAL_KEYS if isinstance(self.engine_scores.get(k), (int, float))]
        return max(values) if values else 0.0

    @property
    def mean_signal(self) -> float:
        values = [
            self.engine_scores[k]
            for k in _SIGNAL_KEYS
            if isinstance(self.engine_scores.get(k), (int, float)) and self.engine_scores[k] > 0
        ]
        return sum(values) / len(values) if values else 0.0

    def to_dict(self) -> dict[str, Any]:
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
    """Semantic detection layer - catches meaning-level similarity.

    Embedding similarity is deliberately NOT a standalone signal: it only counts when the policy
    finds structural support.
    """

    # UniXcoder gives ~0.70 cosine similarity for any two Python files.
    EMBEDDING_BASELINE: float = 0.70
    TRANSFORMER_BASELINE: float = 0.65

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._embedding_cap = min(1.0, max(0.0, float(self.config.get("embedding_max_cap", 0.90))))
        self._baseline_correction = bool(self.config.get("embedding_baseline_correction", True))
        self._embedding_baseline = min(0.99, float(self.config.get("embedding_baseline", self.EMBEDDING_BASELINE)))
        self._transformer_baseline = min(0.99, float(self.config.get("transformer_baseline", self.TRANSFORMER_BASELINE)))

    def _correct(self, raw: float, baseline: float) -> float:
        if self._baseline_correction:
            raw = max(0.0, raw - baseline) / max(0.01, 1.0 - baseline)
        return min(raw, self._embedding_cap)

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: dict[str, float] | None = None,
        engine_details: dict[str, Any] | None = None,
    ) -> Layer3Result:
        """Run semantic detection; absent engines are left out of the result."""
        scores = engine_scores or {}
        embedding_raw = first_score(scores, "embedding", "semantic")
        transformer_raw = first_score(scores, "transformer", "codebert", "unixcoder")

        embedding = self._correct(embedding_raw, self._embedding_baseline) if embedding_raw is not None else None
        transformer = self._correct(transformer_raw, self._transformer_baseline) if transformer_raw is not None else None

        present = [v for v in (embedding, transformer) if v is not None]
        concept_overlap = sum(present) / len(present) if present else 0.0
        if embedding is not None and transformer is not None:
            semantic_similarity = embedding * 0.6 + transformer * 0.4
        else:
            semantic_similarity = present[0] if present else 0.0  # the one engine that reported

        out: dict[str, float] = {}
        if embedding is not None:
            out["embedding"] = embedding_raw  # RAW: the decision engines apply their own baseline
            out["embedding_corrected"] = embedding
        if transformer is not None:
            out["transformer"] = transformer_raw
            out["transformer_corrected"] = transformer
        if present:
            out["concept_overlap"] = concept_overlap
            out["semantic_similarity"] = semantic_similarity

        return Layer3Result(
            embedding_similarity=round(embedding or 0.0, 4),
            transformer_score=round(transformer or 0.0, 4),
            concept_overlap_score=round(concept_overlap, 4),
            semantic_similarity_score=round(semantic_similarity, 4),
            engine_scores=out,
        )
