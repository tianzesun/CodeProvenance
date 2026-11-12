"""Integrity Assessment Report — Unified Dean/Chair-grade report.

Generates one class-level evidence report (HTML/PDF) for human review:
- The highest-scoring pair and what raised its score (the learned model's terms)
- The matched code blocks, with the clone type the code matcher assigned each one
- AI-generated code detection with 8-signal analysis
- Class context: median pair score and the share of pairs in the high band
- An evidence chain (SHA-256 of the report's results) and a student response template

It covers a whole check, not one student, and it never decides misconduct.

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
            "Strong overlap between at least one pair of submissions. Read the "
            "matched code and what raised the score before drawing any conclusion."
        ),
    },
    "critical": {
        "label": "Critical Similarity",
        "color": "#dc2626",
        "bg": "#fef2f2",
        "border": "#fecaca",
        "icon": "▲▲▲",
        "description": (
            "Very strong overlap, often near-verbatim, between at least one pair of "
            "submissions. A score is a reason to look closely, not proof: starter "
            "code and common solutions can also score high."
        ),
    },
}

#: The code matcher's per-block clone types (``CloneType`` values) and the T-label
#: each one is reported under. A pair's type comes only from its matched blocks.
BLOCK_TYPE_TO_T = {"Type 1": "T1", "Type 2": "T2", "Type 3": "T3", "Type 4": "T4"}

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

#: The results page's names for the signals the learned model scores.
ENGINE_LABELS = {
    "winnowing": "Chunk hash match",
    "coverage": "Matched-line coverage",
    "ngram": "Token n-gram match",
    "logic_flow": "Logic flow",
    "embedding": "Semantic meaning",
    "fingerprint": "Token fingerprint",
    "ast": "Structure (AST)",
}

#: Band edges, matching the product's risk levels (``_risk_level``) and review bands.
CRITICAL_MIN, HIGH_MIN, MODERATE_MIN, LOW_MIN = 0.85, 0.65, 0.35, 0.15


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
    engine_scores: list[EngineScore] = field(default_factory=list)
    matched_blocks: list[MatchedBlock] = field(default_factory=list)
    #: The learned model's per-engine terms for this pair's score (empty for old jobs).
    contributions: dict[str, float] = field(default_factory=dict)
    #: From the matched blocks only; empty when the pair has none.
    plagiarism_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_a": self.file_a,
            "file_b": self.file_b,
            "overall_score": round(self.overall_score, 4),
            "contributions": {k: round(v, 4) for k, v in self.contributions.items()},
            "engine_scores": [e.to_dict() for e in self.engine_scores],
            "matched_blocks": [m.to_dict() for m in self.matched_blocks],
            "plagiarism_type": self.plagiarism_type,
            "plagiarism_type_name": PLAGIARISM_TYPES.get(self.plagiarism_type, {}).get("name", ""),
        }


@dataclass
class ClassContext:
    """Class-level context for the submission."""

    total_submissions: int = 0
    total_pairs: int = 0
    average_similarity: float = 0.0
    median_similarity: float = 0.0
    #: Share of pairs at or above the high band.
    flagged_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_submissions": self.total_submissions,
            "total_pairs": self.total_pairs,
            "average_similarity": round(self.average_similarity, 4),
            "median_similarity": round(self.median_similarity, 4),
            "flagged_ratio": round(self.flagged_ratio, 4),
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
    language: str = ""
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
            "language": self.language,
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
    #: What raised the highest-scoring pair's score.
    engine_scores: list[EngineScore] = field(default_factory=list)
    pair_results: list[PairResult] = field(default_factory=list)

    # ── Section 4: Matched code types (from the matched blocks only) ──
    primary_plagiarism_type: str = ""
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
    report_version: str = "2.1"
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


def _line_range(block: dict[str, Any], side: str) -> tuple[int, int]:
    """A block's 1-based line range on one side, from explicit fields or "s-e"."""
    start = block.get(f"line_start_{side}", block.get(f"start_{side}"))
    end = block.get(f"line_end_{side}", block.get(f"end_{side}"))
    if start is None:
        text = str(block.get(f"lines_{side}", ""))
        if "-" in text and text.replace("-", "").isdigit():
            start, end = text.split("-", 1)
    try:
        return int(start or 0), int(end or start or 0)
    except (TypeError, ValueError):
        return 0, 0


