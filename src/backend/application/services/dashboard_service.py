"""Dashboard Service - Generates teacher-ready case list with risk levels and evidence."""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Review priority levels based on similarity score thresholds
# These represent investigation priority rather than absolute risk assessment
RISK_LEVELS: list[tuple[float, str]] = [
    (0.85, "CRITICAL"),  # Requires corroborating evidence
    (0.65, "HIGH"),      # High review priority
    (0.35, "MEDIUM"),    # Moderate review priority
    (0.0, "LOW"),        # Low review priority
]

EXPLANATION_LABELS: Dict[str, str] = {
    "ast": "Code structure",
    "fingerprint": "Token patterns",
    "embedding": "Semantic meaning",
    "token": "Token overlap",
    "ngram": "Code sequences",
    "winnowing": "Fingerprint match",
}


def _risk_level(score: float) -> str:
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return "LOW"


def _top_features(features: Dict[str, float], top_n: int = 5) -> List[Dict[str, Any]]:
    """Return the top-N features sorted by value descending."""
    ranked = sorted(
        [
            {
                "name": k,
                "label": EXPLANATION_LABELS.get(k, k),
                "value": round(v, 3),
                "level": "HIGH" if v > 0.75 else ("MEDIUM" if v > 0.5 else "LOW"),
            }
            for k, v in features.items()
        ],
        key=lambda x: -x["value"],
    )
    return ranked[:top_n]


@dataclass
class DetectionCase:
    """A single detection case for the dashboard."""

    submission_a: str
    submission_b: str
    score: float
    risk_level: str
    top_features: List[Dict[str, Any]] = field(default_factory=list)
    explanation: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    decision: Optional[str] = None  # None | "plagiarism" | "clean" | "review"
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "submission_a": self.submission_a,
            "submission_b": self.submission_b,
            "score": round(self.score, 3),
            "risk_level": self.risk_level,
            "top_features": self.top_features,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "decision": self.decision,
            "timestamp": self.timestamp,
        }


class DashboardService:
    """Generates dashboard case list sorted by risk level."""

    def __init__(self, threshold: float = 0.5) -> None:
        from src.backend.engines.features.feature_extractor import FeatureExtractor
        from src.backend.engines.scoring.fusion_engine import FusionEngine
        from src.backend.domain.decision import DecisionEngine
        from src.backend.evaluation.arbitration import BayesianArbitrator
        from src.backend.ml.fusion_model import HybridFusionModel
        from src.backend.engines.ai.transformer_detector import AIDetectionLayer
        from src.backend.application.services.behavioral_analysis import KeystrokeAnalysisService
        from src.backend.infrastructure.indexing.web_search import WebSearchService

        self._feature_extractor = FeatureExtractor()
        self._fusion_engine = FusionEngine()
        self._decision_engine = DecisionEngine(threshold)
        self._arbitrator = BayesianArbitrator()
        self._hybrid_model = HybridFusionModel()
        self._ai_layer = AIDetectionLayer()
        self._behavioral_service = KeystrokeAnalysisService()
        self._web_search = WebSearchService()

    def analyze_batch(self, submissions: Dict[str, str], keystrokes: Optional[Dict[str, List[Any]]] = None) -> List[DetectionCase]:
        """Analyze all pairs and return sorted case list."""
        cases: List[DetectionCase] = []

        files = list(submissions.keys())
        for i, fa in enumerate(files):
            # 1. Individual Behavioral Check
            behavioral_a = {}
            if keystrokes and fa in keystrokes:
                behavioral_a = self._behavioral_service.analyze_session(keystrokes[fa])
                
            # 2. Web-Scale Search (Individual)
            web_results_a = self._web_search.perform_full_web_scan(submissions[fa], "python")
            
            for fb in files[i + 1 :]:
                ca, cb = submissions[fa], submissions[fb]

                # Run similarity detection
                features = self._feature_extractor.extract(ca, cb)
                feature_dict = features.as_dict()
                
                # AI & Stylometry Analysis (New Forensic Tier)
                ai_a = self._ai_layer.analyze(ca)
                ai_b = self._ai_layer.analyze(cb)
                
                # Hybrid ML Fusion
                ml_score = self._hybrid_model.predict_similarity(feature_dict)
                explanations = self._hybrid_model.explain_prediction(feature_dict)
                
                # Statistical Arbitration
                arbitration = self._arbitrator.arbitrate(feature_dict)
                
                # Final Score
                final_score = (ml_score + arbitration.fused_score) / 2
                
                case = DetectionCase(
                    submission_a=fa,
                    submission_b=fb,
                    score=final_score,
                    risk_level=_risk_level(final_score),
                    top_features=_top_features(feature_dict),
                    explanation=[
                        {
                            "engine": name,
                            "score": round(value, 3),
                            "contribution": round(arbitration.engine_contributions.get(name, 0.0), 3)
                        }
                        for name, value in feature_dict.items()
                    ],
                    evidence=[
                        {"name": "Agreement Index", "value": round(arbitration.agreement_index, 3)},
                        {"name": "Uncertainty", "value": round(arbitration.uncertainty, 3)},
                        {"name": "ML Insights", "value": " | ".join(explanations) if explanations else "None"},
                        {"name": "AI Prob (A/B)", "value": f"{round(ai_a['ai_probability'], 2)} / {round(ai_b['ai_probability'], 2)}"},
                        {"name": "Detection Decision", "value": f"{ai_a['decision']} / {ai_b['decision']}"},
                        {"name": "Behavioral Anomaly (A)", "value": f"{behavioral_a.get('behavioral_anomaly_score', 0.0):.2f}"},
                        {"name": "Web Max Similarity (A)", "value": f"{web_results_a.get('max_web_similarity', 0.0):.2f}"}
                    ],
                )
                cases.append(case)

        cases.sort(key=lambda x: x.score, reverse=True)
        return cases


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_features(code_a: str, code_b: str) -> Dict[str, float]:
    """Extract feature similarities from a code pair.

    Each engine is loaded lazily so a missing model or dependency only
    affects that single feature and is logged for debugging.
    """
    feats: Dict[str, float] = {}
    for feature, module_name in [
        ("ast", "ast_similarity"),
        ("fingerprint", "token_similarity"),
        ("embedding", "winnowing_similarity"),
        ("ngram", "ngram_similarity"),
        ("winnowing", "winnowing_similarity"),
    ]:
        try:
            module = __import__(
                f"src.engines.similarity.{module_name}", fromlist=[""]
            )
            cls_name = _ENGINE_CLASS_NAMES.get(feature, f"{feature.capitalize()}Similarity")
            sim_cls = getattr(module, cls_name)
            feats[feature] = sim_cls().compare({"raw": code_a}, {"raw": code_b})
        except ImportError as exc:
            logger.debug("Feature '%s' skipped (import error): %s", feature, exc)
            feats[feature] = 0.0
        except AttributeError as exc:
            logger.debug("Feature '%s' skipped (missing class %s): %s", feature, _ENGINE_CLASS_NAMES.get(feature, ""), exc)
            feats[feature] = 0.0
        except Exception as exc:
            logger.warning("Feature '%s' failed unexpectedly: %s", feature, exc)
            feats[feature] = 0.0
    return feats


def _fuse_score(features: Dict[str, float]) -> float:
    """Simple weighted fusion of feature scores."""
    weights: Dict[str, float] = {
        "ast": 0.35,
        "fingerprint": 0.40,
        "embedding": 0.25,
        "ngram": 0.0,
        "winnowing": 0.0,
    }
    return min(1.0, sum(v * weights.get(k, 0.0) for k, v in features.items()))