"""
Review Report Builder - Generates teacher-readable plagiarism reports with evidence chain.

Produces structured reports with:
1. Summary (score, label, confidence) - readable in 5 seconds
2. Evidence (feature similarity with HIGH/MEDIUM/LOW impact)
3. Analysis (natural language explanations)
4. Code comparison (matched blocks)
5. Recommendation (action based on score)
6. Teacher decision tracking (approve/reject/review)
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

TEMPLATES = {
    "ast": "Code structure is highly similar ({value:.0%})",
    "fingerprint": "Code fingerprint overlap detected ({value:.0%})",
    "embedding": "Semantic meaning is nearly identical ({value:.0%})",
    "token": "Token patterns match closely ({value:.0%})",
    "ngram": "Code sequences share common patterns ({value:.0%})",
    "winnowing": "Winnowing fingerprints overlap ({value:.0%})",
}

RECOMMENDATIONS = [
    (0.9, "Strong evidence of plagiarism. Recommend immediate action."),
    (0.75, "Likely plagiarism. Recommend detailed review."),
    (0.6, "Suspicious. Manual inspection needed."),
    (0.4, "Some similarities detected. May be coincidence."),
    (0.0, "No significant similarity detected."),
]

def _level(impact):
    if impact > 0.25: return "HIGH"
    elif impact > 0.1: return "MEDIUM"
    return "LOW"

def _get_rec(score):
    for t, rec in RECOMMENDATIONS:
        if score > t: return rec
    return "Review recommended."

def _label(score):
    if score > 0.9: return "HIGH RISK"
    if score > 0.75: return "MEDIUM RISK"
    if score > 0.6: return "SUSPICIOUS"
    return "LOW RISK"

@dataclass
class PlagiarismReport:
    """Complete plagiarism review report for teachers."""
    submission_a: str
    submission_b: str
    score: float
    confidence: float
    label: int
    features: Dict[str, float] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    analysis: List[str] = field(default_factory=list)
    recommendation: str = ""
    matched_blocks: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.recommendation:
            self.recommendation = _get_rec(self.score)
        if not self.evidence:
            self.evidence = self._build_evidence()
        if not self.analysis:
            self.analysis = self._build_analysis()
    
    def _build_evidence(self):
        return sorted([
            {"type": k, "label": FEATURE_LABELS.get(k, k), "value": round(v, 3),
             "impact": v, "level": _level(v)}
            for k, v in self.features.items()
        ], key=lambda x: -x["impact"])
    
    def _build_analysis(self):
        return list(set(
            TEMPLATES.get(k, f"{k} detected ({v:.0%})").format(value=v)
            for k, v in self.features.items() if v > 0.5
        ))
    
    def to_dict(self):
        return {
            "summary": {"submission_a": self.submission_a, "submission_b": self.submission_b,
                        "score": round(self.score, 3), "confidence": round(self.confidence, 3),
                        "label": _label(self.score), "decision": "plagiarism" if self.label else "clean"},
            "evidence": self.evidence,
            "analysis": self.analysis,
            "recommendation": self.recommendation,
            "matched_blocks": self.matched_blocks,
            "metadata": {"timestamp": self.timestamp}}

class ReportBuilder:
    """Generates teacher-ready plagiarism reports from detection results."""
    def build(self, subs, features, score, confidence, label, blocks=None):
        """
        Build report for teacher review.
        subs: {"A": "student1.py", "B": "student2.py"}
        features: {"ast": 0.92, "fingerprint": 0.78, ...}
        """
        return PlagiarismReport(
            submission_a=subs.get("A",""), submission_b=subs.get("B",""),
            score=score, confidence=confidence, label=label,
            features=features, matched_blocks=blocks or [])
