"""Forensic reporting tier for case-level drilldown and analysis.

Generates detailed forensic reports for investigating specific code pairs,
including similarity breakdowns, technique analysis, and causal attribution.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json


class SimilarityTechnique(Enum):
    """Code similarity techniques detected."""
    TOKEN_MATCH = "token_match"
    AST_MATCH = "ast_match"
    STRUCTURAL_MATCH = "structural_match"
    SEMANTIC_MATCH = "semantic_match"
    RENAMING = "renaming"
    REORDERING = "reordering"
    INSERTION = "insertion"
    DELETION = "deletion"


@dataclass
class SimilarityRegion:
    """A region of similarity between two code segments."""
    region_id: str
    source_start_line: int
    source_end_line: int
    target_start_line: int
    target_end_line: int
    similarity_score: float
    technique: SimilarityTechnique
    source_snippet: str
    target_snippet: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "region_id": self.region_id,
            "source_start_line": self.source_start_line,
            "source_end_line": self.source_end_line,
            "target_start_line": self.target_start_line,
            "target_end_line": self.target_end_line,
            "similarity_score": self.similarity_score,
            "technique": self.technique.value,
            "source_snippet": self.source_snippet,
            "target_snippet": self.target_snippet,
            "explanation": self.explanation
        }


@dataclass
class AttributionEvidence:
    """Evidence for attribution decision."""
    evidence_type: str
    confidence: float
    description: str
    location: Optional[Tuple[int, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "evidence_type": self.evidence_type,
            "confidence": self.confidence,
            "description": self.description,
            "location": list(self.location) if self.location else None
        }


@dataclass
class CausalAttribution:
    """Causal attribution for similarity."""
    source: str  # "original", "derivative", "independent"
    confidence: float
    evidence: List[AttributionEvidence]
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "reasoning": self.reasoning
        }


@dataclass
class CodePairAnalysis:
    """Detailed analysis of a single code pair."""
    pair_id: str
    source_file: str
    target_file: str
    overall_similarity: float
    clone_type: str
    similarity_regions: List[SimilarityRegion]
    attribution: CausalAttribution
    technique_summary: Dict[str, float]
    risk_level: str  # "low", "medium", "high", "critical"
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pair_id": self.pair_id,
            "source_file": self.source_file,
            "target_file": self.target_file,
            "overall_similarity": self.overall_similarity,
            "clone_type": self.clone_type,
            "similarity_regions": [r.to_dict() for r in self.similarity_regions],
            "attribution": self.attribution.to_dict(),
            "technique_summary": self.technique_summary,
            "risk_level": self.risk_level,
            "recommendation": self.recommendation
        }


class ForensicReport:
    """Case-level forensic report for detailed investigation.

    Provides drilldown analysis of specific code pairs, including
    similarity breakdowns, technique detection, and causal attribution.
    """

    def __init__(
        self,
        case_id: str,
        timestamp: str,
        investigator: str,
        code_pairs: List[CodePairAnalysis],
        summary: Dict[str, Any],
        methodology: str,
        limitations: Optional[List[str]] = None
    ):
        """Initialize forensic report.

        Args:
            case_id: Unique case identifier
            timestamp: Report generation timestamp
            investigator: Name/ID of investigator
            code_pairs: Analysis of each code pair
            summary: Executive summary
            methodology: Investigation methodology
            limitations: Known limitations
        """
        self.case_id = case_id
        self.timestamp = timestamp
        self.investigator = investigator
        self.code_pairs = code_pairs
        self.summary = summary
        self.methodology = methodology
        self.limitations = limitations or []

    def get_pair_by_id(self, pair_id: str) -> Optional[CodePairAnalysis]:
        """Get code pair analysis by ID.

        Args:
            pair_id: Pair identifier

        Returns:
            Code pair analysis if found, None otherwise
        """
        for pair in self.code_pairs:
            if pair.pair_id == pair_id:
                return pair
        return None

    def get_critical_pairs(self) -> List[CodePairAnalysis]:
        """Get only critical risk pairs.

        Returns:
            List of critical risk code pairs
        """
        return [p for p in self.code_pairs if p.risk_level == "critical"]

    def get_high_risk_pairs(self) -> List[CodePairAnalysis]:
        """Get high and critical risk pairs.

        Returns:
            List of high/critical risk code pairs
        """
        return [p for p in self.code_pairs if p.risk_level in ("high", "critical")]

    def generate_narrative(self) -> str:
        """Generate narrative summary of findings.

        Returns:
            Narrative text describing the investigation
        """
        total_pairs = len(self.code_pairs)
        critical_count = len(self.get_critical_pairs())
        high_count = len(self.get_high_risk_pairs())

        narrative = f"""FORENSIC ANALYSIS REPORT
