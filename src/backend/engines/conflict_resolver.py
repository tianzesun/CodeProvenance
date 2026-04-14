"""
Conflict Resolution Layer - handles engine disagreement.

Detects and resolves conflicts between different similarity engines
to reduce false positives and negatives.
"""
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class ConflictResult:
    """Result of conflict resolution analysis."""
    final_score: float
    confidence: str
    confidence_value: float
    agreement: float
    conflicts: List[str]
    recommended_action: str


class ConflictResolver:
    """
    Resolves disagreements between similarity engines.
    
    Uses variance analysis, agreement voting, and heuristic rules to
    detect and resolve conflicts between AST/GST/Token/Semantic scores.
    """
    
    def resolve(self, engine_scores: Dict[str, float]) -> ConflictResult:
        """
        Resolve conflicts between engine scores.
        
        Args:
            engine_scores: Dictionary of scores from all engines:
                ast, gst, token, semantic, cfg
        
        Returns:
            ConflictResult with resolved score and confidence
        """
        scores = []
        ast = engine_scores.get("ast", 0.0)
        gst = engine_scores.get("gst", 0.0)
        token = engine_scores.get("token", 0.0)
        semantic = engine_scores.get("semantic", 0.0)
        cfg = engine_scores.get("cfg", 0.0)
        
        core_scores = [ast, gst, token]
        all_scores = [ast, gst, token, semantic, cfg]
        
        # Calculate variance and disagreement
        mean = np.mean(all_scores)
        variance = np.var(all_scores)
        max_disagreement = max(all_scores) - min(all_scores)
        
        # Pairwise differences
        ast_gst_diff = abs(ast - gst)
        ast_token_diff = abs(ast - token)
        gst_token_diff = abs(gst - token)
        total_pairwise = ast_gst_diff + ast_token_diff + gst_token_diff
        
        conflicts = []
        confidence = "low_confidence"
        confidence_value = 0.3
        
        # Conflict detection rules
        if ast > 0.9 and gst < 0.5:
            conflicts.append("High AST similarity but low GST match - likely rename obfuscation")
        
        if gst > 0.8 and ast < 0.5:
            conflicts.append("High GST match but low AST similarity - likely surface copy")
        
        if token > 0.7 and ast < 0.4:
            conflicts.append("High token overlap but structural differences - likely common code")
        
        if semantic > 0.8 and ast < 0.5:
            conflicts.append("High semantic similarity but different structure")
        
        # Confidence classification rules
        if total_pairwise < 0.3 and mean > 0.7:
            confidence = "high_confidence"
            confidence_value = 0.95
        elif ast > 0.85 and gst > 0.7 and total_pairwise < 0.6:
            confidence = "high_confidence"
            confidence_value = 0.9
        elif ast > 0.8 and gst > 0.5:
            confidence = "medium_confidence"
            confidence_value = 0.7
        elif ast > 0.7 and total_pairwise < 1.0:
            confidence = "medium_confidence"
            confidence_value = 0.6
        elif total_pairwise > 1.2:
            confidence = "low_confidence"
            confidence_value = 0.3
            conflicts.append("Strong engine disagreement - result unreliable")
        else:
            confidence = "low_confidence"
            confidence_value = 0.4
        
        # Adjust final score based on agreement
        agreement_factor = 1.0 - (total_pairwise / 3.0)
        
        # Weighted final score with confidence adjustment
        if confidence == "high_confidence":
            # Strong agreement - weight all equally
            final_score = 0.5 * ast + 0.3 * gst + 0.2 * token
        elif confidence == "medium_confidence":
            # Partial agreement - trust AST most
            final_score = 0.6 * ast + 0.25 * gst + 0.15 * token
        else:
            # Disagreement - conservative weighting
            final_score = 0.7 * ast + 0.2 * gst + 0.1 * token
            # Penalize for disagreement
            final_score *= agreement_factor
        
        # Clamp to valid range
        final_score = min(1.0, max(0.0, final_score))
        
        # Recommended action
        if confidence == "high_confidence" and final_score > 0.8:
            recommended_action = "Auto-flag as suspicious"
        elif confidence == "medium_confidence" and final_score > 0.6:
            recommended_action = "Review recommended"
        elif confidence == "low_confidence" and final_score > 0.5:
            recommended_action = "Manual review required"
        else:
            recommended_action = "No action needed"
        
        return ConflictResult(
            final_score=round(final_score, 4),
            confidence=confidence,
            confidence_value=round(confidence_value, 2),
            agreement=round(agreement_factor, 2),
            conflicts=conflicts,
            recommended_action=recommended_action
        )
    
    def get_confidence_label(self, value: float) -> str:
        """Convert confidence value to human-readable label."""
        if value >= 0.8:
            return "HIGH"
        elif value >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"


class ConflictResolutionPipeline:
    """
    Full pipeline with conflict resolution.
    
    Combines:
    1. All engine scoring
    2. Conflict detection and resolution
    3. Score calibration
    4. Final verdict generation
    """
    
    def __init__(self):
        self.resolver = ConflictResolver()
        
        # Load base engine
        from src.backend.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
        self.engine = SimilarityEngine()
        register_builtin_algorithms(self.engine)
        
        # Load calibrator
        from src.backend.engines.score_calibration import ScoreCalibrator
        self.calibrator = ScoreCalibrator()
    
    def analyze(self, code_a: str, code_b: str) -> Dict[str, Any]:
        """Full analysis with conflict resolution."""
        result = self.engine.compare({"raw": code_a}, {"raw": code_b})
        engine_scores = result.get("individual_scores", {})
        
        # Resolve conflicts
        conflict_result = self.resolver.resolve(engine_scores)
        
        # Calibrate final score
        calibrated_score = self.calibrator.calibrate(conflict_result.final_score)
        
        return {
            "final_score": conflict_result.final_score,
            "calibrated_score": round(calibrated_score, 4),
            "confidence": conflict_result.confidence,
            "confidence_value": conflict_result.confidence_value,
            "agreement": conflict_result.agreement,
            "conflicts": conflict_result.conflicts,
            "recommended_action": conflict_result.recommended_action,
            "engine_scores": {k: round(v, 4) for k, v in engine_scores.items()},
            "raw_overall_score": round(result.get("overall_score", 0.0), 4)
        }
