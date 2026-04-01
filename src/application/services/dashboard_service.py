"""Dashboard Service - Generates teacher-ready case list with risk levels and evidence."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

RISK_LEVELS = [(0.9, "CRITICAL"), (0.75, "HIGH"), (0.5, "MEDIUM"), (0.0, "LOW")]

EXPLANATION_LABELS = {
    "ast": "Code structure", "fingerprint": "Token patterns",
    "embedding": "Semantic meaning", "token": "Token overlap",
    "ngram": "Code sequences", "winnowing": "Fingerprint match",
}

FEATURE_ORDERS = [
    ["ast","fingerprint","embedding","ngram","winnowing"],
]

def _risk_level(score: float) -> str:
    for t, level in RISK_LEVELS:
        if score >= t: return level
    return "LOW"

def _top_features(features: Dict[str, float], top_n: int = 5) -> List[Dict[str, Any]]:
    return sorted([{"name": k, "label": EXPLANATION_LABELS.get(k, k),
                    "value": round(v, 3), "level": "HIGH" if v > 0.75 else ("MEDIUM" if v > 0.5 else "LOW")}
                   for k, v in features.items()], key=lambda x: -x["value"])[:top_n]

@dataclass
class DetectionCase:
    """A single detection case for the dashboard."""
    submission_a: str
    submission_b: str
    score: float
    risk_level: str
    top_features: List[Dict[str, Any]] = field(default_factory=list)
    explanation: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    decision: Optional[str] = None  # None | "plagiarism" | "clean" | "review"
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {"submission_a": self.submission_a, "submission_b": self.submission_b,
                "score": round(self.score, 3), "risk_level": self.risk_level,
                "top_features": self.top_features, "explanation": self.explanation,
                "evidence": self.evidence, "decision": self.decision, "timestamp": self.timestamp}

class DashboardService:
    """Generates dashboard case list sorted by risk level."""
    
    def analyze_batch(self, submissions: Dict[str, str]) -> List[DetectionCase]:
        """
        Analyze all pairs and return sorted case list.
        
        Args:
            submissions: {"filename.py": "code content", ...}
        """
        from src.infrastructure.report import ReportBuilder
        from src.domain.decision import DecisionEngine
        
        builder = ReportBuilder()
        engine = DecisionEngine()
        cases = []
        
        files = list(submissions.keys())
        for i, fa in enumerate(files):
            for fb in files[i+1:]:
                ca, cb = submissions[fa], submissions[fb]
                
                # Run detection
                features = _extract_features(ca, cb)
                fused = _fuse_score(features)
                result = engine.decide(fused)
                
                # Build report
                report = builder.build(
                    {"A": fa, "B": fb}, features,
                    fused, 0.8, result.final_verdict)
                
                case = DetectionCase(
                    submission_a=fa, submission_b=fb,
                    score=fused, risk_level=_risk_level(fused),
                    top_features=_top_features(features),
                    explanation=report.analysis,
                    evidence=report.evidence,
                )
                cases.append(case)
        
        # Sort by score (highest risk first)
        cases.sort(key=lambda x: x.score, reverse=True)
        return cases
    
    def get_summary(self, cases: List[DetectionCase]) -> Dict[str, Any]:
        total = len(cases)
        critical = sum(1 for c in cases if c.risk_level == "CRITICAL")
        high = sum(1 for c in cases if c.risk_level == "HIGH")
        medium = sum(1 for c in cases if c.risk_level == "MEDIUM")
        low = sum(1 for c in cases if c.risk_level == "LOW")
        return {"total": total, "critical": critical, "high": high, 
                "medium": medium, "low": low,
                "high_risk": critical + high}


def _extract_features(code_a: str, code_b: str) -> Dict[str, float]:
    """Extract feature similarities from code pair."""
    feats = {}
    for feat, module in [("ast", "ast_similarity"), ("fingerprint", "token_similarity"),
                         ("embedding", "embedding_similarity"), ("ngram", "ngram_similarity"),
                         ("winnowing", "winnowing_similarity")]:
        try:
            mod = __import__(f"src.engines.similarity.{module}", fromlist=[""])
            try:
                cls = getattr(mod, "ASTSimilarity" if feat=="ast" else 
                              f"{feat.capitalize()}Similarity")
                feats[feat] = cls().compare({'raw': code_a}, {'raw': code_b})
            except: feats[feat] = 0.0
        except: feats[feat] = 0.0
    return feats

def _fuse_score(features: Dict[str, float]) -> float:
    """Simple weighted fusion."""
    weights = {"ast": 0.35, "fingerprint": 0.40, "embedding": 0.25, "ngram": 0.0, "winnowing": 0.0}
    return min(1.0, sum(v * weights.get(k, 0.0) for k, v in features.items()))
