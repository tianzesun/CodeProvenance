"""Feature Extractor - unified feature computation for all pairs."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class FeatureVector:
    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0

class FeatureExtractor:
    """Unified feature extractor for code pairs."""
    def extract(self, code_a: str, code_b: str) -> FeatureVector:
        """Extract AST, fingerprint, and embedding features."""
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
