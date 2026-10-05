"""
Base similarity algorithm class.

All similarity algorithms should inherit from this base class.
"""

import logging
import math
import threading
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from src.backend.domain.models import Finding

logger = logging.getLogger(__name__)

#: Weight of the deep-analysis score in the final score when ASTs were available.
DEEP_ANALYSIS_WEIGHT = 0.65


class BaseSimilarityAlgorithm(ABC):
    """
    Abstract base class for similarity algorithms.

    Each algorithm should implement the compare method to calculate
    similarity between two parsed code representations and return a Finding.
    """

    def __init__(self, name: str, methodology: str = ""):
        self.name = name
        self.methodology = methodology

    @abstractmethod
    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> Finding:
        """
        Compare two parsed code representations and return a Finding.

        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation

        Returns:
            A Finding object containing scores and evidence
        """

    def get_name(self) -> str:
        """
        Get the name of this algorithm.

        Returns:
            Algorithm name string
        """
        return self.name


def _score_of(result: Any) -> float | None:
    """The numeric score of an algorithm result, or None if it is unusable.

    ``min(1.0, nan)`` is ``1.0``, so a NaN score used to be clamped to a PERFECT
    match. Non-finite and non-numeric results are now treated as a failed algorithm.
    """
    value = result if isinstance(result, (int, float)) else getattr(result, "score", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


class SimilarityEngine:
    """
    Engine that combines multiple similarity algorithms.
    """

    def __init__(self):
        self.algorithms: list[BaseSimilarityAlgorithm] = []
        self.weights: dict[str, float] = {}
        self._deep_analysis_enabled = True
        #: Do not run algorithms whose weight is 0. Off by default because callers
        #: read every algorithm's score from ``individual_scores``; the registered
        #: ``ngram`` and ``embedding`` engines have weight 0 but are still executed
        #: (the embedding one loads a transformer), so turn this on when only the
        #: combined score matters.
        self.skip_zero_weight = False

    def add_algorithm(self, algorithm: BaseSimilarityAlgorithm, weight: float = 1.0):
        """
        Add a similarity algorithm to the engine.

        Args:
            algorithm: Similarity algorithm instance
            weight: Weight for this algorithm in the final score (default 1.0)
        """
        if not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0:
            raise ValueError(f"weight must be a finite non-negative number, got {weight!r}")
        self.algorithms.append(algorithm)
        self.weights[algorithm.get_name()] = float(weight)

    def enable_deep_analysis(self, enabled: bool = True):
        """
        Enable or disable deep analysis features.

        Args:
            enabled: Whether to enable deep analysis
        """
        self._deep_analysis_enabled = enabled

    def compare(
        self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Compare two parsed code representations using all algorithms.

        Algorithms that raise, or return a non-finite score, are LEFT OUT of the
        weighted mean and the confidence interval (they used to be counted as a
        0.0 in the interval) and listed under ``errors``; each failure is logged.
        """
        if not self.algorithms:
            return {
                "overall_score": 0.0,
                "findings": [],
                "individual_scores": {},
                "errors": {},
                "confidence_interval": {"lower": 0.0, "upper": 0.0, "confidence": 0.0},
            }

        findings: list[Finding] = []
        individual_scores: dict[str, float] = {}
        errors: dict[str, str] = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for algorithm in self.algorithms:
            algorithm_name = algorithm.get_name()
            weight = self.weights.get(algorithm_name, 1.0)
            if self.skip_zero_weight and weight == 0:
                continue
            try:
                result = algorithm.compare(parsed_a, parsed_b)
                score = _score_of(result)
                if score is None:
                    raise ValueError(f"returned an unusable score: {result!r}")
                finding = (
                    Finding(engine=algorithm_name, score=score, confidence=1.0)
                    if isinstance(result, (int, float))
                    else result
                )
            except Exception as exc:
                logger.warning("Similarity algorithm %s failed: %s", algorithm_name, exc, exc_info=True)
                errors[algorithm_name] = f"{type(exc).__name__}: {exc}"
                individual_scores[algorithm_name] = 0.0
                continue

            findings.append(finding)
            score = max(0.0, min(1.0, score))
            individual_scores[algorithm_name] = score
            weighted_sum += score * weight
            total_weight += weight

        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        measured = [s for name, s in individual_scores.items() if name not in errors]

        result = {
            "overall_score": overall_score,
            "findings": [f.to_dict() for f in findings],
            "individual_scores": individual_scores,
            "errors": errors,
            "confidence_interval": self._interval(overall_score, measured),
        }

        if self._deep_analysis_enabled:
            self._apply_deep_analysis(result, overall_score, parsed_a, parsed_b, measured)
        return result

    @staticmethod
    def _interval(centre: float, scores: list[float]) -> dict[str, float]:
        """Interval of the mean of the algorithm scores around ``centre``."""
        if len(scores) > 1:
            std_dev = float(np.std(scores))
            margin = 1.96 * std_dev / math.sqrt(len(scores))
        else:
            margin = 0.0
        return {
            "lower": max(0.0, centre - margin),
            "upper": min(1.0, centre + margin),
            "confidence": 0.95,
        }

    def _apply_deep_analysis(
        self,
        result: dict[str, Any],
        overall_score: float,
        parsed_a: dict[str, Any],
        parsed_b: dict[str, Any],
        measured: list[float],
    ) -> None:
        try:
            from .deep_analysis import compare_codes_deep
        except ImportError:
            result["deep_analysis"] = None
            return

        try:
            language = parsed_a.get("language", parsed_b.get("language", "default"))
            deep_result = compare_codes_deep(parsed_a, parsed_b, language)
        except Exception as exc:  # RecursionError on very deep ASTs, malformed AST dicts ...
            # Only ImportError used to be handled, so any other failure here aborted
            # the whole comparison even though every algorithm had succeeded.
            logger.warning("Deep analysis failed: %s", exc, exc_info=True)
            result["deep_analysis"] = None
            return

        result["deep_analysis"] = {
            "tree_edit_distance": deep_result.get("tree_edit_distance", 1.0),
            "tree_kernel_similarity": deep_result.get("tree_kernel_similarity", 0.0),
            "normalized_ast_similarity": deep_result.get("normalized_ast_similarity", 0.0),
            "cfg_similarity": deep_result.get("cfg_similarity", 0.0),
            "clone_score": deep_result.get("clone_detection", {}).get("clone_score", 0.0),
            "is_suspicious": deep_result.get("clone_detection", {}).get("is_suspicious", False),
            "ast_available": bool(deep_result.get("ast_available", True)),
        }
        if not result["deep_analysis"]["ast_available"]:
            # Deep analysis needs parsed ASTs. For raw-source inputs (which is what
            # the feature extractor and visualisation pass) it measured nothing and
            # returned ~0, and blending that in at 65% cut every score to about a
            # third of its value.
            return

        deep_score = deep_result.get("combined_score", 0.0)
        final = overall_score * (1.0 - DEEP_ANALYSIS_WEIGHT) + deep_score * DEEP_ANALYSIS_WEIGHT
        result["overall_score"] = max(0.0, min(1.0, final))
        result["deep_analysis_score"] = deep_score
        # The interval was left around the PRE-blend score, so it could exclude the
        # score actually reported.
        result["confidence_interval"] = self._interval(result["overall_score"], measured)


# Cached singleton for built-in algorithm instances to avoid recreating on every call.
_builtins: dict[str, BaseSimilarityAlgorithm] | None = None
_builtins_lock = threading.Lock()


def _build_embedding_engine() -> BaseSimilarityAlgorithm:
    """UniXcoder (local) if usable, else the OpenAI-compatible embedding engine."""
    try:
        from .unixcoder_similarity import UniXcoderSimilarity

        return UniXcoderSimilarity()
    except Exception:
        from .embedding_similarity import EmbeddingSimilarity

        return EmbeddingSimilarity()


def _get_builtin_algorithms() -> dict[str, BaseSimilarityAlgorithm]:
    """Lazily create and cache all built-in algorithm instances (thread-safe)."""
    global _builtins
    if _builtins is not None:
        return _builtins
    with _builtins_lock:
        if _builtins is not None:
            return _builtins

        from .ast_similarity import ASTSimilarity
        from .execution_similarity import ExecutionSimilarity
        from .ngram_similarity import NgramSimilarity
        from .token_similarity import TokenSimilarity
        from .winnowing_similarity import EnhancedWinnowingSimilarity

        built: dict[str, BaseSimilarityAlgorithm] = {
            "winnowing": EnhancedWinnowingSimilarity(),
            "token": TokenSimilarity(),
            "ngram": NgramSimilarity(),
            "ast": ASTSimilarity(),
            "execution": ExecutionSimilarity(),
            "embedding": _build_embedding_engine(),
        }

        # Graph-based similarity (CFG + DFG structural comparison) — optional
        try:
            from .graph_similarity import GraphSimilarity

            built["graph"] = GraphSimilarity()
        except Exception as exc:
            logger.info("Graph similarity unavailable: %s", exc)

        _builtins = built
        return _builtins


# Register built-in algorithms
def register_builtin_algorithms(engine: SimilarityEngine) -> None:
    """Register all built-in similarity algorithms with the engine.

    Shared algorithm instances are reused across calls via a module-level cache.

    Args:
        engine: SimilarityEngine instance to register algorithms with
    """
    # JPlag-style weighting matching fusion engine formula
    default_weights: dict[str, float] = {
        "ast": 4.0,  # 40%
        "graph": 2.0,  # 20%
        "token": 2.5,  # 25%
        "execution": 1.0,  # 10%
        "winnowing": 0.5,  # 5%
        "ngram": 0.0,  # Disabled - surface-only
        "embedding": 0.0,  # Disabled
    }

    for algo_name, algo in _get_builtin_algorithms().items():
        engine.add_algorithm(algo, weight=default_weights.get(algo_name, 1.0))
