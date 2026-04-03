"""
Evidence Chain PDF Exporter — Academic Integrity Committee Reports.

Generates professional, multi-page PDF reports with:
- Cover page with case metadata
- Executive summary with risk cards
- Similarity heatmap (seaborn/matplotlib)
- Side-by-side code diff visualization
- AI generation probability chart
- Engine performance radar chart
- Confusion matrix
- External tool evidence table
- Statistical significance statement
- Digital signature (SHA-256 hash)
- Anti-tamper integrity verification
- Confidential watermark on every page

Uses WeasyPrint (preferred) or pdfkit (fallback) for HTML→PDF conversion.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from src.infrastructure.reporting.visualizations import (
    generate_similarity_heatmap,
    generate_code_diff_image,
    generate_ai_probability_chart,
    generate_engine_radar_chart,
    generate_confusion_matrix_image,
)

logger = logging.getLogger(__name__)

# PDF backend detection
PDF_BACKEND = None
try:
    import weasyprint
    PDF_BACKEND = "weasyprint"
except ImportError:
    try:
        import pdfkit
        PDF_BACKEND = "pdfkit"
    except ImportError:
        PDF_BACKEND = None


class EvidenceChainPdfExporter:
    """
    Generates forensic evidence chain PDFs for academic integrity committees.

    Usage:
        exporter = EvidenceChainPdfExporter(
            template_dir=Path("src/infrastructure/reporting/templates"),
            output_dir=Path("reports/evidence"),
        )
        pdf_path = exporter.export(case_data)
    """

    SYSTEM_VERSION = "IntegrityDesk v2.5 Forensic Engine"

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.output_dir = output_dir or Path("reports/evidence")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = self.env.get_template("evidence_report.html")

    def export(
        self,
        case_data: Dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Generate a complete evidence chain PDF.

        Args:
            case_data: Dictionary containing all case information.
            output_path: Optional output path. Defaults to output_dir/case_id.pdf.

        Returns:
            Path to generated PDF, or None if generation failed.
        """
        if PDF_BACKEND is None:
            logger.error(
                "No PDF backend available. Install weasyprint or pdfkit."
            )
            return None

        # Build context with visualizations
        context = self._build_context(case_data)

        # Render HTML
        html_content = self.template.render(**context)

        # Determine output path
        case_id = case_data.get("case_id", "unknown")
        if output_path is None:
            output_path = self.output_dir / f"evidence_{case_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to PDF
        try:
            if PDF_BACKEND == "weasyprint":
                weasyprint.HTML(string=html_content).write_pdf(str(output_path))
            elif PDF_BACKEND == "pdfkit":
                import pdfkit
                options = {
                    "page-size": "A4",
                    "margin-top": "18mm",
                    "margin-right": "15mm",
                    "margin-bottom": "20mm",
                    "margin-left": "15mm",
                    "encoding": "UTF-8",
                    "enable-local-file-access": None,
                }
                pdfkit.from_string(html_content, str(output_path), options=options)

            logger.info(f"Evidence PDF exported: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            return None

    def export_html(
        self,
        case_data: Dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """Export as standalone HTML (no PDF conversion)."""
        context = self._build_context(case_data)
        html_content = self.template.render(**context)

        if output_path is None:
            case_id = case_data.get("case_id", "unknown")
            output_path = self.output_dir / f"evidence_{case_id}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path

    def _build_context(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the full Jinja2 context with visualizations."""
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M")

        # Digital signature
        payload = json.dumps(case_data, sort_keys=True, default=str).encode()
        report_hash = hashlib.sha256(payload).hexdigest()

        # Extract core fields
        similarity_score = case_data.get("similarity_score", 0.0)
        ai_probability = case_data.get("ai_probability", 0.0)
        consensus_index = case_data.get("consensus_index", 0.0)

        risk_level = self._risk_label(similarity_score)
        ai_label = self._ai_label(ai_probability)
        consensus_label = self._consensus_label(consensus_index)

        # Generate visualizations
        heatmap_image = self._generate_heatmap(case_data)
        diff_image = self._generate_diff(case_data)
        ai_chart_image = self._generate_ai_chart(case_data)
        radar_image = self._generate_radar(case_data)
        confusion_image = self._generate_confusion_matrix(case_data)

        # Evidence pairs for side-by-side display
        evidence_pairs = self._extract_evidence_pairs(case_data)

        # Tool comparison
        tool_comparison = self._extract_tool_comparison(case_data)

        # Significance statement
        significance_statement = case_data.get("significance_statement", "")

        # External tools
        external_tools = case_data.get("external_tools", [])

        # AI details
        ai_details = case_data.get("ai_details", [])

        # Confusion stats
        confusion_stats = case_data.get("confusion_stats", {})

        # Key conclusions
        key_conclusions = case_data.get("key_conclusions", [])

        # Dataset hash
        dataset_hash = case_data.get("dataset_hash", "N/A")

        return {
            "case_id": case_data.get("case_id", "N/A"),
            "student_name": case_data.get("student_name", "N/A"),
            "student_id": case_data.get("student_id", "N/A"),
            "course": case_data.get("course", "N/A"),
            "assignment": case_data.get("assignment", "N/A"),
            "report_date": timestamp,
            "investigator": case_data.get("investigator", "N/A"),
            "system_version": self.SYSTEM_VERSION,
            "similarity_score": similarity_score,
            "ai_probability": ai_probability,
            "consensus_index": consensus_index,
            "ci_margin": case_data.get("ci_margin", 0.03),
            "n_bootstrap": case_data.get("n_bootstrap", 1000),
            "risk_level": risk_level,
            "ai_label": ai_label,
            "consensus_label": consensus_label,
            "heatmap_image": heatmap_image,
            "diff_image": diff_image,
            "ai_chart_image": ai_chart_image,
            "radar_image": radar_image,
            "confusion_matrix_image": confusion_image,
            "evidence_pairs": evidence_pairs,
            "tool_comparison": tool_comparison,
            "significance_statement": significance_statement,
            "external_tools": external_tools,
            "ai_details": ai_details,
            "confusion_stats": confusion_stats,
            "key_conclusions": key_conclusions,
            "dataset_hash": dataset_hash,
            "report_hash": report_hash,
        }

    def _generate_heatmap(self, case_data: Dict[str, Any]) -> Optional[str]:
        matrix = case_data.get("similarity_matrix")
        labels = case_data.get("similarity_labels")
        if matrix:
            return generate_similarity_heatmap(matrix, labels)
        return None

    def _generate_diff(self, case_data: Dict[str, Any]) -> Optional[str]:
        code_a = case_data.get("code_a", "")
        code_b = case_data.get("code_b", "")
        if code_a and code_b:
            return generate_code_diff_image(
                code_a, code_b,
                case_data.get("file_a", "Submission A"),
                case_data.get("file_b", "Submission B"),
            )
        return None

    def _generate_ai_chart(self, case_data: Dict[str, Any]) -> Optional[str]:
        ai_results = case_data.get("ai_model_results")
        if ai_results:
            return generate_ai_probability_chart(ai_results)
        return None

    def _generate_radar(self, case_data: Dict[str, Any]) -> Optional[str]:
        engine_scores = case_data.get("engine_performance")
        if engine_scores:
            return generate_engine_radar_chart(engine_scores)
        return None

    def _generate_confusion_matrix(self, case_data: Dict[str, Any]) -> Optional[str]:
        stats = case_data.get("confusion_stats", {})
        if "tp" in stats:
            return generate_confusion_matrix_image(
                stats.get("tp", 0),
                stats.get("fp", 0),
                stats.get("tn", 0),
                stats.get("fn", 0),
            )
        return None

    def _extract_evidence_pairs(self, case_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        pairs = case_data.get("evidence_pairs", [])
        result = []
        for p in pairs[:5]:
            result.append({
                "file_a": p.get("file_a", "File A"),
                "file_b": p.get("file_b", "File B"),
                "similarity": p.get("similarity", 0.0),
                "engine": p.get("engine", "Unknown"),
                "risk": self._risk_label(p.get("similarity", 0.0)),
                "a_lines": p.get("a_lines", "—"),
                "b_lines": p.get("b_lines", "—"),
                "code_a": p.get("code_a", ""),
                "code_b": p.get("code_b", ""),
            })
        return result

    def _extract_tool_comparison(self, case_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        tools = case_data.get("tool_comparison", [])
        result = []
        for t in tools:
            result.append({
                "name": t.get("name", "Unknown"),
                "similarity": t.get("similarity", 0.0),
                "precision": t.get("precision", 0.0),
                "recall": t.get("recall", 0.0),
                "f1": t.get("f1", 0.0),
                "ci_lower": t.get("ci_lower", 0.0),
                "ci_upper": t.get("ci_upper", 0.0),
                "risk": self._risk_label(t.get("similarity", 0.0)),
            })
        return result

    @staticmethod
    def _risk_label(score: float) -> str:
        if score >= 0.85:
            return "Critical"
        if score >= 0.65:
            return "High"
        if score >= 0.40:
            return "Medium"
        return "Low"

    @staticmethod
    def _ai_label(prob: float) -> str:
        if prob > 0.7:
            return "Likely AI-Generated"
        if prob > 0.4:
            return "Uncertain"
        return "Likely Human-Written"

    @staticmethod
    def _consensus_label(index: float) -> str:
        if index > 0.8:
            return "Strong Consensus"
        if index > 0.5:
            return "Moderate Consensus"
        return "Weak Consensus"
