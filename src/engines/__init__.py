"""
Engines Layer - Multi-engine similarity detection with fusion.

Provides:
1. Feature extraction from code pairs
2. Multiple similarity engines (AST, Token, N-gram, Embedding, Execution, Winnowing)
3. Fusion scoring combining all engines
4. ML-based weight learning

USAGE:
    from src.engines import MultiEngineSimilarity
    engine = MultiEngineSimilarity()
    result = engine.compare(code_a, code_b)
    # Returns: {score, confidence, features, label}
"""
from src.engines.scoring.fusion_engine import FusedScore
from src.engines.registry import EngineRegistry
from src.engines.base import BaseSimilarityEngine, BaseFeatureExtractor

__all__ = ['MultiEngineSimilarity', 'FusedScore', 'EngineRegistry',
           'BaseSimilarityEngine', 'BaseFeatureExtractor']


class MultiEngineSimilarity:
    """Production multi-engine similarity detection."""
    FEATURE_NAMES = ["ast", "fingerprint", "embedding", "ngram", "winnowing"]
    
    def __init__(self, weights=None, threshold=0.5):
        from src.engines.features.feature_extractor import FeatureExtractor
        from src.engines.scoring.fusion_engine import FusionEngine
        from src.domain.decision import DecisionEngine
        self.extractor = FeatureExtractor()
        self.fusion = FusionEngine(weights)
        self.decision = DecisionEngine(threshold)
    
    def compare(self, code_a, code_b, code_dict=None):
        """Compare two code samples.
        
        Args:
            code_a: First code sample
            code_b: Second code sample
            code_dict: Optional {"A": submission_a_name, "B": submission_b_name}
        """
        features = self.extractor.extract(code_a, code_b)
        fused = self.fusion.fuse(features)
        result = self.decision.decide(fused.final_score)
        feature_dict = {k: v for k, v in zip(self.FEATURE_NAMES,
                        self.extractor.to_features(features))}
        return {
            "score": fused.final_score,
            "confidence": result.confidence,
            "features": feature_dict,
            "label": result.final_verdict,
            "threshold_version": "V1",
        }