def _slice(lines: list[str], start: int, end: int) -> str:
    """Lines ``start``..``end`` (1-based, inclusive), or "" when out of range."""
    if start < 1 or not lines:
        return ""
    return "\n".join(lines[start - 1 : end])


def _pair_type(blocks: list[MatchedBlock]) -> str:
    """The pair's most common block clone type as a T-label; "" with no typed blocks."""
    counts: dict[str, int] = {}
    for block in blocks:
        t = BLOCK_TYPE_TO_T.get(block.clone_type)
        if t:
            counts[t] = counts.get(t, 0) + 1
    # Ties go to the lower (more literal) type, which the blocks then show.
    return min(counts, key=lambda t: (-counts[t], t)) if counts else ""


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

        The job dict shape (after _normalize_job):
            {
                "id": "...",
                "results": [{"file_a", "file_b", "score", "features", "matching_blocks", ...}],
                "summary": {"total_files", "total_pairs", "suspicious_pairs", "average_similarity"},
                "submissions": {"filename.py": "source code", ...},
                "ai_detection": {"enabled", "flagged_count", "total_files", "submissions": [...]},
                "assignment_name": "...", "course_name": "...", "created_at": "...",
            }
        """
        job_id = job_data.get("id", job_data.get("job_id", ""))
        report = IntegrityAssessmentReport(
            case_id=job_id,
            assignment_name=job_data.get("assignment_name", ""),
            course_name=job_data.get("course_name", ""),
            instructor_name=job_data.get("instructor_name", ""),
            # A check covers a whole class, so no student is named here. The owner
            # fields are the uploader (the instructor), never the student.
            student_id=job_data.get("student_id", ""),
            student_display=job_data.get("student_name", ""),
            analysis_timestamp=job_data.get("created_at", ""),
        )

        # Real keys from _normalize_job
        results_raw = job_data.get("results", [])
        summary_raw = job_data.get("summary", {})
        submissions_raw = job_data.get("submissions", {})
        ai_detection_raw = job_data.get("ai_detection", {})

        # ── Pair results (from results list) ──
        report.pair_results = self._build_pair_results(results_raw)

        # ── What raised the highest-scoring pair's score ──
        report.engine_scores = self._top_pair_engine_scores(report.pair_results)

        # ── Overall similarity ──
        if report.pair_results:
            report.overall_similarity = max(
                p.overall_score for p in report.pair_results
            )
        elif summary_raw:
            report.overall_similarity = float(
                summary_raw.get("average_similarity", 0)
            )

        # ── Risk level ──
        report.risk_level = self._classify_risk(report.overall_similarity)

        # ── Plagiarism type ──
        report.primary_plagiarism_type = (
            report.pair_results[0].plagiarism_type if report.pair_results else ""
        )
        report.plagiarism_type_breakdown = self._plagiarism_type_breakdown(
            report.pair_results
        )

        # ── File analysis (AI detection) ──
        report.files = self._build_file_analysis(
            submissions_raw, ai_detection_raw, report.pair_results
        )
        report.ai_detection_summary = self._build_ai_summary(
            report.files, ai_detection_raw
        )

        # ── Executive summary ──
        report.executive_summary = self._build_executive_summary(report)
        report.recommended_action = self._build_recommendation(report)

        # ── Class context (from summary) ──
        report.class_context = self._build_class_context(report)

        # ── Sources (from submissions + results) ──
        report.sources = self._build_sources(submissions_raw, results_raw)

        # ── Historical (not available in pipeline) ──
        report.historical = HistoricalContext()

        # ── Policy ──
        report.policy_references = self._default_policy_references()
        report.sanctions_matrix = self._default_sanctions_matrix()

        # ── Evidence chain hash ──
        report.evidence_chain_hash = report._compute_hash()

        return report

    # ── Engine scores (aggregate from all results' features) ──

    def _top_pair_engine_scores(self, pairs: list[PairResult]) -> list[EngineScore]:
        """The engines that raised the highest-scoring pair's score, strongest first.

        Uses the learned model's terms; ``score`` is each engine's share of what
        raised the score. Older jobs carry no terms, so they report nothing here
        rather than an average of every feature (which used to include the
        fused and raw scores themselves, presented as engines).
        """
        if not pairs or not pairs[0].contributions:
            return []
        raised = {k: v for k, v in pairs[0].contributions.items() if v > 0}
        total = sum(raised.values())
        return [
            EngineScore(engine=k, score=v / total, label=ENGINE_LABELS.get(k, k))
            for k, v in sorted(raised.items(), key=lambda item: -item[1])
        ]

    # ── Pair results ──

    def _build_pair_results(
        self, pairs: list[dict[str, Any]]
    ) -> list[PairResult]:
        results = []
        for pair in pairs:
            # Normalized result shape: {file_a, file_b, score, features, matching_blocks}
            pr = PairResult(
                file_a=pair.get("file_a", ""),
                file_b=pair.get("file_b", ""),
                overall_score=float(pair.get("score", 0)),
                contributions={
                    k: float(v)
                    for k, v in (pair.get("contributions") or {}).items()
                    if isinstance(v, (int, float))
                },
            )
            code_a = str(pair.get("code_a") or "").splitlines()
            code_b = str(pair.get("code_b") or "").splitlines()
            # Engine sub-scores from features dict
            features = pair.get("features", {})
            for engine, value in features.items():
                if isinstance(value, (int, float)):
                    pr.engine_scores.append(
                        EngineScore(engine=engine, score=float(value))
                    )
            # Matched blocks
            for block in pair.get("matching_blocks", []):
                if isinstance(block, dict):
                    # Pipeline blocks give "lines_a" as a "start-end" range, not code:
                    # the appendix used to print "1-8" where the code should be.
                    start_a, end_a = _line_range(block, "a")
                    start_b, end_b = _line_range(block, "b")
                    pr.matched_blocks.append(
                        MatchedBlock(
                            file_a=pr.file_a,
                            file_b=pr.file_b,
                            lines_a=block.get("code_a") or _slice(code_a, start_a, end_a),
                            lines_b=block.get("code_b") or _slice(code_b, start_b, end_b),
                            line_start_a=start_a,
                            line_end_a=end_a,
                            line_start_b=start_b,
                            line_end_b=end_b,
                            similarity=float(block.get("similarity", block.get("score", 0))),
                            clone_type=block.get("clone_type", block.get("type", "")) or "",
                        )
                    )
            pr.plagiarism_type = _pair_type(pr.matched_blocks)
            results.append(pr)
        return sorted(results, key=lambda r: r.overall_score, reverse=True)

    # ── Risk classification ──

    def _classify_risk(self, score: float) -> str:
        if score >= CRITICAL_MIN:
            return "critical"
        elif score >= HIGH_MIN:
            return "high"
        elif score >= MODERATE_MIN:
            return "moderate"
        elif score >= LOW_MIN:
            return "low"
        return "clean"

    # ── Matched code types ──

    def _plagiarism_type_breakdown(self, pairs: list[PairResult]) -> dict[str, float]:
        """Share of matched blocks by clone type, across every pair.

        This used to bucket pair *scores* into T1-T5, so a 0.9 score read
        "Identical Copy" even when its blocks were renamed, and a 0.2 score read
        "Semantic Clone". Only the code matcher's block types are used now.
        """
        counts: dict[str, int] = {}
        for pair in pairs:
            for block in pair.matched_blocks:
                t = BLOCK_TYPE_TO_T.get(block.clone_type)
                if t:
                    counts[t] = counts.get(t, 0) + 1
        total = sum(counts.values())
        return {t: round(n / total, 4) for t, n in sorted(counts.items())} if total else {}

    # ── File analysis (from submissions + ai_detection) ──

    def _build_file_analysis(
        self,
        submissions: dict[str, str],
        ai_raw: dict[str, Any],
        pairs: list[PairResult] | None = None,
    ) -> list[FileAnalysis]:
        """Build file analysis from submissions dict and ai_detection data.

        Jobs read back from report.json carry no ``submissions``; their files are
        then taken from the compared pairs, so the report never says 0 files.
        """
        files = []
        names = list(submissions) or sorted(
            {name for p in pairs or [] for name in (p.file_a, p.file_b) if name}
        )
        for fname in names:
            fa = FileAnalysis(filename=fname)
            # Match AI detection by filename
            ai_subs = ai_raw.get("submissions", []) if isinstance(ai_raw, dict) else []
            for ai_entry in ai_subs:
                if isinstance(ai_entry, dict) and ai_entry.get("filename") == fname:
                    fa.ai_probability = float(ai_entry.get("ai_probability", 0))
                    fa.ai_confidence = float(ai_entry.get("confidence", 0))
                    fa.ai_signals = {
                        k: float(v)
                        for k, v in (ai_entry.get("signals") or {}).items()
                        if isinstance(v, (int, float))
                    }
                    break
            files.append(fa)
        return files

    def _build_ai_summary(
        self, files: list[FileAnalysis], ai_raw: dict[str, Any]
    ) -> dict[str, Any]:
        """Build AI detection summary from files and raw ai_detection dict."""
        if not ai_raw or not ai_raw.get("enabled"):
            return {"available": bool(ai_raw)}
        return {
            "available": True,
            "total_files": int(ai_raw.get("total_files", len(files))),
            "flagged_count": int(ai_raw.get("flagged_count", 0)),
            "flagged_ratio": round(
                int(ai_raw.get("flagged_count", 0))
                / max(int(ai_raw.get("total_files", 1)), 1),
                4,
            ),
            "average_probability": round(
                float(ai_raw.get("average_score", 0)), 4
            ),
            "max_probability": round(
                float(ai_raw.get("highest_score", 0)), 4
            ),
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
                "Detailed examination recommended. Read the matched code and what "
                "raised the score. If the overlap is not explained by the assignment, "
                "meet the student to discuss it before proceeding."
            )
        else:
            return (
                "Examine the matched code first. If the overlap is not explained by "
                "starter code or the assignment, follow your institution's academic "
                "integrity process; the student must have the chance to respond."
            )

    # ── Class context (from summary dict) ──

    def _build_class_context(self, report: IntegrityAssessmentReport) -> ClassContext:
        """Computed from the report's own pairs (the summary dict lacks most of it)."""
        scores = sorted(p.overall_score for p in report.pair_results)
        if not scores:
            return ClassContext()
        mid = len(scores) // 2
        median = scores[mid] if len(scores) % 2 else (scores[mid - 1] + scores[mid]) / 2
        return ClassContext(
            total_submissions=len(report.files),
            total_pairs=len(scores),
            average_similarity=sum(scores) / len(scores),
            median_similarity=median,
            flagged_ratio=sum(s >= HIGH_MIN for s in scores) / len(scores),
        )

    # ── Sources (from submissions + results) ──

    def _build_sources(
        self, submissions: dict[str, str], results: list[dict[str, Any]]
    ) -> list[SourceProvenance]:
        """Build source provenance from submissions dict."""
        import hashlib

        _EXT_MAP = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".java": "Java", ".cpp": "C++", ".c": "C", ".cs": "C#",
            ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
            ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala",
            ".r": "R", ".m": "MATLAB", ".sh": "Shell", ".sql": "SQL",
            ".html": "HTML", ".css": "CSS", ".json": "JSON", ".yaml": "YAML",
        }
        sources = []
        for fname, content in submissions.items():
            import os

            ext = os.path.splitext(fname)[1].lower()
            sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""
            sources.append(
                SourceProvenance(
                    filename=fname,
                    language=_EXT_MAP.get(ext, ext.lstrip(".").upper() if ext else "Unknown"),
                    line_count=content.count("\n") + 1 if content else 0,
                    file_size=len(content.encode("utf-8")) if content else 0,
                    sha256=sha256,
                )
            )
        return sources

    # ── Defaults ──

    def _default_policy_references(self) -> list[str]:
        # Deliberately generic: the policy, procedure and any sanction are the
        # institution's to state, not this software's. (A US FERPA notice and an
        # invented sanctions matrix used to appear here.)
        return [
            (
                "Follow your institution's academic integrity policy and procedures. "
                "This report does not set or recommend any sanction."
            ),
            (
                "The student has the right to see this evidence and to respond before "
                "any decision is made."
            ),
            (
                "Handle this report as confidential personal information under the "
                "privacy law that applies to your institution."
            ),
        ]

    def _default_sanctions_matrix(self) -> list[dict[str, str]]:
        return []
