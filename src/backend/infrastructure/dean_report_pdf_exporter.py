"""PDF exporter for Dean-grade Academic Integrity Evidence Reports.

Generates professional PDF reports suitable for:
- Academic integrity hearings
- Department reviews
- Dean-level decisions
- Committee deliberations
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from src.backend.infrastructure.dean_report_generator import (
    DeanGradeReport,
    VERDICT_LABELS,
)


class DeanReportPdfExporter:
    """Exports Dean-grade evidence reports as PDF and HTML."""

    SYSTEM_VERSION = "IntegrityDesk Forensic Evidence Engine v2.6"

    def __init__(self, template_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.output_dir = output_dir or Path("reports/dean")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = self.env.get_template("dean_report.html")

    def export(
        self,
        report: DeanGradeReport,
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """Export report as PDF.

        Args:
            report: DeanGradeReport instance
            output_path: Optional output path

        Returns:
            Path to generated PDF, or None if export failed
        """
        context = self._build_context(report)
        html_content = self.template.render(**context)

        if output_path is None:
            output_path = self.output_dir / f"report_{report.case_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import weasyprint
            weasyprint.HTML(string=html_content).write_pdf(str(output_path))
            return output_path
        except ImportError:
            pass

        try:
            import pdfkit
            options = {
                "page-size": "A4",
                "margin-top": "18mm",
                "margin-right": "15mm",
                "margin-bottom": "20mm",
                "margin-left": "15mm",
                "encoding": "UTF-8",
            }
            pdfkit.from_string(html_content, str(output_path), options=options)
            return output_path
        except Exception:
            pass

        return self._export_html_fallback(report, output_path)

    def export_html(
        self,
        report: DeanGradeReport,
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """Export report as HTML."""
        context = self._build_context(report)
        html_content = self.template.render(**context)

        if output_path is None:
            output_path = self.output_dir / f"report_{report.case_id}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path

    def _build_context(self, report: DeanGradeReport) -> Dict[str, Any]:
        """Build template context from report."""
        struct_ev = report.structural_evidence[0] if report.structural_evidence else None
        lex_ev = report.lexical_evidence[0] if report.lexical_evidence else None
        sem_ev = report.semantic_evidence[0] if report.semantic_evidence else None
        cf_ev = report.control_flow_evidence[0] if report.control_flow_evidence else None
        div_ev = report.divergence_evidence[0] if report.divergence_evidence else None

        return {
            "case_id": report.case_id,
            "course_id": report.course_id,
            "assignment_id": report.assignment_id,
            "submission_a_id": report.submission_a_id,
            "submission_b_id": report.submission_b_id,
            "final_verdict": report.final_verdict,
            "verdict_label": VERDICT_LABELS.get(report.final_verdict, ""),
            "summary_paragraph": self._generate_summary_paragraph(report),
            "generated_at": report.generated_at,
            "report_hash": self._compute_report_hash(report),
            "structural_score": struct_ev.value if struct_ev else None,
            "structural_confidence": struct_ev.confidence if struct_ev else None,
            "structural_explanation": struct_ev.explanation if struct_ev else None,
            "lexical_score": lex_ev.value if lex_ev else None,
            "lexical_confidence": lex_ev.confidence if lex_ev else None,
            "lexical_explanation": lex_ev.explanation if lex_ev else None,
            "semantic_score": sem_ev.value if sem_ev else None,
            "semantic_confidence": sem_ev.confidence if sem_ev else None,
            "semantic_explanation": sem_ev.explanation if sem_ev else None,
            "semantic_disclaimer": self._get_semantic_disclaimer(sem_ev),
            "control_flow_score": cf_ev.value if cf_ev else None,
            "control_flow_confidence": cf_ev.confidence if cf_ev else None,
            "control_flow_explanation": cf_ev.explanation if cf_ev else None,
            "divergence_score": div_ev.value if div_ev else None,
            "reviewer_notes": report.reviewer_notes,
            "cluster_disclaimer": "Cluster membership alone does not imply misconduct.",
        }

    def _generate_summary_paragraph(self, report: DeanGradeReport) -> str:
        """Generate neutral summary paragraph."""
        if report.final_verdict == "CLEAN":
            return ("Analysis of the two submissions shows no significant structural, "
                    "lexical, or semantic overlap that would suggest shared work.")
        elif report.final_verdict == "REVIEW_REQUIRED":
            return ("Analysis reveals some similarities between submissions that merit "
                    "instructor review to determine if the patterns have academic explanation.")
        else:
            return ("Analysis reveals strong structural and lexical overlap between "
                    "submissions. This evidence warrants detailed examination by the instructor.")

    def _get_semantic_disclaimer(self, sem_ev) -> Optional[str]:
        """Get semantic evidence disclaimer."""
        if sem_ev:
            return ("Semantic similarity alone is not sufficient for academic misconduct inference. "
                    "This is supplementary evidence only.")
        return None

    def _compute_report_hash(self, report: DeanGradeReport) -> str:
        """Compute hash for report integrity."""
        content = json.dumps(report.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _export_html_fallback(
        self, report: DeanGradeReport, output_path: Path
    ) -> Optional[Path]:
        """Fallback to HTML export when PDF backends unavailable."""
        context = self._build_context(report)
        html_content = self.template.render(**context)

        html_path = output_path.with_suffix(".html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding="utf-8")
        return html_path


def export_dean_report(
    report: DeanGradeReport,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    """Convenience function to export a Dean-grade report."""
    exporter = DeanReportPdfExporter()
    return exporter.export(report, output_path)