Case ID: {self.case_id}
Investigator: {self.investigator}
Date: {self.timestamp}

EXECUTIVE SUMMARY
=================
Total code pairs analyzed: {total_pairs}
Critical risk pairs: {critical_count}
High risk pairs: {high_count}

METHODOLOGY
===========
{self.methodology}

KEY FINDINGS
============
"""

        for i, pair in enumerate(self.code_pairs[:5], 1):
            narrative += f"""
{i}. {pair.source_file} vs {pair.target_file}
   Similarity: {pair.overall_similarity:.2%}
   Clone Type: {pair.clone_type}
   Risk Level: {pair.risk_level}
   Attribution: {pair.attribution.source} (confidence: {pair.attribution.confidence:.2%})
   Recommendation: {pair.recommendation}
"""

        if self.limitations:
            narrative += f"""
LIMITATIONS
===========
{chr(10).join('- ' + lim for lim in self.limitations)}
"""

        return narrative

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.

        Returns:
            Dictionary representation of the report
        """
        return {
            "case_id": self.case_id,
            "timestamp": self.timestamp,
            "investigator": self.investigator,
            "code_pairs": [p.to_dict() for p in self.code_pairs],
            "summary": self.summary,
            "methodology": self.methodology,
            "limitations": self.limitations
        }

    def to_json(self, indent: int = 2) -> str:
        """Generate JSON format.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForensicReport':
        """Create report from dictionary.

        Args:
            data: Dictionary containing report data

        Returns:
            ForensicReport instance
        """
        code_pairs = []
        for pair_data in data["code_pairs"]:
            regions = [
                SimilarityRegion(
                    region_id=r["region_id"],
                    source_start_line=r["source_start_line"],
                    source_end_line=r["source_end_line"],
                    target_start_line=r["target_start_line"],
                    target_end_line=r["target_end_line"],
                    similarity_score=r["similarity_score"],
                    technique=SimilarityTechnique(r["technique"]),
                    source_snippet=r["source_snippet"],
                    target_snippet=r["target_snippet"],
                    explanation=r["explanation"]
                )
                for r in pair_data["similarity_regions"]
            ]

            evidence = [
                AttributionEvidence(
                    evidence_type=e["evidence_type"],
                    confidence=e["confidence"],
                    description=e["description"],
                    location=tuple(e["location"]) if e.get("location") else None
                )
                for e in pair_data["attribution"]["evidence"]
            ]

            attribution = CausalAttribution(
                source=pair_data["attribution"]["source"],
                confidence=pair_data["attribution"]["confidence"],
                evidence=evidence,
                reasoning=pair_data["attribution"]["reasoning"]
            )

            code_pairs.append(CodePairAnalysis(
                pair_id=pair_data["pair_id"],
                source_file=pair_data["source_file"],
                target_file=pair_data["target_file"],
                overall_similarity=pair_data["overall_similarity"],
                clone_type=pair_data["clone_type"],
                similarity_regions=regions,
                attribution=attribution,
                technique_summary=pair_data["technique_summary"],
                risk_level=pair_data["risk_level"],
                recommendation=pair_data["recommendation"]
            ))

        return cls(
            case_id=data["case_id"],
            timestamp=data["timestamp"],
            investigator=data["investigator"],
            code_pairs=code_pairs,
            summary=data["summary"],
            methodology=data["methodology"],
            limitations=data.get("limitations", [])
        )