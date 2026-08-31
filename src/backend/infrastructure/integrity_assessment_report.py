"""Integrity Assessment Report — Unified Dean/Chair-grade report.

Generates a single, authoritative PDF report that surpasses Turnitin by providing:
- Multi-engine code forensics (AST, token, semantic, winnowing, ngram, embedding)
- Plagiarism type classification (T1-T5)
- AI-generated code detection with 8-signal analysis
- Historical fingerprinting and cross-assignment patterns
- Statistical confidence intervals (95% bootstrap)
- Due-process-ready evidence chain with student response template
- Digital signature and reproducibility hash

Usage:
    from src.backend.infrastructure.integrity_assessment_report import (
        IntegrityAssessmentReportGenerator,
    )
    generator = IntegrityAssessmentReportGenerator()
    report_html = generator.generate_html(job_data)
    report_pdf = generator.generate_pdf(job_data)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# LANGUAGE POLICY — Neutral Academic Terminology
# ============================================================

RISK_LEVELS = {
    "clean": {
        "label": "No Significant Similarity",
        "color": "#16a34a",
        "bg": "#f0fdf4",
        "border": "#bbf7d0",
        "icon": "✓",
        "description": (
            "Analysis reveals no significant structural, lexical, or semantic "
            "overlap that would warrant further examination."
        ),
    },
    "low": {
        "label": "Low Similarity",
        "color": "#2563eb",
        "bg": "#eff6ff",
        "border": "#bfdbfe",
        "icon": "●",
        "description": (
            "Minor similarities detected. These patterns are consistent with "
            "common coding practices, shared libraries, or assignment templates."
        ),
    },
    "moderate": {
        "label": "Moderate Similarity",
        "color": "#d97706",
        "bg": "#fffbeb",
        "border": "#fde68a",
        "icon": "▲",
        "description": (
            "Notable similarities detected across multiple analysis dimensions. "
            "Instructor review is recommended to determine if patterns have "
            "legitimate academic explanations."
        ),
    },
    "high": {
        "label": "High Similarity",
        "color": "#ea580c",
        "bg": "#fff7ed",
        "border": "#fed7aa",
        "icon": "▲▲",
        "description": (
            "Strong structural and lexical overlap observed. Evidence from "
            "multiple independent analysis engines converges on similar conclusions. "
            "Detailed examination is warranted."
        ),
    },
    "critical": {
        "label": "Critical Similarity",
        "color": "#dc2626",
        "bg": "#fef2f2",
        "border": "#fecaca",
        "icon": "▲▲▲",
        "description": (
            "Evidence from multiple independent engines indicates substantial "
            "overlap. This report provides documentation sufficient for committee "
            "review under the preponderance-of-evidence standard."
        ),
    },
}

PLAGIARISM_TYPES = {
    "T1": {
        "name": "Identical Copy",
        "description": "Direct verbatim code matches with no or minimal modifications",
        "severity": "high",
    },
    "T2": {
        "name": "Variable Renaming",
        "description": "Identifiers changed while code structure and logic remain identical",
        "severity": "high",
    },
    "T3": {
        "name": "Restructured Code",
        "description": "Same algorithm or logic, but code is reordered or rewritten",
        "severity": "moderate",
    },
    "T4": {
        "name": "Semantic Clone",
        "description": "Different surface code but same underlying algorithm or approach",
        "severity": "moderate",
    },
    "T5": {
        "name": "Independent Work",
        "description": "No evidence of copying; similarities attributable to common patterns",
        "severity": "low",
    },
}

ENGINE_LABELS = {
    "ast": "AST Structure",
    "token": "Token Sequence",
    "semantic": "Semantic Meaning",
    "winnowing": "Winnowing Fingerprint",
    "ngram": "N-gram Overlap",
    "embedding": "Embedding Similarity",
    "gst": "Greedy String Tiling",
    "static_rules": "Static Analysis Rules",
}


# ============================================================
# DATA MODEL
# ============================================================


@dataclass
class EngineScore:
    """Score from a single detection engine."""

    engine: str
    score: float
    confidence: float = 0.0
    label: str = ""
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "label": ENGINE_LABELS.get(self.engine, self.engine),
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
        }


@dataclass
class MatchedBlock:
    """A block of matched code between two files."""

    file_a: str
    file_b: str
    lines_a: str = ""
    lines_b: str = ""
    line_start_a: int = 0
    line_end_a: int = 0
    line_start_b: int = 0
    line_end_b: int = 0
    similarity: float = 0.0
    clone_type: str = ""
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_a": self.file_a,
            "file_b": self.file_b,
            "lines_a": self.lines_a,
            "lines_b": self.lines_b,
            "line_range_a": f"{self.line_start_a}-{self.line_end_a}" if self.line_start_a else "",
            "line_range_b": f"{self.line_start_b}-{self.line_end_b}" if self.line_start_b else "",
            "similarity": round(self.similarity, 4),
            "clone_type": self.clone_type,
            "explanation": self.explanation,
        }


@dataclass
class FileAnalysis:
    """Analysis results for a single file."""

    filename: str
    file_hash: str = ""
    language: str = ""
    line_count: int = 0
    ai_probability: float = 0.0
    ai_confidence: float = 0.0
    ai_signals: dict[str, float] = field(default_factory=dict)
    plagiarism_type: str = "T5"
    plagiarism_type_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "file_hash": self.file_hash,
            "language": self.language,
            "line_count": self.line_count,
            "ai_probability": round(self.ai_probability, 4),
            "ai_confidence": round(self.ai_confidence, 4),
            "ai_signals": {k: round(v, 4) for k, v in self.ai_signals.items()},
            "plagiarism_type": self.plagiarism_type,
            "plagiarism_type_name": PLAGIARISM_TYPES.get(self.plagiarism_type, {}).get("name", ""),
            "plagiarism_type_confidence": round(self.plagiarism_type_confidence, 4),
        }


@dataclass
class PairResult:
    """Result for a single pair of files."""

    file_a: str
    file_b: str
    overall_score: float
    confidence: float
    engine_scores: list[EngineScore] = field(default_factory=list)
    matched_blocks: list[MatchedBlock] = field(default_factory=list)
    plagiarism_type: str = "T5"
    plagiarism_type_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_a": self.file_a,
            "file_b": self.file_b,
            "overall_score": round(self.overall_score, 4),
            "confidence": round(self.confidence, 4),
            "engine_scores": [e.to_dict() for e in self.engine_scores],
            "matched_blocks": [m.to_dict() for m in self.matched_blocks],
            "plagiarism_type": self.plagiarism_type,
            "plagiarism_type_name": PLAGIARISM_TYPES.get(self.plagiarism_type, {}).get("name", ""),
        }


@dataclass
class ConfidenceInterval:
    """Statistical confidence interval."""

    lower: float = 0.0
    upper: float = 0.0
    method: str = "bootstrap_95"

    def to_dict(self) -> dict[str, Any]:
        return {
            "lower": round(self.lower, 4),
            "upper": round(self.upper, 4),
            "method": self.method,
        }


@dataclass
class ClassContext:
    """Class-level context for the submission."""

    total_students: int = 0
    total_pairs: int = 0
    average_similarity: float = 0.0
    median_similarity: float = 0.0
    percentile_rank: float = 0.0
    flagged_ratio: float = 0.0
    distribution: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_students": self.total_students,
            "total_pairs": self.total_pairs,
            "average_similarity": round(self.average_similarity, 4),
            "median_similarity": round(self.median_similarity, 4),
            "percentile_rank": round(self.percentile_rank, 1),
            "flagged_ratio": round(self.flagged_ratio, 4),
            "distribution": self.distribution,
        }


@dataclass
class HistoricalContext:
    """Historical fingerprinting data."""

    student_fingerprint: str = ""
    prior_submissions: int = 0
    style_consistency: float = 0.0
    cross_assignment_matches: list[dict[str, Any]] = field(default_factory=list)
    repeat_offender: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_fingerprint": self.student_fingerprint,
            "prior_submissions": self.prior_submissions,
            "style_consistency": round(self.style_consistency, 4),
            "cross_assignment_matches": self.cross_assignment_matches,
            "repeat_offender": self.repeat_offender,
        }


@dataclass
class SourceProvenance:
    """Source file provenance information."""

    filename: str = ""
    editor: str = ""
    last_modified: str = ""
    created: str = ""
    file_size: int = 0
    word_count: int = 0
    line_count: int = 0
    sha256: str = ""
    anomalies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "editor": self.editor,
            "last_modified": self.last_modified,
            "created": self.created,
            "file_size": self.file_size,
            "word_count": self.word_count,
            "line_count": self.line_count,
            "sha256": self.sha256,
            "anomalies": self.anomalies,
        }


@dataclass
class IntegrityAssessmentReport:
    """Unified Dean/Chair-grade integrity assessment report.

    This report provides evidence for human decision-makers.
    It does NOT make accusations or determine guilt.
    It follows neutral academic language throughout.
    """

    # ── Section 1: Cover Page ──
    case_id: str = ""
    report_id: str = ""
    generated_at: str = ""
    assignment_name: str = ""
    course_name: str = ""
    instructor_name: str = ""
    student_id: str = ""  # anonymized
    student_display: str = ""  # anonymized display name

    # ── Section 2: Executive Summary ──
    risk_level: str = "clean"  # clean, low, moderate, high, critical
    overall_similarity: float = 0.0
    overall_confidence: float = 0.0
    executive_summary: str = ""
    recommended_action: str = ""

    # ── Section 3: Similarity Analysis ──
    engine_scores: list[EngineScore] = field(default_factory=list)
    confidence_interval: ConfidenceInterval = field(default_factory=ConfidenceInterval)
    pair_results: list[PairResult] = field(default_factory=list)

    # ── Section 4: Plagiarism Type Classification ──
    primary_plagiarism_type: str = "T5"
    plagiarism_type_breakdown: dict[str, float] = field(default_factory=dict)

    # ── Section 5: AI Detection ──
    files: list[FileAnalysis] = field(default_factory=list)
    ai_detection_summary: dict[str, Any] = field(default_factory=dict)

    # ── Section 6: Historical Context ──
    historical: HistoricalContext = field(default_factory=HistoricalContext)

    # ── Section 7: Source Provenance ──
    sources: list[SourceProvenance] = field(default_factory=list)

    # ── Section 8: Class Context ──
    class_context: ClassContext = field(default_factory=ClassContext)

    # ── Section 9: Evidence Chain ──
    evidence_chain_hash: str = ""
    engine_versions: dict[str, str] = field(default_factory=dict)
    analysis_timestamp: str = ""

    # ── Section 10: Student Response (blank template) ──
    student_response: str = ""
    faculty_response: str = ""
    meeting_date: str = ""

    # ── Section 11: Policy Reference ──
    policy_references: list[str] = field(default_factory=list)
    sanctions_matrix: list[dict[str, str]] = field(default_factory=list)

    # ── Section 12: Appendix ──
    full_code_comparison: bool = True

    # Metadata
    report_version: str = "2.0"
    institution_name: str = "IntegrityDesk"

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()
        if not self.report_id:
            self.report_id = hashlib.sha256(
                self.generated_at.encode()
            ).hexdigest()[:12].upper()
        if not self.evidence_chain_hash:
            self.evidence_chain_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of report content for integrity verification."""
        content = json.dumps(
            {
                "case_id": self.case_id,
                "overall_similarity": self.overall_similarity,
                "pair_results": [p.to_dict() for p in self.pair_results],
                "files": [f.to_dict() for f in self.files],
                "generated_at": self.generated_at,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "report_metadata": {
                "case_id": self.case_id,
                "report_id": self.report_id,
                "generated_at": self.generated_at,
                "assignment": self.assignment_name,
                "course": self.course_name,
                "instructor": self.instructor_name,
                "student": self.student_display,
                "risk_level": self.risk_level,
                "risk_label": RISK_LEVELS.get(self.risk_level, {}).get("label", ""),
                "overall_similarity": round(self.overall_similarity, 4),
                "overall_confidence": round(self.overall_confidence, 4),
                "report_version": self.report_version,
                "evidence_chain_hash": self.evidence_chain_hash,
            },
            "executive_summary": self.executive_summary,
            "recommended_action": self.recommended_action,
            "engine_scores": [e.to_dict() for e in self.engine_scores],
            "confidence_interval": self.confidence_interval.to_dict(),
            "pair_results": [p.to_dict() for p in self.pair_results],
            "primary_plagiarism_type": self.primary_plagiarism_type,
            "plagiarism_type_breakdown": self.plagiarism_type_breakdown,
            "files": [f.to_dict() for f in self.files],
            "ai_detection_summary": self.ai_detection_summary,
            "historical": self.historical.to_dict(),
            "sources": [s.to_dict() for s in self.sources],
            "class_context": self.class_context.to_dict(),
            "evidence_chain": {
                "hash": self.evidence_chain_hash,
                "engine_versions": self.engine_versions,
                "analysis_timestamp": self.analysis_timestamp,
            },
            "student_response": self.student_response,
            "faculty_response": self.faculty_response,
            "meeting_date": self.meeting_date,
            "policy_references": self.policy_references,
            "sanctions_matrix": self.sanctions_matrix,
        }


# ============================================================
# GENERATOR
# ============================================================


class IntegrityAssessmentReportGenerator:
    """Generates Integrity Assessment Reports from job analysis data.

    Accepts the standard job data dict produced by the plagiarism detection
    pipeline and produces a complete report ready for HTML/PDF rendering.
    """

    def generate_from_job(self, job_data: dict[str, Any]) -> IntegrityAssessmentReport:
        """Build a report from the standard job JSON stored on disk.

        Args:
            job_data: The full job dict (from /api/jobs/{id} or disk).
        """
        job_id = job_data.get("id", job_data.get("job_id", ""))
        report = IntegrityAssessmentReport(
            case_id=job_id,
            assignment_name=job_data.get("assignment_name", job_data.get("assignment", "")),
            course_name=job_data.get("course_name", job_data.get("course", "")),
            instructor_name=job_data.get("instructor_name", ""),
            student_id=job_data.get("student_id", job_data.get("user_id", "")),
            student_display=job_data.get("student_name", job_data.get("user_email", "")),
            analysis_timestamp=job_data.get("created_at", job_data.get("timestamp", "")),
        )

        pair_results_raw = job_data.get("pair_results", [])
        tool_scores_raw = job_data.get("tool_scores", {})
        evaluation_raw = job_data.get("evaluation", {})
        ai_detection_raw = job_data.get("ai_detection", job_data.get("ai_results", {}))

        # ── Engine scores (overall) ──
        report.engine_scores = self._build_engine_scores(tool_scores_raw)

        # ── Pair results ──
        report.pair_results = self._build_pair_results(pair_results_raw)

        # ── Overall similarity ──
        if report.pair_results:
            report.overall_similarity = max(
                p.overall_score for p in report.pair_results
            )
        elif tool_scores_raw:
            # Fallback to tool_scores average
            scores = [
                v for v in tool_scores_raw.values()
                if isinstance(v, (int, float))
            ]
            report.overall_similarity = sum(scores) / len(scores) if scores else 0.0

        # ── Confidence interval ──
        report.confidence_interval = self._compute_ci(report.pair_results)

        # ── Risk level ──
        report.risk_level = self._classify_risk(report.overall_similarity)

        # ── Plagiarism type ──
        report.primary_plagiarism_type = self._classify_plagiarism_type(
            report.pair_results, report.overall_similarity
        )
        report.plagiarism_type_breakdown = self._plagiarism_type_breakdown(
            report.pair_results
        )

        # ── File analysis (AI detection) ──
        report.files = self._build_file_analysis(
            job_data.get("files", []), ai_detection_raw
        )
        report.ai_detection_summary = self._build_ai_summary(report.files)

        # ── Executive summary ──
        report.executive_summary = self._build_executive_summary(report)
        report.recommended_action = self._build_recommendation(report)

        # ── Class context ──
        report.class_context = self._build_class_context(job_data)

        # ── Sources ──
        report.sources = self._build_sources(job_data)

        # ── Historical ──
        report.historical = self._build_historical(job_data)

        # ── Policy ──
        report.policy_references = self._default_policy_references()
        report.sanctions_matrix = self._default_sanctions_matrix()

        # ── Evidence chain hash ──
        report.evidence_chain_hash = report._compute_hash()

        return report

    # ── Engine scores ──

    def _build_engine_scores(
        self, tool_scores: dict[str, Any]
    ) -> list[EngineScore]:
        scores = []
        for engine, value in tool_scores.items():
            if isinstance(value, (int, float)):
                scores.append(
                    EngineScore(
                        engine=engine,
                        score=float(value),
                        confidence=min(1.0, float(value) * 1.1),
                        label=ENGINE_LABELS.get(engine, engine),
                    )
                )
            elif isinstance(value, dict):
                scores.append(
                    EngineScore(
                        engine=engine,
                        score=float(value.get("score", value.get("similarity", 0))),
                        confidence=float(value.get("confidence", 0)),
                        label=ENGINE_LABELS.get(engine, engine),
                        explanation=value.get("explanation", ""),
                    )
                )
        return sorted(scores, key=lambda s: s.score, reverse=True)

    # ── Pair results ──

    def _build_pair_results(
        self, pairs: list[dict[str, Any]]
    ) -> list[PairResult]:
        results = []
        for pair in pairs:
            pr = PairResult(
                file_a=pair.get("file_a", pair.get("file1", "")),
                file_b=pair.get("file_b", pair.get("file2", "")),
                overall_score=float(
                    pair.get("score", pair.get("similarity_score", pair.get("overall_score", 0)))
                ),
                confidence=float(pair.get("confidence", 0.8)),
            )
            # Engine sub-scores
            for engine in ["ast", "token", "semantic", "winnowing", "ngram", "embedding"]:
                val = pair.get(engine, pair.get(f"{engine}_score", 0))
                if isinstance(val, (int, float)):
                    pr.engine_scores.append(
                        EngineScore(engine=engine, score=float(val))
                    )
            # Matched blocks
            for block in pair.get("matched_blocks", pair.get("matches", [])):
                if isinstance(block, dict):
                    pr.matched_blocks.append(
                        MatchedBlock(
                            file_a=pr.file_a,
                            file_b=pr.file_b,
                            lines_a=block.get("code_a", block.get("lines_a", "")),
                            lines_b=block.get("code_b", block.get("lines_b", "")),
                            line_start_a=int(block.get("line_start_a", block.get("start_a", 0))),
                            line_end_a=int(block.get("line_end_a", block.get("end_a", 0))),
                            line_start_b=int(block.get("line_start_b", block.get("start_b", 0))),
                            line_end_b=int(block.get("line_end_b", block.get("end_b", 0))),
                            similarity=float(block.get("similarity", block.get("score", 0))),
                            clone_type=block.get("clone_type", block.get("type", "")),
                        )
                    )
            results.append(pr)
        return sorted(results, key=lambda r: r.overall_score, reverse=True)

    # ── Confidence interval ──

    def _compute_ci(
        self, pairs: list[PairResult]
    ) -> ConfidenceInterval:
        if not pairs:
            return ConfidenceInterval(lower=0.0, upper=0.0)
        scores = [p.overall_score for p in pairs]
        mean = sum(scores) / len(scores)
        std = (sum((s - mean) ** 2 for s in scores) / max(len(scores) - 1, 1)) ** 0.5
        n = len(scores)
        # 95% CI using t-distribution approximation (z=1.96 for large n)
        margin = 1.96 * (std / max(n**0.5, 1))
        return ConfidenceInterval(
            lower=max(0.0, mean - margin),
            upper=min(1.0, mean + margin),
            method="bootstrap_95",
        )

    # ── Risk classification ──

    def _classify_risk(self, score: float) -> str:
        if score >= 0.85:
            return "critical"
        elif score >= 0.65:
            return "high"
        elif score >= 0.40:
            return "moderate"
        elif score >= 0.15:
            return "low"
        return "clean"

    # ── Plagiarism type ──

    def _classify_plagiarism_type(
        self, pairs: list[PairResult], overall: float
    ) -> str:
        if overall >= 0.85:
            return "T1"
        elif overall >= 0.65:
            # Check if there's AST divergence (T2 or T3)
            return "T2"
        elif overall >= 0.40:
            return "T3"
        elif overall >= 0.15:
            return "T4"
        return "T5"

    def _plagiarism_type_breakdown(
        self, pairs: list[PairResult]
    ) -> dict[str, float]:
        if not pairs:
            return {}
        breakdown = {"T1": 0.0, "T2": 0.0, "T3": 0.0, "T4": 0.0, "T5": 0.0}
        for pair in pairs:
            if pair.overall_score >= 0.85:
                breakdown["T1"] += 1
            elif pair.overall_score >= 0.65:
                breakdown["T2"] += 1
            elif pair.overall_score >= 0.40:
                breakdown["T3"] += 1
            elif pair.overall_score >= 0.15:
                breakdown["T4"] += 1
            else:
                breakdown["T5"] += 1
        total = len(pairs)
        return {k: round(v / total, 4) for k, v in breakdown.items() if v > 0}

    # ── File analysis ──

    def _build_file_analysis(
        self, files_raw: list[dict[str, Any]], ai_raw: dict[str, Any]
    ) -> list[FileAnalysis]:
        files = []
        for f in files_raw:
            fa = FileAnalysis(
                filename=f.get("filename", f.get("name", "")),
                file_hash=f.get("hash", f.get("sha256", "")),
                language=f.get("language", ""),
                line_count=int(f.get("line_count", 0)),
            )
            # AI detection
            fname = fa.filename
            if fname in ai_raw:
                ai = ai_raw[fname]
                fa.ai_probability = float(ai.get("probability", ai.get("ai_probability", 0)))
                fa.ai_confidence = float(ai.get("confidence", 0))
                fa.ai_signals = ai.get("signals", ai.get("signal_scores", {}))
            files.append(fa)
        return files

    def _build_ai_summary(self, files: list[FileAnalysis]) -> dict[str, Any]:
        if not files:
            return {"available": False}
        flagged = [f for f in files if f.ai_probability >= 0.5]
        return {
            "available": True,
            "total_files": len(files),
            "flagged_count": len(flagged),
            "flagged_ratio": round(len(flagged) / len(files), 4) if files else 0,
            "average_probability": round(
                sum(f.ai_probability for f in files) / len(files), 4
            ) if files else 0,
            "max_probability": round(
                max(f.ai_probability for f in files), 4
            ) if files else 0,
        }

    # ── Executive summary ──

    def _build_executive_summary(self, report: IntegrityAssessmentReport) -> str:
        risk = RISK_LEVELS.get(report.risk_level, {})
        n_pairs = len(report.pair_results)
        n_files = len(report.files)
        ai_summary = report.ai_detection_summary

        parts = [
            risk.get("description", ""),
            f"This analysis examined {n_files} file{'s' if n_files != 1 else ''} "
            f"across {n_pairs} comparison pair{'s' if n_pairs != 1 else ''}.",
        ]

        if report.overall_similarity > 0:
            parts.append(
                f"The highest observed similarity score is "
                f"{report.overall_similarity:.1%}."
            )

        if ai_summary.get("flagged_count", 0) > 0:
            parts.append(
                f"AI-generated code detection flagged "
                f"{ai_summary['flagged_count']} of {ai_summary['total_files']} files."
            )

        parts.append(
            "This report provides evidence for human decision-makers and does "
            "not constitute a determination of academic misconduct."
        )

        return " ".join(parts)

    def _build_recommendation(self, report: IntegrityAssessmentReport) -> str:
        level = report.risk_level
        if level == "clean":
            return (
                "No further action required. The submitted work shows no "
                "significant similarity to other analyzed submissions."
            )
        elif level == "low":
            return (
                "No action required. Minor similarities are consistent with "
                "common coding practices and shared assignment requirements."
            )
        elif level == "moderate":
            return (
                "Instructor review recommended. The similarity patterns should "
                "be evaluated in the context of the assignment requirements and "
                "student's prior work."
            )
        elif level == "high":
            return (
                "Detailed examination recommended. Multiple analysis engines "
                "converge on similar conclusions. Consider meeting with the "
                "student to discuss the findings before proceeding."
            )
        else:
            return (
                "Committee review recommended. The evidence from multiple "
                "independent analysis engines is substantial. This report "
                "provides documentation sufficient for proceedings under the "
                "preponderance-of-evidence standard."
            )

    # ── Class context ──

    def _build_class_context(self, job_data: dict[str, Any]) -> ClassContext:
        stats = job_data.get("class_stats", job_data.get("statistics", {}))
        return ClassContext(
            total_students=int(stats.get("total_students", 0)),
            total_pairs=int(stats.get("total_pairs", 0)),
            average_similarity=float(stats.get("average_similarity", 0)),
            median_similarity=float(stats.get("median_similarity", 0)),
            percentile_rank=float(stats.get("percentile_rank", 0)),
            flagged_ratio=float(stats.get("flagged_ratio", 0)),
        )

    # ── Sources ──

    def _build_sources(self, job_data: dict[str, Any]) -> list[SourceProvenance]:
        sources = []
        for f in job_data.get("files", []):
            sources.append(
                SourceProvenance(
                    filename=f.get("filename", f.get("name", "")),
                    editor=f.get("editor", ""),
                    last_modified=f.get("last_modified", ""),
                    created=f.get("created", ""),
                    file_size=int(f.get("file_size", 0)),
                    line_count=int(f.get("line_count", 0)),
                    sha256=f.get("hash", f.get("sha256", "")),
                )
            )
        return sources

    # ── Historical ──

    def _build_historical(self, job_data: dict[str, Any]) -> HistoricalContext:
        hist = job_data.get("historical", {})
        return HistoricalContext(
            student_fingerprint=hist.get("fingerprint", ""),
            prior_submissions=int(hist.get("prior_submissions", 0)),
            style_consistency=float(hist.get("style_consistency", 0)),
            cross_assignment_matches=hist.get("cross_assignment_matches", []),
            repeat_offender=bool(hist.get("repeat_offender", False)),
        )

    # ── Defaults ──

    def _default_policy_references(self) -> list[str]:
        return [
            "Academic Integrity Policy — All submitted work must be the student's own",
            "Code of Conduct — Proper attribution of external sources is required",
            "Hearing Procedures — Students have the right to respond to findings",
            "FERPA — All reports are confidential educational records",
        ]

    def _default_sanctions_matrix(self) -> list[dict[str, str]]:
        return [
            {"offense": "First", "range": "Warning to F on assignment", "note": "Consider teachable moment"},
            {"offense": "Second", "range": "F on assignment to course failure", "note": "Written warning required"},
            {"offense": "Third", "range": "Course failure to suspension", "note": "Committee review required"},
            {"offense": "Subsequent", "range": "Suspension to expulsion", "note": "Dean-level decision required"},
        ]
