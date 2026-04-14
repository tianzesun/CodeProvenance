"""Detection Pipeline - Unified execution flow.

Stages:
1. Preprocess → 2. Feature extraction → 3. Similarity engines → 4. Fusion → 5. Decision → 6. Persist
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class PipelineResult:
    stage_results: Dict[str, float] = field(default_factory=dict)
    final_scores: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class DetectionPipeline:
    """Production execution backbone."""
    def __init__(self, weights=None, threshold=0.5):
        from src.backend.engines.features import FeatureExtractor
        from src.backend.engines.scoring import FusionEngine
        from src.backend.domain.decision import DecisionEngine
        self.preprocessor = lambda a,b: (a, b)  # Identity for now
        self.feature_extractor = FeatureExtractor()
        self.fusion_engine = FusionEngine(weights)
        self.decision_engine = DecisionEngine(threshold)
        self.persist = lambda x: x  # Identity for now
    
    def execute(self, submissions: Dict[str, Dict[str, str]]) -> PipelineResult:
        result = PipelineResult()
        for sub_id, sub in submissions.items():
            # Stage 1-2: Preprocess + Feature extraction
            ca, cb = self.preprocessor(sub.get("code_a",""), sub.get("code_b",""))
            features = self.feature_extractor.extract(ca, cb)
            # Stage 3-4: Similarity engines + Fusion
            fused = self.fusion_engine.fuse(features)
            # Stage 5: Decision
            decision = self.decision_engine.decide(fused.final_score)
            # Stage 6: Persist
            output = {"submission_id": sub_id, "score": fused.final_score,
                      "decision": decision.final_verdict, "confidence": decision.confidence}
            result.final_scores.append(self.persist(output))
        return result
