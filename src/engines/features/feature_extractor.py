"""Feature Extractor - Extracts features from code pairs for similarity engines."""
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class FeatureVector:
    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0
    ngram: float = 0.0
    winnowing: float = 0.0

class FeatureExtractor:
    FEATURE_ORDER = ["ast", "fingerprint", "embedding", "ngram", "winnowing"]
    
    def extract(self, code_a: str, code_b: str) -> FeatureVector:
        return FeatureVector(
            ast=self._ast_similarity(code_a, code_b),
            fingerprint=self._fingerprint_similarity(code_a, code_b),
            embedding=self._embedding_similarity(code_a, code_b),
            ngram=self._ngram_similarity(code_a, code_b),
            winnowing=self._winnowing_similarity(code_a, code_b))
    
    def to_features(self, fv: FeatureVector) -> List[float]:
        return [fv.ast, fv.fingerprint, fv.embedding, fv.ngram, fv.winnowing]
    
    @staticmethod
    def _ast_similarity(a, b):
        try:
            from src.engines.similarity.ast_similarity import ASTSimilarity
            return ASTSimilarity().compare(
                {'raw': a, 'tokens': []}, 
                {'raw': b, 'tokens': []})
        except: return 0.0
    
    @staticmethod
    def _fingerprint_similarity(a, b):
        try:
            from src.engines.similarity.token_similarity import TokenSimilarity
            return TokenSimilarity().compare(
                {'raw': a, 'tokens': []}, 
                {'raw': b, 'tokens': []})
        except: return 0.0
    
    @staticmethod
    def _embedding_similarity(a, b):
        try:
            from src.engines.similarity.embedding_similarity import EmbeddingSimilarity
            return EmbeddingSimilarity().compare({'raw': a}, {'raw': b})
        except: return 0.0
    
    @staticmethod
    def _ngram_similarity(a, b):
        try:
            from src.engines.similarity.ngram_similarity import NgramSimilarity
            return NgramSimilarity().compare(
                {'raw': a, 'tokens': []}, 
                {'raw': b, 'tokens': []})
        except: return 0.0
    
    @staticmethod
    def _winnowing_similarity(a, b):
        try:
            from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
            return EnhancedWinnowingSimilarity().compare(
                {'raw': a, 'tokens': []}, 
                {'raw': b, 'tokens': []})
        except: return 0.0
