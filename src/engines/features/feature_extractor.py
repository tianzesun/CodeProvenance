"""Feature Extractor - unified feature computation."""
from typing import Dict, List, Any, Optional
from src.core.domain import FeatureVector

class FeatureExtractor:
    """Unified feature extractor for code pairs."""
    def extract(self, code_a: str, code_b: str) -> FeatureVector:
        return FeatureVector(
            ast=self._compute_ast(code_a, code_b),
            fingerprint=self._compute_fingerprint(code_a, code_b),
            embedding=self._compute_embedding(code_a, code_b))
    def _compute_ast(self, a, b):
        try:
            from src.engines.similarity.ast_similarity import ASTSimilarity
            return ASTSimilarity().compare({'raw': a}, {'raw': b})
        except: return 0.0
    def _compute_fingerprint(self, a, b):
        try:
            from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
            return EnhancedWinnowingSimilarity().compare({'raw': a}, {'raw': b})
        except: return 0.0
    def _compute_embedding(self, a, b):
        try:
            from src.engines.similarity.embedding_similarity import EmbeddingSimilarity
            return EmbeddingSimilarity().compare({'raw': a}, {'raw': b})
        except: return 0.0
