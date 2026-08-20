"""Evidence Viewer - Side-by-side comparison with matched elements highlighted.

Provides detailed evidence for similarity analysis with:
- Line-by-line diff visualization
- Matched function/block identification
- AST structure comparison
- Confidence scoring
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MatchedElement:
    """A matched code element between two submissions."""

    element_type: str  # 'function', 'class', 'block', 'statement'
    element_name: str
    start_line_a: int
    end_line_a: int
    start_line_b: int
    end_line_b: int
    similarity: float
    confidence: float = 1.0
    details: list[str] = field(default_factory=list)


@dataclass
class DiffHunk:
    """A hunk of diff output."""

    hunk_type: str  # 'added', 'removed', 'changed', 'context'
    line_number: int | None
    content: str
    original_content: str | None = None


@dataclass
class EvidenceView:
    """Complete evidence view for a submission pair."""

    submission_a_id: str
    submission_b_id: str
    similarity_score: float
    verdict: str
    confidence: float
    matched_elements: list[MatchedElement] = field(default_factory=list)
    diff_hunks: list[DiffHunk] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_a_id": self.submission_a_id,
            "submission_b_id": self.submission_b_id,
            "similarity_score": self.similarity_score,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "matched_elements": [
                {
                    "element_type": e.element_type,
                    "element_name": e.element_name,
                    "start_line_a": e.start_line_a,
                    "end_line_a": e.end_line_a,
                    "start_line_b": e.start_line_b,
                    "end_line_b": e.end_line_b,
                    "similarity": e.similarity,
                    "confidence": e.confidence,
                    "details": e.details,
                }
                for e in self.matched_elements
            ],
            "diff_hunks": [
                {
                    "hunk_type": d.hunk_type,
                    "line_number": d.line_number,
                    "content": d.content,
                    "original_content": d.original_content,
                }
                for d in self.diff_hunks
            ],
            "analysis_notes": self.analysis_notes,
            "recommendations": self.recommendations,
        }


class EvidenceViewer:
    """Generate evidence views for code similarity analysis."""

    def __init__(self) -> None:
        """Initialize the evidence viewer."""

    def generate_view(
        self,
        code_a: str,
        code_b: str,
        submission_a_id: str,
        submission_b_id: str,
        similarity_score: float,
        engine_details: dict[str, Any] | None = None,
    ) -> EvidenceView:
        """
        Generate an evidence view for a code pair.

        Args:
            code_a: First code submission.
            code_b: Second code submission.
            submission_a_id: ID of first submission.
            submission_b_id: ID of second submission.
            similarity_score: Overall similarity score.
            engine_details: Optional engine-specific details.

        Returns:
            EvidenceView with analysis results.
        """
        # Determine verdict based on similarity
        verdict = self._determine_verdict(similarity_score)
        confidence = self._calculate_confidence(similarity_score, engine_details)

        # Find matched elements
        matched_elements = self._find_matched_elements(code_a, code_b)

        # Generate diff hunks
        diff_hunks = self._generate_diff(code_a, code_b)

        # Generate analysis notes
        analysis_notes = self._generate_analysis_notes(
            similarity_score, matched_elements, engine_details
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(verdict, matched_elements)

        return EvidenceView(
            submission_a_id=submission_a_id,
            submission_b_id=submission_b_id,
            similarity_score=similarity_score,
            verdict=verdict,
            confidence=confidence,
            matched_elements=matched_elements,
            diff_hunks=diff_hunks,
            analysis_notes=analysis_notes,
            recommendations=recommendations,
        )

    def _determine_verdict(self, score: float) -> str:
        """Determine verdict based on similarity score."""
        if score >= 0.85:
            return "HIGH_RISK"
        elif score >= 0.70:
            return "MEDIUM_RISK"
        elif score >= 0.50:
            return "LOW_RISK"
        else:
            return "INCONCLUSIVE"

    def _calculate_confidence(
        self, score: float, engine_details: dict[str, Any] | None
    ) -> float:
        """Calculate confidence in the similarity assessment."""
        if engine_details is None:
            return 0.5

        # Count engines that agree
        agreeing_engines = sum(
            1 for v in engine_details.values() if abs(v - score) < 0.2
        )
        total_engines = len(engine_details)

        if total_engines == 0:
            return 0.5

        base_confidence = agreeing_engines / total_engines
        return min(1.0, base_confidence + 0.3)

    def _find_matched_elements(self, code_a: str, code_b: str) -> list[MatchedElement]:
        """Find matched functions, classes, and blocks."""
        matches = []

        lines_a = code_a.splitlines()
        lines_b = code_b.splitlines()

        # Find function definitions
        func_pattern = re.compile(r"def\s+(\w+)\s*\(")
        for i, line in enumerate(lines_a):
            match = func_pattern.search(line)
            if match:
                func_name = match.group(1)
                # Look for matching function in B
                for j, line_b in enumerate(lines_b):
                    if func_pattern.search(line_b):
                        match_b = func_pattern.search(line_b)
                        if match_b and match_b.group(1) == func_name:
                            matches.append(
                                MatchedElement(
                                    element_type="function",
                                    element_name=func_name,
                                    start_line_a=i + 1,
                                    end_line_a=i + 1,
                                    start_line_b=j + 1,
                                    end_line_b=j + 1,
                                    similarity=0.9,
                                    confidence=0.8,
                                    details=["Function signature match"],
                                )
                            )

        return matches

    def _generate_diff(self, code_a: str, code_b: str) -> list[DiffHunk]:
        """Generate diff hunks between two code submissions."""
        lines_a = code_a.splitlines(keepends=True)
        lines_b = code_b.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        hunks = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    hunks.append(
                        DiffHunk(
                            hunk_type="context",
                            line_number=i + 1,
                            content=lines_a[i].rstrip(),
                        )
                    )
            elif tag == "replace":
                for i in range(i1, i2):
                    hunks.append(
                        DiffHunk(
                            hunk_type="removed",
                            line_number=i + 1,
                            content=lines_a[i].rstrip(),
                            original_content=lines_a[i].rstrip(),
                        )
                    )
                for j in range(j1, j2):
                    hunks.append(
                        DiffHunk(
                            hunk_type="added",
                            line_number=j + 1,
                            content=lines_b[j].rstrip(),
                        )
                    )
            elif tag == "delete":
                for i in range(i1, i2):
                    hunks.append(
                        DiffHunk(
                            hunk_type="removed",
                            line_number=i + 1,
                            content=lines_a[i].rstrip(),
                            original_content=lines_a[i].rstrip(),
                        )
                    )
            elif tag == "insert":
                for j in range(j1, j2):
                    hunks.append(
                        DiffHunk(
                            hunk_type="added",
                            line_number=j + 1,
                            content=lines_b[j].rstrip(),
                        )
                    )

        return hunks

    def _generate_analysis_notes(
        self,
        score: float,
        matched_elements: list[MatchedElement],
        engine_details: dict[str, Any] | None,
    ) -> list[str]:
        """Generate analysis notes for the evidence view."""
        notes = []

        if score >= 0.8:
            notes.append("High similarity detected across multiple analysis engines.")
        elif score >= 0.6:
            notes.append("Moderate similarity detected. Manual review recommended.")
        else:
            notes.append("Low similarity detected. Submissions appear distinct.")

        if matched_elements:
            notes.append(f"Found {len(matched_elements)} matched code elements.")

        if engine_details:
            notes.append(f"Analysis based on {len(engine_details)} similarity engines.")

        return notes

    def _generate_recommendations(
        self, verdict: str, matched_elements: list[MatchedElement]
    ) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if verdict == "HIGH_RISK":
            recommendations.append("Flag for academic integrity review.")
            recommendations.append("Compare with known source materials.")
            if matched_elements:
                recommendations.append(
                    f"Review {len(matched_elements)} matched elements for context."
                )
        elif verdict == "MEDIUM_RISK":
            recommendations.append("Manual review recommended.")
            recommendations.append("Check for external source attribution.")
        elif verdict == "LOW_RISK":
            recommendations.append("No immediate action required.")
        else:
            recommendations.append("Further analysis may be needed.")

        return recommendations


def generate_evidence_view(
    code_a: str,
    code_b: str,
    submission_a_id: str,
    submission_b_id: str,
    similarity_score: float,
    engine_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to generate an evidence view.

    Args:
        code_a: First code submission.
        code_b: Second code submission.
        submission_a_id: ID of first submission.
        submission_b_id: ID of second submission.
        similarity_score: Overall similarity score.
        engine_details: Optional engine-specific details.

    Returns:
        Dict with evidence view data.
    """
    viewer = EvidenceViewer()
    result = viewer.generate_view(
        code_a,
        code_b,
        submission_a_id,
        submission_b_id,
        similarity_score,
        engine_details,
    )
    return result.to_dict()
