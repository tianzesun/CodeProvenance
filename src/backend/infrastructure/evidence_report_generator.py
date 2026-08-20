"""Formal Evidence Report Generator for Academic Integrity Cases.

This module generates dean-ready, academically defensible evidence reports
that can be used in academic review processes and disciplinary hearings.

Report Structure:
1. Case Summary
2. Evidence Overview
3. Matched Evidence Details
4. Conflict & Weakness Analysis
5. Rule-Based Interpretation
6. Final Verdict
7. Auditability Section
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class VerdictType(str, Enum):
    """Allowed verdict types for academic integrity reports."""

    CLEAN = "CLEAN"
    SUSPICIOUS = "SUSPICIOUS"
    STRONG_SIMILARITY = "STRONG_SIMILARITY"


@dataclass
class EvidenceDetail:
    """Detailed evidence match information."""

    file_a_location: str
    file_b_location: str
    match_type: str
    similarity_score: float
    explanation: str
    code_snippet_a: str | None = None
    code_snippet_b: str | None = None


@dataclass
class EvidenceCategory:
    """Evidence category summary."""

    category: str
    strength: str  # LOW, MODERATE, HIGH
    explanation: str
    score: float


class EvidenceReportGenerator:
    """Generate formal evidence reports for academic integrity cases."""

    def __init__(
        self, system_version: str = "1.0.0", rule_set_version: str = "1.0"
    ) -> None:
        self.system_version = system_version
        self.rule_set_version = rule_set_version

    def generate_report(
        self,
        case_id: str,
        submission_a: str,
        submission_b: str,
        verdict: VerdictType,
        confidence: float,
        evidence_categories: list[EvidenceCategory],
        matched_details: list[EvidenceDetail],
        conflict_analysis: list[str],
        triggered_rules: list[str],
        course_context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generate a formal evidence report.

        Args:
            case_id: Unique case identifier
            submission_a: First submission identifier
            submission_b: Second submission identifier
            verdict: Final verdict (CLEAN, SUSPICIOUS, STRONG_SIMILARITY)
            confidence: Rule-based confidence (0.0-1.0)
            evidence_categories: List of evidence category summaries
            matched_details: Detailed match information
            conflict_analysis: List of conflict/weakness notes
            triggered_rules: Rules that triggered the verdict
            course_context: Optional course/assignment info

        Returns:
            Formal evidence report dictionary
        """
        report = {
            "report_metadata": {
                "report_id": case_id,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "system_version": self.system_version,
                "rule_set_version": self.rule_set_version,
            },
            "case_summary": {
                "submission_a_id": submission_a,
                "submission_b_id": submission_b,
            },
            "evidence_overview": [
                {
                    "category": cat.category,
                    "strength": cat.strength,
                    "explanation": cat.explanation,
                    "raw_score": cat.score,
                }
                for cat in evidence_categories
            ],
            "matched_evidence_details": [
                {
                    "file_a_location": detail.file_a_location,
                    "file_b_location": detail.file_b_location,
                    "match_type": detail.match_type,
                    "similarity_score": detail.similarity_score,
                    "explanation": detail.explanation,
                    "code_snippet_a": detail.code_snippet_a,
                    "code_snippet_b": detail.code_snippet_b,
                }
                for detail in matched_details
            ],
            "conflict_and_weakness_analysis": conflict_analysis,
            "rule_based_interpretation": {
                "triggered_rules": triggered_rules,
                "interpretation": self._generate_interpretation(
                    triggered_rules, verdict
                ),
            },
            "final_verdict": {
                "verdict": verdict.value,
                "confidence": f"{confidence:.0%}",
            },
            "auditability_section": {
                "system_version": self.system_version,
                "rule_set_version": self.rule_set_version,
                "reproducibility_notes": "This report was generated using deterministic policy rules. All decisions are reproducible given the same input evidence.",
            },
        }
        return report

    def _generate_interpretation(
        self, triggered_rules: list[str], verdict: VerdictType
    ) -> str:
        """Generate human-readable interpretation."""
        if "IDENTITY_MATCH" in triggered_rules:
            return "Exact or near-exact match detected between submissions."
        elif "STRONG_STRUCTURAL" in triggered_rules:
            return "Strong structural similarity (AST/control flow) indicates substantial code overlap."
        elif "SEMANTIC_DOMINANCE" in triggered_rules:
            return "High semantic similarity with supporting structural evidence suggests potential collaboration or external source usage."
        elif "WEAK_SIGNAL_GUARD" in triggered_rules:
            return "Insufficient structural evidence to establish similarity. Files appear to be independent works."
        elif "CONFLICT_RULE" in triggered_rules:
            return "Inconsistent evidence patterns require manual review. Signals do not align consistently."
        else:
            return "Evidence patterns require careful academic judgment."

    def to_json(self, report: dict[str, Any]) -> str:
        """Convert report to JSON string."""
        return json.dumps(report, indent=2)

    def to_html(self, report: dict[str, Any]) -> str:
        """Convert report to HTML format."""
        # This would contain the HTML generation logic
        # For now, return a placeholder
        return f"<html><body><pre>{json.dumps(report, indent=2)}</pre></body></html>"
