"""Scoring Pipeline - Execution orchestration only, delegates scoring to fusion engine.

This pipeline orchestrates the execution flow but does NOT compute similarity scores.
All scoring logic is delegated to the fusion engine (single source of truth).

Execution flow:
Submission -> Feature Extraction -> Fusion Engine -> Threshold Decision -> Result
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PipelineResult:
    """Result from scoring pipeline execution."""
    submission_id: str
    features: Dict[str, float]
    fused_score: float
    confidence: float
    decision: int
    metadata: Dict[str, Any]


class ScoringPipeline:
    """
    Formal execution graph - orchestration only.
    
    This is NOT business logic - it's the execution path definition.
    All scoring logic is delegated to the fusion engine.
    """
    
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        """Initialize pipeline with configuration.
        
        Args:
            weights: Optional weights for fusion engine
            threshold: Threshold for binary decision
        """
        # Import here to avoid circular dependencies
        from src.backend.engines.features import FeatureExtractor
        from src.backend.engines.scoring import get_scoring_engine
        from src.backend.core.decision import DecisionEngine
        
        self.feature_extractor = FeatureExtractor()
        self.scoring_engine = get_scoring_engine()  # Single source of truth
        self.threshold_engine = DecisionEngine(threshold)
    
    def execute(self, code_a: str, code_b: str, submission_id: str = "") -> PipelineResult:
        """Execute scoring pipeline with full traceability.
        
        Args:
            code_a: First code snippet
            code_b: Second code snippet
            submission_id: Optional submission identifier
            
        Returns:
            PipelineResult with scores and decision
        """
        # Step 1: Feature Extraction (provides inputs to scoring engine)
        features = self.feature_extractor.extract(code_a, code_b)
        
        # Step 2: Compute similarity scores using single source of truth
        # The fusion engine is the ONLY place that computes final scores
        fused_result = self.scoring_engine.compute_similarity(
            token_score=features.fingerprint,
            ast_score=features.ast,
            graph_score=getattr(features, 'graph', None),
            embedding_score=features.embedding,
            execution_score=getattr(features, 'execution', None),
            metadata={"submission_id": submission_id}
        )
        
        # Step 3: Threshold Decision (uses score from fusion engine)
        decision = self.threshold_engine.decide(fused_result.final_score)
        
        return PipelineResult(
            submission_id=submission_id,
            features={
                "ast": features.ast,
                "fingerprint": features.fingerprint,
                "embedding": features.embedding,
            },
            fused_score=fused_result.final_score,
            confidence=fused_result.confidence,
            decision=decision.predicted,
            metadata={
                "fusion_method": fused_result.fusion_method,
                "component_scores": fused_result.component_scores,
                "threshold": self.threshold_engine.threshold,
            }
        )
    
    def execute_batch(
        self,
        code_pairs: List[tuple],
        submission_ids: Optional[List[str]] = None
    ) -> List[PipelineResult]:
        """Execute pipeline on batch of code pairs.
        
        Args:
            code_pairs: List of (code_a, code_b) tuples
            submission_ids: Optional list of submission identifiers
            
        Returns:
            List of PipelineResult objects
        """
        if submission_ids is None:
            submission_ids = [f"batch_{i}" for i in range(len(code_pairs))]
        
        results = []
        for (code_a, code_b), sub_id in zip(code_pairs, submission_ids):
            result = self.execute(code_a, code_b, sub_id)
            results.append(result)
        
        return results