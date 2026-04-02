"""Detect Submission Use Case - orchestrates the submission detection flow."""
from typing import Dict, List, Any, Optional
from src.engines.features.feature_extractor import FeatureExtractor
from src.engines.scoring.fusion_engine import FusionEngine
from src.domain.decision import DecisionEngine


class DetectSubmission:
    """Application use case for detecting code similarity in submissions."""

    def __init__(self, weights: Optional[Dict[str, float]] = None, threshold: float = 0.5):
        self.feature_extractor = FeatureExtractor()
        self.fusion_engine = FusionEngine(weights)
        self.decision_engine = DecisionEngine(threshold)
        self.threshold = threshold

    def execute(self, code_a: str, code_b: str) -> Dict[str, Any]:
        """Execute similarity detection for a pair of code submissions.

        Args:
            code_a: Source code of the first submission.
            code_b: Source code of the second submission.

        Returns:
            Dictionary containing score, decision, and confidence.
        """
        features = self.feature_extractor.extract(code_a, code_b)
        fused = self.fusion_engine.fuse(features)
        decision = self.decision_engine.decide(fused.final_score)

        return {
            "score": fused.final_score,
            "confidence": fused.confidence,
            "decision": decision.final_verdict,
            "threshold": self.threshold,
            "features": {
                "ast": features.ast,
                "fingerprint": features.fingerprint,
                "embedding": features.embedding,
                "ngram": features.ngram,
                "winnowing": features.winnowing,
            },
        }

    def batch_execute(self, submissions: Dict[str, str]) -> List[Dict[str, Any]]:
        """Execute similarity detection for all pairs of submissions.

        Args:
            submissions: Dictionary mapping filenames to source code.

        Returns:
            List of result dictionaries for each pair.
        """
        results = []
        filenames = list(submissions.keys())

        for i, name_a in enumerate(filenames):
            for name_b in filenames[i + 1:]:
                code_a = submissions[name_a]
                code_b = submissions[name_b]
                result = self.execute(code_a, code_b)
                result["file_a"] = name_a
                result["file_b"] = name_b
                results.append(result)

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results