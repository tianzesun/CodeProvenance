"""Review Report Builder - Generates teacher-readable plagiarism reports with evidence chain.

Produces structured reports with:
1. Summary (score, label, confidence)
2. Evidence (feature similarity levels)
3. Analysis (natural language explanation)
4. Code comparison (matched blocks)
5. Recommendation (action based on score)
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

FEATURE_LABELS = {
    "ast": "Code structure similarity",
    "fingerprint": "Fingerprint overlap",
    "embedding": "Semantic similarity",
    "token": "Token-level similarity",
    "ngram": "N-gram similarity",
    "winnowing": "Fingerprint match",
}

EXPLANATION_TEMPLATES = {
    "ast": "Code structure is highly similar",
    "fingerprint": "Code fingerprint overlap detected",
    "embedding": "Semantic meaning is nearly identical",
    "token": "Token patterns match closely",
    "ngram": "Code sequences share common patterns",
    "winnowing": "Winnowing fingerprints overlap",
}

RECOMMENDATIONS = {
    (0.9, 1.0): "Strong evidence of plagiarism. Recommend immediate action.",
    (0.75, 0.9): "Likely plagiarism. Recommend detailed review.",
    (0.6, 0.75): "Suspicious. Manual inspection needed.",
    (0.4, 0.6): "Some similarities detected. May be coincidence.",
    (0.0, 0.4): "No significant similarity detected.",
}

def _level(impact: float) -> str:
    if impact > 0.25: return "HIGH"
    elif impact > 0.1: return "MEDIUM"
    return "LOW"

def _get_recommendation(score: float) -> str:
    for (lo, hi), rec in RECOMMENDATIONS.items():
        if lo < score <= hi:
            return rec
    return "Review recommended."

def _score_label(score: float) -> str:
    if score > 0.9: return "HIGH RISK"
    if score > 0.75: return "MEDIUM RISK"
    if score > 0.6: return "SUSPICIOUS"
    return "LOW RISK"

def _format_evidence(features: Dict[str, float]) -> List[Dict[str, Any]]:
    """Build evidence chain from feature similarities."""
    evidence = []
    for feat, val in features.items():
        label = FEATURE_LABELS.get(feat, feat)
        impact = val  # Higher similarity = higher impact
        evidence.append({
            "type": feat,
            "label": label,
            "value": round(val, 3),
            "impact": impact,
            "level": _level(impact),
        })
    return sorted(evidence, key=lambda x: -abs(x["impact"]))

def _format_analysis(features: Dict[str, float]) -> List[str]:
    """Generate natural language explanations."""
    lines = []
    for feat, val in features.items():
        if val > 0.5:
            tmpl = EXPLANATION_TEMPLATES.get(feat, f"{feat} similarity detected")
            lines.append(tmpl)
    return list(set(lines))

@dataclass
class PlagiarismReport:
    """Complete plagiarism review report."""
    submission_a: str
    submission_b: str
    score: float
    confidence: float
    label: int
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    analysis: List[str] = field(default_factory=list)
    recommendation: str = ""
    matched_blocks: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.recommendation:
            self.recommendation = _get_recommendation(self.score)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "submission_a": self.submission_a,
                "submission_b": self.submission_b,
                "score": round(self.score, 3),
                "confidence": round(self.confidence, 3),
                "label": _score_label(self.score),
                "decision": "plagiarism" if self.label == 1 else "clean",
            },
            "evidence": self.evidence,
            "analysis": self.analysis,
            "recommendation": self.recommendation,
            "matched_blocks": self.matched_blocks,
            "metadata": {"timestamp": self.timestamp},
        }

class ReportBuilder:
    """Builds plagiarism review reports from detection results."""
    def build(self, submissions: Dict[str, str], features: Dict[str, float],
              score: float, confidence: float, label: int,
              matched_blocks: List[Dict[str, Any]] = None) -> PlagiarismReport:
        """
        Build complete plagiarism report.
        
        Args:
            submissions: {"A": "...", "B": "..."}
            features: {"ast": 0.9, "fingerprint": 0.85, ...}
            score: Overall plagiarism score [0, 1]
            confidence: Decision confidence [0, 1]
            label: 1=plagiarism, 0=clean
            matched_blocks: Code comparison evidence
        """
        evidence = _format_evidence(features)
        analysis = _format_analysis(features)
        blocks = matched_blocks or []
        return PlagiarismReport(
            submission_a=submissions.get("A", ""),
            submission_b=submissions.get("B", ""),
            score=score, confidence=confidence, label=label,
            evidence=evidence, analysis=analysis,
            matched_blocks=blocks,
        )

# For backward compatibility
def build_review_report(submissions, features, score, confidence, label,
                        matched_blocks=None) -> Dict[str, Any]:
    """Generate review report JSON."""
    builder = ReportBuilder()
    report = builder.build(submissions, features, score, confidence, label, matched_blocks)
    return report.to_dict()
