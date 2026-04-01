"""Feature Layer - Phase 2. Extract similarity features from code pairs."""
from typing import Any, Dict
from src.core.models import CodePair, FeatureVector

class FeatureExtractor:
    """Extract similarity features from code pairs."""
    
    def extract(self, pair: CodePair, code_a: str = "", code_b: str = "") -> FeatureVector:
        """Extract all similarity features for a code pair."""
        ast_sim = self._compute_ast_similarity(code_a, code_b)
        fp_sim = self._compute_fingerprint_similarity(code_a, code_b)
        emb_sim = self._compute_embedding_similarity(code_a, code_b)
        
        return FeatureVector(
            pair_id=pair.id,
            ast=ast_sim,
            fingerprint=fp_sim,
            embedding=emb_sim,
        )
    
    def _compute_ast_similarity(self, a: str, b: str) -> float:
        """Compute AST structural similarity."""
        try:
            from src.core.similarity.ast_similarity import ASTSimilarity
            return ASTSimilarity().compare({'raw': a, 'tokens': self._tokenize(a)}, {'raw': b, 'tokens': self._tokenize(b)})
        except:
            return 0.0
    
    def _compute_fingerprint_similarity(self, a: str, b: str) -> float:
        """Compute token/fingerprint similarity."""
        try:
            from src.core.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
            engine = EnhancedWinnowingSimilarity()
            return engine.compare({'raw': a, 'tokens': self._tokenize(a)}, {'raw': b, 'tokens': self._tokenize(b)})
        except:
            return 0.0
    
    def _compute_embedding_similarity(self, a: str, b: str) -> float:
        """Compute AI embedding similarity."""
        try:
            from src.core.similarity.embedding_similarity import EmbeddingSimilarity
            return EmbeddingSimilarity().compare({'raw': a}, {'raw': b})
        except:
            return 0.0
    
    def _tokenize(self, code: str) -> list:
        """Basic tokenization fallback."""
        import re
        return [{'type': 'WORD', 'value': t.lower()} for t in re.findall(r'\b\w+\b', code)]
