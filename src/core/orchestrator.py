"""Orchestrator - SINGLE entry point for ALL detection workflows.

USES UNIFIED ENGINES LAYER:
- engines/features/ → feature extraction
- engines/scoring/ → fusion scoring
- core/decision/ → runtime decision

DESIGN RULES:
- NEVER import evaluation/ (offline only)
- NEVER call engines directly, use orchestrator only
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from src.core.models import CodePair

@dataclass
class DetectionResult:
    """Result from orchestrator - decision from SINGLE decision layer."""
    pair_id: str
    score: float
    decision: int
    confidence: float

class Orchestrator:
    """
    SINGLE entry point for all detection workflows.
    flow: input → engines/features → engines/scoring → core/decision → result
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.engines.features.feature_extractor import FeatureExtractor
        from src.engines.scoring.fusion_engine import FusionEngine
        from src.core.decision import DecisionEngine
        self.extractor = FeatureExtractor()
        self.fusion = FusionEngine(weights)
        self.decision = DecisionEngine(threshold)
    
    def run(self, pairs: List[CodePair], code_store: Dict[str, str]) -> List[DetectionResult]:
        """Run detection through orchestrator ONLY."""
        results = []
        for pair in pairs:
            # Extract features
            features = self.extractor.extract(code_store.get(pair.a,""), code_store.get(pair.b,""))
            # Fuse score
            fused = self.fusion.fuse(features)
            # Make decision
            final = self.decision.decide(fused.final_score)
            results.append(DetectionResult(
                pair_id=pair.id,
                score=fused.final_score,
                decision=final.predicted,
                confidence=final.confidence,
            ))
        return results
