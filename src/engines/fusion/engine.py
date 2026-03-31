"""Fusion Engine - Ensemble of multiple similarity engines."""
from typing import Dict, List, Any, Optional
from src.engines.base_engine import BaseEngine, EngineResult


class FusionEngine(BaseEngine):
    def __init__(self, weight: float = 1.0, strategy: str = 'weighted_average',
                 fingerprint_weight: float = 1.5, ast_weight: float = 2.0, semantic_weight: float = 1.0):
        super().__init__(name="fusion", weight=weight)
        self.strategy = strategy
        self.engines = [
            FingerprintEngine(weight=fingerprint_weight),
            ASTEngine(weight=ast_weight),
            SemanticEngine(weight=semantic_weight),
        ]
    def compare(self, code_a: str, code_b: str, language: str = 'auto', **kwargs) -> EngineResult:
        results = []
        individual_scores = {}
        for engine in self.engines:
            if engine.supports_language(language):
                try:
                    r = engine.compare(code_a, code_b, language, **kwargs)
                    results.append(r)
                    individual_scores[engine.get_name()] = r.score
                except Exception:
                    individual_scores[engine.get_name()] = 0.0
        if not results:
            return EngineResult(score=0.0, details={'error': 'All engines failed'}, confidence=0.0)
        # Fuse
        if self.strategy == 'max':
            score = max(r.score for r in results)
        elif self.strategy == 'min':
            score = min(r.score for r in results)
        else:
            ws = sum(r.score * r.confidence for r in results)
            tw = sum(r.confidence for r in results)
            score = ws / tw if tw else 0.0
        conf = 1.0
        if results:
            import math
            conf = math.prod(r.confidence for r in results) ** (1 / len(results))
        return EngineResult(score=score, details={'strategy': self.strategy,
                            'individual_scores': individual_scores}, confidence=conf)
    def get_name(self) -> str:
        return "fusion"
