"""
Decision Authority - Single Source of Truth for Final Verdicts

This module is the ONLY place that produces final decisions.
All other modules must provide inputs, not make decisions.

Responsibility: Collects engine outputs, normalizes scores, applies weighting policy,
produces final verdict, and logs reasoning trace.

This separates research systems (multiple decision points) from engineered systems (single authority).
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class Verdict(Enum):
    """Final verdict categories."""
    PLAGIARIZED = "plagiarized"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    UNCERTAIN = "uncertain"


@dataclass
class EngineOutput:
    """Output from a single engine."""
    engine_name: str
    engine_version: str
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ReasoningStep:
    """Single step in reasoning trace."""
    step_name: str
    input_data: Any
    output_data: Any
    rationale: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DecisionTrace:
    """Complete reasoning trace for a decision."""
    decision_id: str
    timestamp: str
    engine_outputs: List[EngineOutput]
    normalized_scores: Dict[str, float]
    weighted_score: float
    final_verdict: Verdict
    confidence: float
    reasoning_steps: List[ReasoningStep]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionResult:
    """Final decision result."""
    verdict: Verdict
    confidence: float
    weighted_score: float
    trace: DecisionTrace
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScoreNormalizer:
    """Normalizes scores from different engines to common scale."""
    
    @staticmethod
    def normalize(score: float, engine_name: str, metadata: Dict[str, Any]) -> float:
        """Normalize score to 0.0-1.0 range.
        
        Different engines may produce scores in different ranges.
        This normalizes them to a common scale.
        """
        # Handle different score ranges
        if engine_name in ["ast", "token", "graph"]:
            # These engines produce 0.0-1.0 directly
            return max(0.0, min(1.0, score))
        
        elif engine_name == "embedding":
            # Embedding scores may need transformation
            # Cosine similarity is already -1 to 1, normalize to 0 to 1
            return (score + 1.0) / 2.0
        
        elif engine_name == "execution":
            # Execution scores may be boolean or percentage
            if isinstance(score, bool):
                return 1.0 if score else 0.0
            return max(0.0, min(1.0, score))
        
        elif engine_name == "ngram":
            # N-gram overlap is already 0.0-1.0
            return max(0.0, min(1.0, score))
        
        else:
            # Default: clamp to 0.0-1.0
            return max(0.0, min(1.0, score))


class WeightingPolicy:
    """Applies weighting policy to normalized scores."""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """Initialize with custom weights or use defaults."""
        self.weights = weights or {
            "ast": 0.25,
            "token": 0.20,
            "graph": 0.20,
            "embedding": 0.15,
            "execution": 0.10,
            "ngram": 0.10,
        }
        
        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
    
    def apply(self, normalized_scores: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
        """Apply weights to normalized scores.
        
        Returns:
            Tuple of (weighted_score, contribution_breakdown)
        """
        weighted_score = 0.0
        contributions = {}
        
        for engine_name, score in normalized_scores.items():
            weight = self.weights.get(engine_name, 0.0)
            contribution = score * weight
            weighted_score += contribution
            contributions[engine_name] = contribution
        
        return weighted_score, contributions


class VerdictClassifier:
    """Classifies weighted score into final verdict."""
    
    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """Initialize with custom thresholds or use defaults."""
        self.thresholds = thresholds or {
            "plagiarized": 0.85,
            "suspicious": 0.60,
            "clean": 0.30,
        }
    
    def classify(self, weighted_score: float, confidence: float) -> Verdict:
        """Classify weighted score into verdict."""
        # Adjust verdict based on confidence
        effective_score = weighted_score * confidence
        
        if effective_score >= self.thresholds["plagiarized"]:
            return Verdict.PLAGIARIZED
        elif effective_score >= self.thresholds["suspicious"]:
            return Verdict.SUSPICIOUS
        elif effective_score >= self.thresholds["clean"]:
            return Verdict.CLEAN
        else:
            return Verdict.UNCERTAIN


class DecisionAuthority:
    """
    Single source of truth for final decisions.
    
    This is the ONLY module that produces final verdicts.
    All other modules must provide inputs, not make decisions.
    
    Responsibilities:
    1. Collects engine outputs
    2. Normalizes scores
    3. Applies weighting policy
    4. Produces final verdict
    5. Logs reasoning trace
    """
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        """Initialize decision authority.
        
        Args:
            weights: Custom weights for each engine
            thresholds: Custom thresholds for verdict classification
        """
        self.normalizer = ScoreNormalizer()
        self.weighting_policy = WeightingPolicy(weights)
        self.verdict_classifier = VerdictClassifier(thresholds)
        self.decision_counter = 0
    
    def decide(
        self,
        engine_outputs: List[EngineOutput],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """
        Make final decision based on engine outputs.
        
        This is the SINGLE SOURCE OF TRUTH for decisions.
        All other code must call this function, not make decisions directly.
        
        Args:
            engine_outputs: List of outputs from all engines
            metadata: Additional metadata for decision
            
        Returns:
            DecisionResult with verdict, confidence, and reasoning trace
        """
        self.decision_counter += 1
        decision_id = f"decision_{self.decision_counter:06d}"
        timestamp = datetime.now().isoformat()
        
        reasoning_steps = []
        
        # Step 1: Collect engine outputs
        reasoning_steps.append(ReasoningStep(
            step_name="collect_outputs",
            input_data=[{"engine": e.engine_name, "score": e.score} for e in engine_outputs],
            output_data={"num_engines": len(engine_outputs)},
            rationale=f"Collected outputs from {len(engine_outputs)} engines",
        ))
        
        # Step 2: Normalize scores
        normalized_scores = {}
        for output in engine_outputs:
            normalized = self.normalizer.normalize(
                output.score,
                output.engine_name,
                output.metadata
            )
            normalized_scores[output.engine_name] = normalized
        
        reasoning_steps.append(ReasoningStep(
            step_name="normalize_scores",
            input_data={e.engine_name: e.score for e in engine_outputs},
            output_data=normalized_scores,
            rationale="Normalized all scores to 0.0-1.0 range",
        ))
        
        # Step 3: Apply weighting policy
        weighted_score, contributions = self.weighting_policy.apply(normalized_scores)
        
        reasoning_steps.append(ReasoningStep(
            step_name="apply_weights",
            input_data=normalized_scores,
            output_data={"weighted_score": weighted_score, "contributions": contributions},
            rationale=f"Applied weighting policy, weighted score: {weighted_score:.4f}",
        ))
        
        # Step 4: Calculate confidence
        # Confidence is based on agreement between engines
        if len(engine_outputs) > 1:
            scores = list(normalized_scores.values())
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            # Lower variance = higher confidence
            confidence = max(0.0, 1.0 - variance)
        else:
            confidence = engine_outputs[0].confidence if engine_outputs else 0.5
        
        reasoning_steps.append(ReasoningStep(
            step_name="calculate_confidence",
            input_data=normalized_scores,
            output_data={"confidence": confidence},
            rationale=f"Calculated confidence based on engine agreement: {confidence:.4f}",
        ))
        
        # Step 5: Classify verdict
        final_verdict = self.verdict_classifier.classify(weighted_score, confidence)
        
        reasoning_steps.append(ReasoningStep(
            step_name="classify_verdict",
            input_data={"weighted_score": weighted_score, "confidence": confidence},
            output_data={"verdict": final_verdict.value},
            rationale=f"Classified as {final_verdict.value} (score: {weighted_score:.4f}, confidence: {confidence:.4f})",
        ))
        
        # Create decision trace
        trace = DecisionTrace(
            decision_id=decision_id,
            timestamp=timestamp,
            engine_outputs=engine_outputs,
            normalized_scores=normalized_scores,
            weighted_score=weighted_score,
            final_verdict=final_verdict,
            confidence=confidence,
            reasoning_steps=reasoning_steps,
            metadata=metadata or {},
        )
        
        # Log decision
        logger.info(
            f"Decision {decision_id}: {final_verdict.value} "
            f"(score: {weighted_score:.4f}, confidence: {confidence:.4f})"
        )
        
        return DecisionResult(
            verdict=final_verdict,
            confidence=confidence,
            weighted_score=weighted_score,
            trace=trace,
            metadata={
                "decision_id": decision_id,
                "timestamp": timestamp,
                "num_engines": len(engine_outputs),
            }
        )
    
    def decide_from_scores(
        self,
        scores: Dict[str, float],
        confidences: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """Make decision from raw scores dictionary.
        
        Convenience method that creates EngineOutput objects from scores.
        
        Args:
            scores: Dictionary mapping engine names to scores
            confidences: Optional dictionary mapping engine names to confidences
            metadata: Additional metadata
            
        Returns:
            DecisionResult with verdict, confidence, and reasoning trace
        """
        engine_outputs = []
        
        for engine_name, score in scores.items():
            confidence = confidences.get(engine_name, 0.8) if confidences else 0.8
            
            engine_outputs.append(EngineOutput(
                engine_name=engine_name,
                engine_version="1.0",
                score=score,
                confidence=confidence,
                metadata=metadata or {},
            ))
        
        return self.decide(engine_outputs, metadata)
    
    def get_decision_trace(self, decision_id: str) -> Optional[DecisionTrace]:
        """Get decision trace by ID.
        
        Note: In production, this would query a database.
        For now, it returns None (traces are returned in DecisionResult).
        """
        # In production, implement database lookup
        return None
    
    def export_trace_json(self, trace: DecisionTrace) -> str:
        """Export decision trace as JSON."""
        trace_dict = {
            "decision_id": trace.decision_id,
            "timestamp": trace.timestamp,
            "engine_outputs": [
                {
                    "engine_name": e.engine_name,
                    "engine_version": e.engine_version,
                    "score": e.score,
                    "confidence": e.confidence,
                    "metadata": e.metadata,
                    "timestamp": e.timestamp,
                }
                for e in trace.engine_outputs
            ],
            "normalized_scores": trace.normalized_scores,
            "weighted_score": trace.weighted_score,
            "final_verdict": trace.final_verdict.value,
            "confidence": trace.confidence,
            "reasoning_steps": [
                {
                    "step_name": s.step_name,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "rationale": s.rationale,
                    "timestamp": s.timestamp,
                }
                for s in trace.reasoning_steps
            ],
            "metadata": trace.metadata,
        }
        
        return json.dumps(trace_dict, indent=2, default=str)


# Global decision authority instance
_authority: Optional[DecisionAuthority] = None


def get_decision_authority() -> DecisionAuthority:
    """Get the global decision authority (singleton)."""
    global _authority
    
    if _authority is None:
        _authority = DecisionAuthority()
    
    return _authority


def make_decision(
    engine_outputs: List[EngineOutput],
    metadata: Optional[Dict[str, Any]] = None,
) -> DecisionResult:
    """
    Make final decision.
    
    This is the SINGLE ENTRY POINT for decision making.
    All other code must call this function, not make decisions directly.
    
    Args:
        engine_outputs: List of outputs from all engines
        metadata: Additional metadata
        
    Returns:
        DecisionResult with verdict, confidence, and reasoning trace
    """
    authority = get_decision_authority()
    return authority.decide(engine_outputs, metadata)


def make_decision_from_scores(
    scores: Dict[str, float],
    confidences: Optional[Dict[str, float]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DecisionResult:
    """
    Make decision from raw scores.
    
    Convenience function that creates EngineOutput objects.
    
    Args:
        scores: Dictionary mapping engine names to scores
        confidences: Optional dictionary mapping engine names to confidences
        metadata: Additional metadata
        
    Returns:
        DecisionResult with verdict, confidence, and reasoning trace
    """
    authority = get_decision_authority()
    return authority.decide_from_scores(scores, confidences, metadata)