"""Dean-Grade Academic Integrity Evidence Report Generator.

This module generates structured evidence reports suitable for:
- Academic integrity hearings
- Department reviews
- Dean-level decisions
- Committee deliberations

The report follows strict language policies:
- NEVER accuses students
- Uses neutral academic terminology
- Provides evidence, not verdicts
- Is auditable and reproducible
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ============================================================
# LANGUAGE POLICY - Academic Neutral Terminology
# ============================================================

VERDICT_LABELS = {
    "CLEAN": "No significant similarity detected",
    "REVIEW_REQUIRED": "Evidence suggests examination recommended",
    "STRONG_SIMILARITY_OBSERVED": "Strong structural and lexical overlap observed",
}

# Dean-friendly terminology mapping
DEAN_TERMINOLOGY = {
    "structural": "Code Structure Alignment",
    "lexical": "Sequence Overlap",
    "semantic": "Conceptual Content Match",
    "control_flow": "Logic Flow Similarity",
    "historical": "Work Pattern Consistency",
    "cluster": "Peer Group Analysis",
    "divergence": "Implementation Differences",
    "ai_indicators": "Generative AI Signals",
}

EVIDENCE_DESCRIPTIONS = {
    "structural": "Structural analysis reveals matching code organization patterns",
    "lexical": "Lexical analysis shows overlapping code sequences",
    "semantic": "Semantic analysis indicates conceptual alignment",
    "control_flow": "Control flow analysis reveals similar program execution patterns",
    "historical": "Historical analysis shows consistency with past work patterns",
    "cluster": "Cluster analysis groups this submission with similar works",
    "divergence": "Divergence analysis shows differences in implementation details",
    "ai_indicators": "AI detection indicators (non-decisive)",
}


@dataclass
class EvidenceItem:
    """Single evidence item with explanation."""

    evidence_type: str
    description: str
    value: float
    confidence: str  # HIGH, MEDIUM, LOW
    explanation: str
    matched_spans: List[Dict[str, Any]] = field(default_factory=list)
    source_references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "description": self.description,
            "value": round(self.value, 3),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "matched_spans": self.matched_spans,
            "source_references": self.source_references,
        }


@dataclass
class DeanGradeReport:
    """Dean-grade academic integrity evidence report.

    This report provides evidence for human decision-makers.
    It does NOT make accusations or determine guilt.
    """

    # Case identifiers
    case_id: str
    course_id: str
    assignment_id: str
    submission_a_id: str
    submission_b_id: str

    # Final classification (evidence-based, not accusatory)
    final_verdict: str  # CLEAN, REVIEW_REQUIRED, STRONG_SIMILARITY_OBSERVED

    # Evidence sections
    structural_evidence: List[EvidenceItem] = field(default_factory=list)
    lexical_evidence: List[EvidenceItem] = field(default_factory=list)
    semantic_evidence: List[EvidenceItem] = field(default_factory=list)
    control_flow_evidence: List[EvidenceItem] = field(default_factory=list)
    historical_evidence: List[EvidenceItem] = field(default_factory=list)
    cluster_evidence: List[EvidenceItem] = field(default_factory=list)
    divergence_evidence: List[EvidenceItem] = field(default_factory=list)
    ai_indicators: List[EvidenceItem] = field(default_factory=list)

    # Reviewer notes
    reviewer_notes: List[str] = field(default_factory=list)

    # Dean-specific fields
    executive_summary: Optional[Dict[str, Any]] = field(default_factory=dict)
    policy_references: List[str] = field(default_factory=list)
    precedent_comparison: List[Dict[str, Any]] = field(default_factory=list)
    student_context: Optional[Dict[str, Any]] = field(default_factory=dict)
    timeline: List[Dict[str, str]] = field(default_factory=list)
    confidence_interval: Optional[Dict[str, float]] = field(default_factory=dict)
    recommendation: Optional[Dict[str, Any]] = field(default_factory=dict)

    # Metadata
    generated_at: str = ""
    report_version: str = "1.0"
    evidence_bundle_hash: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "report_metadata": {
                "case_id": self.case_id,
                "course_id": self.course_id,
                "assignment_id": self.assignment_id,
                "submission_a_id": self.submission_a_id,
                "submission_b_id": self.submission_b_id,
                "final_verdict": self.final_verdict,
                "verdict_label": VERDICT_LABELS.get(self.final_verdict, ""),
                "generated_at": self.generated_at,
                "report_version": self.report_version,
            },
            "executive_summary": self._build_executive_summary(),
            "evidence_overview": self._build_evidence_overview(),
            "structural_evidence": self._items_to_dict(self.structural_evidence),
            "lexical_evidence": self._items_to_dict(self.lexical_evidence),
            "semantic_evidence": self._items_to_dict(self.semantic_evidence),
            "control_flow_evidence": self._items_to_dict(self.control_flow_evidence),
            "historical_evidence": self._items_to_dict(self.historical_evidence),
            "cluster_evidence": self._items_to_dict(self.cluster_evidence),
            "divergence_evidence": self._items_to_dict(self.divergence_evidence),
            "ai_indicators": self._items_to_dict(self.ai_indicators),
            "reviewer_notes": self.reviewer_notes,
            # Dean-specific sections
            "policy_references": self.policy_references,
            "precedent_comparison": self.precedent_comparison,
            "student_context": self.student_context,
            "timeline": self.timeline,
            "confidence_interval": self.confidence_interval,
            "recommendation": self.recommendation,
        }

    def _items_to_dict(self, items: List[EvidenceItem]) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in items]

    def _build_executive_summary(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "submissions_compared": f"{self.submission_a_id} vs {self.submission_b_id}",
            "final_classification": self.final_verdict,
            "classification_explanation": VERDICT_LABELS.get(self.final_verdict, ""),
            "summary_paragraph": self._generate_summary_paragraph(),
        }

    def _generate_summary_paragraph(self) -> str:
        """Generate neutral summary paragraph."""
        if self.final_verdict == "CLEAN":
            return (
                "Analysis of the two submissions shows no significant structural, "
                "lexical, or semantic overlap that would suggest shared work."
            )
        elif self.final_verdict == "REVIEW_REQUIRED":
            return (
                "Analysis reveals some similarities between submissions that merit "
                "instructor review to determine if the patterns have academic explanation."
            )
        else:
            return (
                "Analysis reveals strong structural and lexical overlap between "
                "submissions. This evidence warrants detailed examination by the instructor."
            )

    def _build_evidence_overview(self) -> Dict[str, Any]:
        """Build compact evidence overview table."""
        return {
            "structural_similarity": self._get_top_evidence(self.structural_evidence),
            "lexical_similarity": self._get_top_evidence(self.lexical_evidence),
            "semantic_similarity": self._get_top_evidence(self.semantic_evidence),
            "control_flow_similarity": self._get_top_evidence(
                self.control_flow_evidence
            ),
            "structural_divergence": self._get_top_evidence(self.divergence_evidence),
        }

    def _get_top_evidence(self, items: List[EvidenceItem]) -> Optional[Dict[str, Any]]:
        if not items:
            return None
        top = items[0]
        return {
            "description": top.description,
            "value": round(top.value, 3),
            "confidence": top.confidence,
        }


class DeanReportGenerator:
    """Generates dean-grade evidence reports from detection results."""

    def __init__(self):
        self.evidence_weights = {
            "structural": 0.35,
            "lexical": 0.25,
            "semantic": 0.15,
            "control_flow": 0.20,
            "divergence": 0.05,
        }

    def generate(
        self,
        case_id: str,
        course_id: str,
        assignment_id: str,
        submission_a_id: str,
        submission_b_id: str,
        evidence_bundle: Dict[str, Any],
        reviewer_notes: Optional[List[str]] = None,
    ) -> DeanGradeReport:
        """Generate a dean-grade report from evidence bundle.

        Args:
            case_id: Unique case identifier
            course_id: Course identifier
            assignment_id: Assignment identifier
            submission_a_id: First submission ID
            submission_b_id: Second submission ID
            evidence_bundle: Structured evidence from detection engines
            reviewer_notes: Optional instructor notes

        Returns:
            DeanGradeReport ready for review
        """
        # Extract evidence items
        structural = self._extract_structural_evidence(evidence_bundle)
        lexical = self._extract_lexical_evidence(evidence_bundle)
        semantic = self._extract_semantic_evidence(evidence_bundle)
        control_flow = self._extract_control_flow_evidence(evidence_bundle)
        historical = self._extract_historical_evidence(evidence_bundle)
        cluster = self._extract_cluster_evidence(evidence_bundle)
        divergence = self._extract_divergence_evidence(evidence_bundle)
        ai_indicators = self._extract_ai_indicators(evidence_bundle)

        # Determine verdict based on evidence
        verdict = self._determine_verdict(
            structural, lexical, semantic, control_flow, divergence
        )

        return DeanGradeReport(
            case_id=case_id,
            course_id=course_id,
            assignment_id=assignment_id,
            submission_a_id=submission_a_id,
            submission_b_id=submission_b_id,
            final_verdict=verdict,
            structural_evidence=structural,
            lexical_evidence=lexical,
            semantic_evidence=semantic,
            control_flow_evidence=control_flow,
            historical_evidence=historical,
            cluster_evidence=cluster,
            divergence_evidence=divergence,
            ai_indicators=ai_indicators,
            reviewer_notes=reviewer_notes or [],
            evidence_bundle_hash=self._compute_hash(evidence_bundle),
        )

    def _extract_structural_evidence(
        self, bundle: Dict[str, Any]
    ) -> List[EvidenceItem]:
        """Extract structural evidence from bundle."""
        items = []
        shape = bundle.get("shape_similarity", 0.0)
        semantic_nodes = bundle.get("semantic_node_similarity", 0.0)
        divergence_score = bundle.get("divergence_score", 0.0)

        if shape > 0.1:
            items.append(
                EvidenceItem(
                    evidence_type="structural",
                    description="AST structure similarity",
                    value=shape,
                    confidence=(
                        "HIGH" if shape > 0.7 else "MEDIUM" if shape > 0.4 else "LOW"
                    ),
                    explanation="Code organization patterns show alignment",
                )
            )

        if semantic_nodes > 0.1:
            items.append(
                EvidenceItem(
                    evidence_type="semantic",
                    description="Semantic node similarity",
                    value=semantic_nodes,
                    confidence=(
                        "HIGH"
                        if semantic_nodes > 0.7
                        else "MEDIUM" if semantic_nodes > 0.4 else "LOW"
                    ),
                    explanation="Function logic and operations show conceptual alignment",
                )
            )

        # Add divergence evidence if present
        if divergence_score > 0.0:
            items.append(
                EvidenceItem(
                    evidence_type="divergence",
                    description="Structural divergence",
                    value=divergence_score,
                    confidence="HIGH",
                    explanation="Implementation differences reduce similarity concerns",
                )
            )

        return items

    def _extract_lexical_evidence(self, bundle: Dict[str, Any]) -> List[EvidenceItem]:
        """Extract lexical evidence from bundle."""
        items = []

        for key in ["ngram", "winnowing", "fingerprint"]:
            value = bundle.get(key, 0.0)
            if value > 0.1:
                items.append(
                    EvidenceItem(
                        evidence_type="lexical",
                        description=f"{key.replace('_', ' ').title()} similarity",
                        value=value,
                        confidence=(
                            "HIGH"
                            if value > 0.8
                            else "MEDIUM" if value > 0.5 else "LOW"
                        ),
                        explanation="Code sequences show overlapping patterns",
                    )
                )

        return items

    def _extract_semantic_evidence(self, bundle: Dict[str, Any]) -> List[EvidenceItem]:
        """Extract semantic evidence from bundle."""
        items = []
        embedding = bundle.get("embedding_similarity", 0.0)

        if embedding > 0.1:
            items.append(
                EvidenceItem(
                    evidence_type="semantic",
                    description="Embedding-based semantic similarity",
                    value=embedding,
                    confidence="LOW",  # Embeddings are weak evidence alone
                    explanation=(
                        "Semantic analysis indicates conceptual alignment. "
                        "Note: This is supplementary evidence only."
                    ),
                )
            )

        return items

    def _extract_control_flow_evidence(
        self, bundle: Dict[str, Any]
    ) -> List[EvidenceItem]:
        """Extract control flow evidence from bundle."""
        items = []
        cf_similarity = bundle.get("control_flow_similarity", 0.0)

        if cf_similarity > 0.1:
            items.append(
                EvidenceItem(
                    evidence_type="control_flow",
                    description="Control flow structure similarity",
                    value=cf_similarity,
                    confidence=(
                        "HIGH"
                        if cf_similarity > 0.7
                        else "MEDIUM" if cf_similarity > 0.4 else "LOW"
                    ),
                    explanation="Program execution patterns show alignment",
                )
            )

        return items

    def _extract_historical_evidence(
        self, bundle: Dict[str, Any]
    ) -> List[EvidenceItem]:
        """Extract historical evidence from bundle."""
        items = []
        history = bundle.get("historical_evidence", {})

        if history:
            consistency = history.get("style_consistency", 0.0)
            if consistency > 0.0:
                items.append(
                    EvidenceItem(
                        evidence_type="historical",
                        description="Style consistency analysis",
                        value=consistency,
                        confidence="MEDIUM",
                        explanation="Submission aligns with student's historical patterns",
                    )
                )

        return items

    def _extract_cluster_evidence(self, bundle: Dict[str, Any]) -> List[EvidenceItem]:
        """Extract cluster evidence from bundle."""
        items = []
        cluster = bundle.get("cluster_evidence", {})

        if cluster:
            density = cluster.get("cluster_density", 0.0)
            if density > 0.0:
                items.append(
                    EvidenceItem(
                        evidence_type="cluster",
                        description="Similarity cluster membership",
                        value=density,
                        confidence="LOW",
                        explanation=(
                            "Submission groups with similar works. "
                            "Note: Cluster membership alone does not imply misconduct."
                        ),
                    )
                )

        return items

    def _extract_divergence_evidence(
        self, bundle: Dict[str, Any]
    ) -> List[EvidenceItem]:
        """Extract divergence evidence from bundle."""
        items = []
        divergence = bundle.get("divergence_score", 0.0)

        if divergence > 0.0:
            items.append(
                EvidenceItem(
                    evidence_type="divergence",
                    description="Structural divergence score",
                    value=divergence,
                    confidence=(
                        "HIGH"
                        if divergence > 0.7
                        else "MEDIUM" if divergence > 0.4 else "LOW"
                    ),
                    explanation="Implementation differences reduce similarity concerns",
                )
            )

        return items

    def _extract_ai_indicators(self, bundle: Dict[str, Any]) -> List[EvidenceItem]:
        """Extract AI indicators (non-decisive) from bundle."""
        items = []
        ai = bundle.get("ai_indicators", {})

        if ai:
            perplexity = ai.get("perplexity_score", 0.0)
            if perplexity > 0.0:
                items.append(
                    EvidenceItem(
                        evidence_type="ai_indicators",
                        description="AI detection indicators",
                        value=perplexity,
                        confidence="LOW",
                        explanation=(
                            "AI detection signals (non-decisive). "
                            "These indicators alone cannot determine academic misconduct."
                        ),
                    )
                )

        return items

    def _determine_verdict(
        self,
        structural: List[EvidenceItem],
        lexical: List[EvidenceItem],
        semantic: List[EvidenceItem],
        control_flow: List[EvidenceItem],
        divergence: List[EvidenceItem],
    ) -> str:
        """Determine final verdict based on evidence (not accusatory)."""
        # Calculate weighted evidence strength
        struct_score = max((e.value for e in structural), default=0.0)
        lexical_score = max((e.value for e in lexical), default=0.0)
        semantic_score = max((e.value for e in semantic), default=0.0)
        cf_score = max((e.value for e in control_flow), default=0.0)
        div_score = max((e.value for e in divergence), default=0.0)

        # Weighted combination
        evidence_strength = (
            struct_score * 0.35
            + lexical_score * 0.25
            + semantic_score * 0.15
            + cf_score * 0.20
            + (1.0 - div_score) * 0.05  # Lower divergence = stronger evidence
        )

        # Determine verdict
        if evidence_strength < 0.4:
            return "CLEAN"
        elif evidence_strength < 0.7:
            return "REVIEW_REQUIRED"
        else:
            return "STRONG_SIMILARITY_OBSERVED"

    def _compute_hash(self, bundle: Dict[str, Any]) -> str:
        """Compute hash for evidence bundle reproducibility."""
        import hashlib

        content = json.dumps(bundle, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


def generate_dean_report(
    case_id: str,
    course_id: str,
    assignment_id: str,
    submission_a_id: str,
    submission_b_id: str,
    evidence_bundle: Dict[str, Any],
    reviewer_notes: Optional[List[str]] = None,
) -> DeanGradeReport:
    """Convenience function to generate a dean-grade report.

    This is the main entry point for report generation.
    """
    generator = DeanReportGenerator()
    return generator.generate(
        case_id=case_id,
        course_id=course_id,
        assignment_id=assignment_id,
        submission_a_id=submission_a_id,
        submission_b_id=submission_b_id,
        evidence_bundle=evidence_bundle,
        reviewer_notes=reviewer_notes,
    )
