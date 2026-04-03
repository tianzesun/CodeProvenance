"""Tool adapters for cross-dataset benchmarking.

Wraps existing engines to provide a unified interface where all tools
output a score between 0-1.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import time


class ToolAdapter(ABC):
    """Abstract interface for tool adapters.

    All adapters must:
    - Have a unique name
    - Accept code_a and code_b strings
    - Return a similarity score in [0, 1]
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        pass

    @abstractmethod
    def score(self, code_a: str, code_b: str) -> float:
        """Compute similarity score between two code snippets.

        Args:
            code_a: First code snippet
            code_b: Second code snippet

        Returns:
            Similarity score in [0, 1]
        """
        pass

    def score_batch(
        self,
        pairs: List[tuple],
    ) -> List[float]:
        """Score multiple pairs.

        Args:
            pairs: List of (code_a, code_b) tuples

        Returns:
            List of scores in same order
        """
        return [self.score(a, b) for a, b in pairs]

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about this tool."""
        return {"name": self.name}


class BaseToolAdapter(ToolAdapter):
    """Base class with common functionality."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def get_metadata(self) -> Dict[str, Any]:
        return {"name": self.name}


class EngineAdapter(BaseToolAdapter):
    """Adapt a DetectionEngine to the ToolAdapter interface.

    Wraps engines from benchmark.registry that implement compare(code1, code2) -> float.
    """

    def __init__(self, engine, name: str = ""):
        engine_name = name
        if not engine_name:
            if hasattr(engine, "name"):
                n = engine.name
                engine_name = n() if callable(n) else n
            else:
                engine_name = type(engine).__name__
        super().__init__(name=engine_name)
        self._engine = engine

    def score(self, code_a: str, code_b: str) -> float:
        result = self._engine.compare(code_a, code_b)
        if isinstance(result, float):
            return max(0.0, min(1.0, result))
        if isinstance(result, dict):
            raw = result.get("overall_score", result.get("score", 0.0))
            return max(0.0, min(1.0, float(raw)))
        if hasattr(result, "score"):
            return max(0.0, min(1.0, float(result.score)))
        return max(0.0, min(1.0, float(result)))


class SimilarityAlgorithmAdapter(BaseToolAdapter):
    """Adapt a BaseSimilarityAlgorithm to the ToolAdapter interface.

    Wraps similarity algorithms that implement compare(parsed_a, parsed_b) -> Finding.
    """

    def __init__(self, algorithm, name: str = ""):
        algo_name = name
        if not algo_name:
            if hasattr(algorithm, "get_name"):
                algo_name = algorithm.get_name()
            elif hasattr(algorithm, "name"):
                n = algorithm.name
                algo_name = n() if callable(n) else n
            else:
                algo_name = type(algorithm).__name__
        super().__init__(name=algo_name)
        self._algorithm = algorithm

    def score(self, code_a: str, code_b: str) -> float:
        parsed_a = {"code": code_a, "tokens": code_a.split()}
        parsed_b = {"code": code_b, "tokens": code_b.split()}
        finding = self._algorithm.compare(parsed_a, parsed_b)
        if hasattr(finding, "score"):
            return max(0.0, min(1.0, float(finding.score)))
        if isinstance(finding, dict):
            raw = finding.get("score", finding.get("overall_score", 0.0))
            return max(0.0, min(1.0, float(raw)))
        return max(0.0, min(1.0, float(finding)))


class HybridEngineAdapter(BaseToolAdapter):
    """Adapt the SimilarityEngine (multi-algorithm hybrid) to ToolAdapter."""

    def __init__(self, engine=None, name: str = "hybrid"):
        super().__init__(name=name)
        self._engine = engine
        self._initialized = False

    def _ensure_engine(self):
        if self._engine is not None:
            return
        from src.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
        self._engine = SimilarityEngine()
        register_builtin_algorithms(self._engine)
        self._initialized = True

    def score(self, code_a: str, code_b: str) -> float:
        self._ensure_engine()
        parsed_a = {"code": code_a, "tokens": code_a.split()}
        parsed_b = {"code": code_b, "tokens": code_b.split()}
        result = self._engine.compare(parsed_a, parsed_b)
        raw = result.get("overall_score", 0.0)
        return max(0.0, min(1.0, float(raw)))


class TokenJaccardAdapter(BaseToolAdapter):
    """Simple token-based Jaccard similarity adapter."""

    def __init__(self):
        super().__init__(name="token_jaccard")

    def score(self, code_a: str, code_b: str) -> float:
        tokens_a = set(code_a.split())
        tokens_b = set(code_b.split())
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0


class NgramAdapter(BaseToolAdapter):
    """N-gram overlap similarity adapter."""

    def __init__(self, n: int = 3):
        super().__init__(name=f"ngram_{n}")
        self._n = n

    def _get_ngrams(self, text: str) -> set:
        tokens = text.split()
        if len(tokens) < self._n:
            return {tuple(tokens)}
        return {tuple(tokens[i:i + self._n]) for i in range(len(tokens) - self._n + 1)}

    def score(self, code_a: str, code_b: str) -> float:
        ng_a = self._get_ngrams(code_a)
        ng_b = self._get_ngrams(code_b)
        if not ng_a and not ng_b:
            return 1.0
        if not ng_a or not ng_b:
            return 0.0
        intersection = len(ng_a & ng_b)
        union = len(ng_a | ng_b)
        return intersection / union if union > 0 else 0.0


class CosineTFIDFAdapter(BaseToolAdapter):
    """Cosine similarity on token frequency vectors."""

    def __init__(self):
        super().__init__(name="cosine_tfidf")

    def score(self, code_a: str, code_b: str) -> float:
        from collections import Counter
        import math

        def tf_vector(text):
            tokens = text.split()
            return Counter(tokens)

        def cosine_sim(vec_a, vec_b):
            all_tokens = set(vec_a.keys()) | set(vec_b.keys())
            if not all_tokens:
                return 1.0
            dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in all_tokens)
            mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
            mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)

        vec_a = tf_vector(code_a)
        vec_b = tf_vector(code_b)
        return max(0.0, min(1.0, cosine_sim(vec_a, vec_b)))


def build_default_adapters() -> List[ToolAdapter]:
    """Build a list of default tool adapters.

    Returns:
        List of ToolAdapter instances
    """
    adapters = [
        TokenJaccardAdapter(),
        NgramAdapter(n=3),
        NgramAdapter(n=5),
        CosineTFIDFAdapter(),
    ]

    try:
        hybrid = HybridEngineAdapter()
        adapters.append(hybrid)
    except Exception:
        pass

    try:
        from benchmark.registry import registry
        for eng_name in registry.list_engines():
            try:
                engine = registry.get_instance(eng_name)
                adapters.append(EngineAdapter(engine, name=eng_name))
            except Exception:
                pass
    except ImportError:
        pass

    return adapters
