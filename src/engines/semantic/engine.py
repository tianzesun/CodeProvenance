"""Semantic Engine - Code meaning similarity detection."""
from typing import Dict, Any
from src.engines.base_engine import BaseEngine, EngineResult


class SemanticEngine(BaseEngine):
    def __init__(self, weight: float = 1.0, model_name: str = 'codebert'):
        super().__init__(name="semantic", weight=weight)
        self.model_name = model_name

    def compare(self, code_a: str, code_b: str, language: str = 'auto', **kwargs) -> EngineResult:
        try:
            from src.core.similarity.embedding_similarity import EmbeddingSimilarity
            score = EmbeddingSimilarity(model_name=self.model_name).compare({'raw': code_a}, {'raw': code_b})
            return EngineResult(score=score, details={'algorithm': 'embedding', 'model': self.model_name}, confidence=0.75)
        except Exception:
            return EngineResult(score=0.5, details={'fallback': True}, confidence=0.0)

    def get_name(self) -> str:
        return "semantic"

    def supports_language(self, language: str) -> bool:
        return language.lower() in {'python', 'java', 'javascript', 'typescript', 'go', 'rust', 'c', 'cpp', 'csharp'}
