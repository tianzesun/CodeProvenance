"""Professional report generator for code similarity analysis.

Generates HTML, PDF, and JSON reports with:
- Side-by-side code highlighting
- Similarity heatmaps
- Risk level indicators
- AI detection results
- Professional formatting

Usage:
    from src.backend.infrastructure.professional_report_generator import ReportGenerator
    generator = ReportGenerator()
    html_report = generator.generate_html_report(analysis_results)
    generator.save_report(html_report, "report.html")
"""

import json
import logging
import hashlib
from html import escape
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.backend.engines.similarity.code_matching import CodeHighlighter

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate professional plagiarism detection reports."""

    def __init__(
        self, institution_name: str = "CodeProvenance", branding_color: str = "#2563eb"
    ) -> None:
        """Initialize report generator.

        Args:
            institution_name: Name of the institution/course
            branding_color: Primary color for branding (hex)
        """
        self.institution_name = institution_name
        self.branding_color = branding_color

    def generate_html_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive HTML report.

        Args:
            results: Analysis results from the detection service

        Returns:
            HTML string of the report
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = results.get("summary", {})
        pairs = results.get("pairs", [])
        top_pair = max(
            pairs, key=lambda pair: pair.get("similarity_score", 0), default={}
        )
        top_score = top_pair.get("similarity_score", 0)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntegrityDesk Originality Report - {escape(self.institution_name)}</title>
    <style>
        :root {{ color-scheme: light; --brand: {self.branding_color}; --ink: #172033; --muted: #64748b; --line: #dbe3ef; --soft: #f7f9fc; }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; background: #eef3f8; color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.5; }}
        .shell {{ max-width: 980px; margin: 0 auto; background: #fff; min-height: 100vh; box-shadow: 0 20px 70px rgba(15, 23, 42, 0.12); }}
        .conf-banner {{ background: #172033; color: #fff; text-align: center; padding: 8px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }}
        header {{ padding: 26px 34px; color: #fff; border-bottom: 1px solid #1557b0; background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%); display: flex; justify-content: space-between; gap: 22px; align-items: center; }}
        .report-head-left {{ display: flex; align-items: center; gap: 16px; }}
        .report-logo {{ width: 42px; height: 42px; background: rgba(255,255,255,.18); border-radius: 8px; display: grid; place-items: center; font-weight: 900; }}
        .eyebrow {{ color: rgba(255,255,255,.82); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }}
        h1 {{ margin: 8px 0 4px; font-size: 30px; line-height: 1.15; }}
        h2 {{ margin: 0; font-size: 18px; }}
        h3 {{ margin: 0; font-size: 15px; }}
        .meta {{ color: var(--muted); font-size: 13px; }}
        header .meta {{ color: rgba(255,255,255,.82); text-align: right; }}
        header h1 {{ color: #fff; }}
        main {{ padding: 30px 40px 44px; }}
        .summary {{ display: grid; grid-template-columns: 1.2fr repeat(4, minmax(130px, 1fr)); gap: 14px; margin-bottom: 22px; }}
        .card {{ border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 16px; }}
        .card.soft {{ background: var(--soft); }}
        .label {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
        .value {{ margin-top: 6px; font-size: 24px; font-weight: 800; }}
        .section {{ border: 1px solid var(--line); border-radius: 8px; background: #fff; margin-top: 18px; overflow: hidden; }}
        .section-head {{ padding: 16px 18px; border-bottom: 1px solid var(--line); background: #fbfdff; display: flex; justify-content: space-between; gap: 16px; align-items: center; }}
        .section-body {{ padding: 18px; }}
        .method-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
        .method {{ border-left: 3px solid var(--brand); background: #f8fafc; padding: 12px; border-radius: 6px; font-size: 13px; color: #334155; }}
        .decision-panel {{ border: 1px solid #bfdbfe; background: #eff6ff; border-radius: 8px; padding: 18px; }}
        .decision-title {{ color: #1e3a8a; font-size: 20px; font-weight: 900; margin: 4px 0 8px; }}
        .two-col {{ display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(280px, .75fr); gap: 14px; }}
        .audit-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
        .audit-item {{ border: 1px solid var(--line); border-radius: 8px; padding: 11px 12px; background: #fff; }}
        .hash {{ font: 11px/1.45 "SFMono-Regular", Consolas, "Liberation Mono", monospace; color: #475569; overflow-wrap: anywhere; }}
        .decision-box {{ border: 1px solid #c7d2fe; background: #eef2ff; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
        .signature-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 18px; }}
        .signature-line {{ border-top: 1px solid #334155; padding-top: 7px; color: #475569; font-size: 12px; }}
        .heat-row {{ display: grid; grid-template-columns: 34px 1fr 78px 84px; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid #eef2f7; }}
        .heat-row:last-child {{ border-bottom: 0; }}
        .rank {{ width: 30px; height: 30px; border-radius: 6px; display: grid; place-items: center; background: var(--brand); color: #fff; font-weight: 800; font-size: 12px; }}
        .bar {{ height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: 6px; }}
        .bar > span {{ display: block; height: 100%; background: var(--brand); }}
        .badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 800; }}
        .risk-critical, .risk-high {{ background: #fee2e2; color: #991b1b; }}
        .risk-review {{ background: #e0f2fe; color: #075985; }}
        .risk-medium {{ background: #fef3c7; color: #92400e; }}
        .risk-low {{ background: #dcfce7; color: #166534; }}
        details.finding {{ border-top: 1px solid var(--line); }}
        details.finding:first-child {{ border-top: 0; }}
        summary {{ cursor: pointer; list-style: none; padding: 18px; display: grid; grid-template-columns: 1fr auto auto; gap: 14px; align-items: center; }}
        summary::-webkit-details-marker {{ display: none; }}
        summary:after {{ content: "Show Details"; color: var(--brand); font-size: 13px; font-weight: 800; }}
        details[open] summary:after {{ content: "Hide Details"; }}
        .finding-body {{ padding: 0 18px 18px; }}
        .evidence-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }}
        .code-card {{ border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #0f172a; }}
        .code-title {{ background: #1e293b; color: #e2e8f0; font-size: 12px; font-weight: 700; padding: 9px 12px; }}
        table.code {{ width: 100%; border-collapse: collapse; font: 12px/1.55 "SFMono-Regular", Consolas, "Liberation Mono", monospace; }}
        .ln {{ width: 48px; text-align: right; color: #94a3b8; background: #111827; border-right: 1px solid #334155; padding: 0 8px; user-select: none; vertical-align: top; }}
        .src {{ color: #dbeafe; white-space: pre-wrap; overflow-wrap: anywhere; padding: 0 10px; }}
        .matched .ln {{ background: #3f2f12; color: #fde68a; }}
        .matched .src {{ background: #422006; color: #fef3c7; }}
        .signals {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 12px 0; }}
        .signal {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
        .signal-row {{ display: flex; justify-content: space-between; gap: 12px; padding: 5px 0; font-size: 13px; border-bottom: 1px solid #eef2f7; }}
        .signal-row:last-child {{ border-bottom: 0; }}
        .note {{ color: #475569; font-size: 13px; }}
        footer {{ border-top: 1px solid var(--line); color: var(--muted); padding: 18px 40px; font-size: 12px; }}
        @media print {{
            body {{ background: #fff; }}
            .shell {{ box-shadow: none; }}
            summary:after {{ display: none; }}
        }}
        @media (max-width: 900px) {{
            header, main, footer {{ padding-left: 18px; padding-right: 18px; }}
            .summary, .method-grid, .evidence-grid, .signals, .two-col, .audit-grid, .signature-grid {{ grid-template-columns: 1fr; }}
            summary {{ grid-template-columns: 1fr; }}
            .heat-row {{ grid-template-columns: 30px 1fr; }}
        }}
    </style>
</head>
<body>
<div class="shell">
    <div class="conf-banner">Confidential -- Academic Integrity Evidence Report</div>
    <header>
        <div class="report-head-left">
            <div class="report-logo">ID</div>
            <div>
                <div class="eyebrow">{escape(self.institution_name)} Evidence Packet</div>
                <h1>IntegrityDesk Originality Report</h1>
            </div>
        </div>
        <div class="meta">Generated {timestamp}<br>Report ID {escape(str(results.get('report_id', 'N/A')))}</div>
    </header>
    <main>
        <div class="summary">
            <div class="card soft">
                <div class="label">Fused Review Score</div>
                <div class="value">{top_score:.1%}</div>
                <div class="meta">{escape(str(top_pair.get('file_a', 'No file')))} vs {escape(str(top_pair.get('file_b', 'No file')))}</div>
            </div>
            <div class="card"><div class="label">Files</div><div class="value">{summary.get('total_files', 0)}</div></div>
            <div class="card"><div class="label">Pairs</div><div class="value">{summary.get('total_pairs', 0)}</div></div>
            <div class="card"><div class="label">Flagged</div><div class="value">{summary.get('suspicious_pairs', 0)}</div></div>
            <div class="card"><div class="label">Avg Fused Score</div><div class="value">{summary.get('average_similarity', 0):.1%}</div></div>
        </div>

        {self._generate_executive_decision(results, top_pair)}
        {self._generate_chain_of_custody(results, timestamp)}

        <section class="section">
            <div class="section-head">
                <h2>How The System Reached This Result</h2>
                <span class="meta">Corroborating evidence, not a single score</span>
            </div>
            <div class="section-body">
                <div class="method-grid">
                    <div class="method"><strong>Lexical evidence.</strong> Token, n-gram, and winnowing signals find copied or lightly edited source even when spacing and comments change.</div>
                    <div class="method"><strong>Structural evidence.</strong> AST and control-structure signals compare program shape so renamed variables do not hide similar logic.</div>
                    <div class="method"><strong>Report evidence.</strong> The highlighted snippets below show matching line spans from the submitted files. External tools are listed separately with their own coverage numbers when available.</div>
                </div>
            </div>
        </section>

        {self._generate_ai_summary(results.get('ai_detection', {}))}

        <section class="section">
            <div class="section-head">
                <h2>Top Review Pairs</h2>
            </div>
            <div class="section-body">
                {self._generate_heatmap(pairs)}
            </div>
        </section>

        <section class="section">
            <div class="section-head">
                <h2>Detailed Findings And Evidence</h2>
                <span class="meta">{len(pairs)} pair(s)</span>
            </div>
            {self._generate_pair_details(pairs)}
        </section>

        {self._generate_signoff_section()}
    </main>
    <footer>
        Generated by CodeProvenance. Prepared as an institutional evidence packet for academic integrity review; decision fields require authorized institutional sign-off.
    </footer>
</div>
</body>
</html>"""

        return html

    def generate_json_report(self, results: Dict[str, Any]) -> str:
        """Generate a JSON report for API consumption.

        Args:
            results: Analysis results from the detection service

        Returns:
            JSON string of the report
        """
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "institution": self.institution_name,
                "version": "1.0",
                "report_id": results.get("report_id", "N/A"),
            },
            "summary": results.get("summary", {}),
            "pairs": results.get("pairs", []),
            "selected_tools": results.get("selected_tools", []),
            "external_tool_results": results.get("external_tool_results", {}),
            "assignment_mode": results.get("assignment_mode"),
            "assignment_mode_name": results.get("assignment_mode_name"),
            "assignment_mode_version": results.get("assignment_mode_version"),
            "reproducibility": results.get("reproducibility", {}),
            "ai_detection": results.get("ai_detection", {}),
            "web_analysis": results.get("web_analysis", {}),
            "recommendations": self._generate_recommendations(results),
        }

        return json.dumps(report, indent=2, default=str)

    def save_report(self, content: str, filepath: str) -> None:
        """Save report to file.

        Args:
            content: Report content (HTML or JSON)
            filepath: Path to save the file
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        logger.info(f"Report saved to {filepath}")

    def _generate_risk_cards(self, distribution: Dict[str, int]) -> str:
        """Generate risk level cards HTML."""
        risk_levels = [
            (
                "Critical",
                distribution.get("critical", 0),
                "bg-red-100 text-red-800 border-red-200",
            ),
            (
                "High",
                distribution.get("high", 0),
                "bg-orange-100 text-orange-800 border-orange-200",
            ),
            (
                "Medium",
                distribution.get("medium", 0),
                "bg-yellow-100 text-yellow-800 border-yellow-200",
            ),
            (
                "Low",
                distribution.get("low", 0),
                "bg-green-100 text-green-800 border-green-200",
            ),
        ]

        cards = []
        for name, count, color_class in risk_levels:
            cards.append(
                f"""
            <div class="border rounded-lg p-4 {color_class}">
                <dt class="text-sm font-medium"> {name} Risk</dt>
                <dd class="mt-1 text-2xl font-bold">{count}</dd>
            </div>
            """
            )

        return "".join(cards)

    def _generate_executive_decision(
        self, results: Dict[str, Any], top_pair: Dict[str, Any]
    ) -> str:
        """Render the institutional decision recommendation."""
        pairs = results.get("pairs", [])
        decision = self._case_decision_label(pairs)
        standard = self._evidence_standard_label(top_pair)
        support = self._concrete_support_count(
            top_pair.get("engine_scores", {}), top_pair.get("external_evidence", [])
        )
        summary = results.get("summary", {})
        recommendations = self._generate_recommendations(results)
        recommendation_rows = "".join(
            f"<li>{escape(str(item))}</li>" for item in recommendations
        )

        return f"""
        <section class="section">
            <div class="section-head">
                <h2>Executive Decision Summary</h2>
                <span class="badge {self._risk_class(standard)}">{escape(standard)}</span>
            </div>
            <div class="section-body two-col">
                <div class="decision-panel">
                    <div class="label">Recommended Institutional Action</div>
                    <div class="decision-title">{escape(decision)}</div>
                    <p class="note">{self._case_decision_text(top_pair, support)}</p>
                </div>
                <div class="audit-grid" style="grid-template-columns:1fr;">
                    <div class="audit-item">
                        <div class="label">Concrete Evidence Sources</div>
                        <div class="value">{support}</div>
                    </div>
                    <div class="audit-item">
                        <div class="label">Pairs Requiring Review</div>
                        <div class="value">{summary.get('suspicious_pairs', 0)}</div>
                    </div>
                    <div class="audit-item">
                        <div class="label">Recommended Next Steps</div>
                        <ul class="note">{recommendation_rows}</ul>
                    </div>
                </div>
            </div>
        </section>
        """

    def _generate_chain_of_custody(
        self, results: Dict[str, Any], timestamp: str
    ) -> str:
        """Render chain-of-custody and reproducibility fields."""
        report_id = escape(str(results.get("report_id", "N/A")))
        selected_tools = results.get("selected_tools", [])
        tool_names = ", ".join(str(tool) for tool in selected_tools) or "CodeProvenance"
        reproducibility = results.get("reproducibility", {})
        submission_hash = str(
            reproducibility.get("submission_set_hash")
            or self._report_submission_hash(results.get("pairs", []))
        )
        mode_name = str(
            results.get("assignment_mode_name")
            or results.get("assignment_mode")
            or "Default"
        )

        return f"""
        <section class="section">
            <div class="section-head">
                <h2>Chain Of Custody</h2>
                <span class="meta">Reproducibility and audit metadata</span>
            </div>
            <div class="section-body audit-grid">
                <div class="audit-item"><div class="label">Report ID</div><div class="hash">{report_id}</div></div>
                <div class="audit-item"><div class="label">Generated</div><div class="hash">{escape(timestamp)}</div></div>
                <div class="audit-item"><div class="label">Assignment Mode</div><div class="hash">{escape(mode_name)}</div></div>
                <div class="audit-item"><div class="label">Tools Used</div><div class="hash">{escape(tool_names)}</div></div>
                <div class="audit-item"><div class="label">Submission Set Hash</div><div class="hash">{escape(submission_hash[:64])}</div></div>
                <div class="audit-item"><div class="label">Evidence Policy</div><div class="hash">Score is triage; decision is based on listed evidence blocks and external-tool support.</div></div>
            </div>
        </section>
        """

    def _generate_signoff_section(self) -> str:
        """Render sign-off lines for institutional use."""
        return """
        <section class="section">
            <div class="section-head">
                <h2>Decision Sign-Off</h2>
                <span class="meta">For authorized institutional use</span>
            </div>
            <div class="section-body">
                <div class="signature-grid">
                    <div><div class="signature-line">Instructor / Investigator</div></div>
                    <div><div class="signature-line">Academic Integrity Officer</div></div>
                    <div><div class="signature-line">Dean / Delegate</div></div>
                </div>
            </div>
        </section>
        """

    def _generate_ai_summary(self, ai_data: Dict[str, Any]) -> str:
        """Generate AI detection summary section."""
        if not ai_data:
            return ""

        ai_flagged = ai_data.get("flagged_count", 0)
        total_files = ai_data.get("total_files", 0)

        return f"""
        <section class="section">
            <div class="section-head">
                <h2>AI Detection Summary</h2>
            </div>
            <div class="section-body">
                <div class="method-grid">
                    <div class="card soft">
                        <div class="label">AI-Flagged Files</div>
                        <div class="value">{ai_flagged}</div>
                    </div>
                    <div class="card soft">
                        <div class="label">Files Analyzed</div>
                        <div class="value">{total_files}</div>
                    </div>
                    <div class="card soft">
                        <div class="label">Detection Rate</div>
                        <div class="value">{(ai_flagged/total_files*100) if total_files > 0 else 0:.1f}%</div>
                    </div>
                </div>
            </div>
        </section>
        """

    def _generate_heatmap(self, pairs: List[Dict[str, Any]]) -> str:
        """Generate similarity heatmap visualization."""
        if not pairs:
            return "<p class='text-gray-500'>No pairs to display.</p>"

        # Sort by similarity score
        sorted_pairs = sorted(
            pairs, key=lambda x: x.get("similarity_score", 0), reverse=True
        )

        rows = []
        for i, pair in enumerate(sorted_pairs[:20]):  # Top 20
            score = pair.get("similarity_score", 0)
            file_a = pair.get("file_a", "Unknown")
            file_b = pair.get("file_b", "Unknown")
            review_label = self._review_label(pair)

            rows.append(
                f"""
            <div class="heat-row">
                <div class="rank">{i+1}</div>
                <div class="flex-1">
                    <div>
                        <strong>{escape(str(file_a))}</strong> vs <strong>{escape(str(file_b))}</strong>
                    </div>
                    <div class="bar"><span style="width: {score*100:.1f}%"></span></div>
                </div>
                <strong>{score:.1%}</strong>
                <span class="badge {self._risk_class(review_label)}">{escape(review_label)}</span>
            </div>
            """
            )

        return f"""
        <div>
            {''.join(rows)}
        </div>
        """

    def _generate_pair_details(self, pairs: List[Dict[str, Any]]) -> str:
        """Generate detailed pair comparison sections."""
        if not pairs:
            return "<div class='section-body meta'>No pairs to display.</div>"

        details = []
        sorted_pairs = sorted(
            pairs, key=lambda item: item.get("similarity_score", 0), reverse=True
        )
        for pair in sorted_pairs:
            file_a = pair.get("file_a", "Unknown")
            file_b = pair.get("file_b", "Unknown")
            score = pair.get("similarity_score", 0)
            review_label = self._review_label(pair)
            engines = pair.get("engine_scores", {})
            ai_info = pair.get("ai_detection", {})
            code_a = pair.get("code_a", "")
            code_b = pair.get("code_b", "")
            external_evidence = pair.get("external_evidence", [])
            evidence_html = self._render_evidence_segments(
                code_a, code_b, file_a, file_b
            )
            ai_html = self._render_ai_details(ai_info)
            signal_html = self._render_engine_scores(engines)
            external_html = self._render_external_evidence(external_evidence)
            decision_html = self._render_pair_decision_box(pair)
            provenance_html = self._render_pair_provenance(pair)

            details.append(
                f"""
            <details class="finding">
                <summary>
                    <div>
                        <h3>{escape(str(file_a))} vs {escape(str(file_b))}</h3>
                        <div class="meta">Open details for matching line spans, external-tool evidence, and engine agreement.</div>
                    </div>
                    <strong>{score:.1%}</strong>
                    <span class="badge {self._risk_class(review_label)}">{escape(review_label)}</span>
                </summary>
                <div class="finding-body">
                    {decision_html}
                    <div class="signals">
                        <div class="signal">
                            <h3>Engine Agreement</h3>
                            {signal_html}
                        </div>
                        <div class="signal">
                            <h3>Interpretation</h3>
                            <p class="note">{self._pair_interpretation(score, engines)}</p>
                            {ai_html}
                        </div>
                    </div>
                    {external_html}
                    {provenance_html}
                    {evidence_html}
                </div>
            </details>
            """
            )

        return "".join(details)

    def _risk_class(self, risk: Any) -> str:
        """Return a CSS class for a risk label."""
        normalized = str(risk or "").strip().lower()
        if "evidence" in normalized or "review" in normalized:
            return "risk-review"
        if normalized in {"critical", "high"}:
            return "risk-high"
        if normalized == "medium":
            return "risk-medium"
        if normalized == "low":
            return "risk-low"
        return "risk-medium"

    def _review_label(self, pair: Dict[str, Any]) -> str:
        """Return evidence-supported review wording for a pair."""
        score = self._safe_float(pair.get("similarity_score"))
        support = self._concrete_support_count(
            pair.get("engine_scores", {}), pair.get("external_evidence", [])
        )
        if score >= 0.85 and support >= 2:
            return "High Evidence Review"
        if score >= 0.65 and support >= 1:
            return "Evidence Review"
        if score >= 0.35:
            return "Needs Instructor Review"
        return "Low Priority"

    def _case_decision_label(self, pairs: List[Dict[str, Any]]) -> str:
        """Return a case-level recommendation based on the strongest pair."""
        if not pairs:
            return "No Action Recommended"
        top_pair = max(
            pairs, key=lambda pair: self._safe_float(pair.get("similarity_score"))
        )
        score = self._safe_float(top_pair.get("similarity_score"))
        support = self._concrete_support_count(
            top_pair.get("engine_scores", {}), top_pair.get("external_evidence", [])
        )
        if score >= 0.85 and support >= 2:
            return "Substantial Similarity Supported By Evidence"
        if score >= 0.65 and support >= 1:
            return "Escalate For Formal Academic Integrity Review"
        if score >= 0.35:
            return "Instructor Review Required"
        return "No Action Recommended"

    def _case_decision_text(self, top_pair: Dict[str, Any], support: int) -> str:
        """Explain the case recommendation."""
        if not top_pair:
            return "No comparison pair exceeded the review threshold."

        file_a = escape(str(top_pair.get("file_a", "first file")))
        file_b = escape(str(top_pair.get("file_b", "second file")))
        score = self._safe_float(top_pair.get("similarity_score"))
        return (
            f"The strongest pair is {file_a} vs {file_b} with a fused review score "
            f"of {score:.1%}. The recommendation is based on {support} concrete "
            "evidence source(s), visible code spans, and any listed external-tool "
            "coverage. The score alone is not used as the decision record."
        )

    def _evidence_standard_label(self, pair: Dict[str, Any]) -> str:
        """Classify whether the evidence package is strong enough for escalation."""
        if not pair:
            return "No Evidence"
        score = self._safe_float(pair.get("similarity_score"))
        support = self._concrete_support_count(
            pair.get("engine_scores", {}), pair.get("external_evidence", [])
        )
        if score >= 0.85 and support >= 2:
            return "Evidence Standard Met"
        if score >= 0.65 and support >= 1:
            return "Evidence Review"
        return "Evidence Incomplete"

    def _concrete_support_count(
        self, engines: Dict[str, Any], external_evidence: List[Dict[str, Any]]
    ) -> int:
        """Count concrete evidence sources that support escalation."""
        concrete_engine_names = {
            "fingerprint",
            "winnowing",
            "ngram",
            "logic_flow",
            "moss",
            "jplag",
            "dolos",
            "pmd",
            "nicad",
            "sherlock",
        }
        count = 0
        for name, value in engines.items():
            if (
                str(name).lower() in concrete_engine_names
                and self._safe_float(value) >= 0.5
            ):
                count += 1
        for evidence in external_evidence:
            if self._safe_float(evidence.get("score")) >= 0.5:
                count += 1
        return count

    def _safe_float(self, value: Any) -> float:
        """Convert a value to float, defaulting to zero."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _render_engine_scores(self, engines: Dict[str, Any]) -> str:
        """Render the per-engine score table."""
        if not engines:
            return "<p class='note'>No engine breakdown was stored for this pair.</p>"

        rows = []
        for engine_name, engine_score in sorted(engines.items()):
            try:
                score = float(engine_score)
                display = f"{score:.1%}"
            except (TypeError, ValueError):
                display = escape(str(engine_score))
            rows.append(
                "<div class='signal-row'>"
                f"<span>{escape(str(engine_name).replace('_', ' ').title())}</span>"
                f"<strong>{display}</strong>"
                "</div>"
            )
        return "".join(rows)

    def _render_ai_details(self, ai_info: Dict[str, Any]) -> str:
        """Render pair-specific AI detection support."""
        if not ai_info:
            return ""

        ai_prob = float(ai_info.get("ai_probability", 0) or 0)
        ai_confidence = float(ai_info.get("confidence", 0) or 0)
        indicators = [
            escape(str(indicator)) for indicator in ai_info.get("indicators", [])[:3]
        ]
        indicator_text = ", ".join(indicators) if indicators else "No indicators listed"
        return (
            "<div class='signal-row'><span>AI probability</span>"
            f"<strong>{ai_prob:.1%}</strong></div>"
            "<div class='signal-row'><span>AI confidence</span>"
            f"<strong>{ai_confidence:.1%}</strong></div>"
            f"<p class='note'>AI indicators: {indicator_text}</p>"
        )

    def _render_external_evidence(self, evidence: List[Dict[str, Any]]) -> str:
        """Render independent external-tool evidence for a pair."""
        if not evidence:
            return ""

        rows = []
        for item in evidence:
            tool = escape(str(item.get("tool") or "External tool").upper())
            score = self._safe_float(item.get("score"))
            file_a_percent = item.get("file_a_percent")
            file_b_percent = item.get("file_b_percent")
            coverage = ""
            if file_a_percent is not None and file_b_percent is not None:
                coverage = (
                    f" · coverage {self._safe_float(file_a_percent):.1%} / "
                    f"{self._safe_float(file_b_percent):.1%}"
                )
            report_url = str(item.get("report_url") or "")
            link = (
                f" · <a href='{escape(report_url)}' target='_blank' rel='noopener noreferrer'>source report</a>"
                if report_url
                else ""
            )
            rows.append(
                "<div class='signal-row'>"
                f"<span>{tool}{coverage}{link}</span>"
                f"<strong>{score:.1%}</strong>"
                "</div>"
            )

        return (
            "<div class='signal' style='margin-bottom:12px;'>"
            "<h3>External Tool Evidence</h3>"
            f"{''.join(rows)}"
            "<p class='note'>External tool scores are reported as independent evidence. "
            "They are not treated as final academic decisions.</p>"
            "</div>"
        )

    def _render_pair_decision_box(self, pair: Dict[str, Any]) -> str:
        """Render pair-level recommendation and evidence sufficiency."""
        label = self._review_label(pair)
        support = self._concrete_support_count(
            pair.get("engine_scores", {}), pair.get("external_evidence", [])
        )
        standard = self._evidence_standard_label(pair)
        return f"""
        <div class="decision-box">
            <div class="label">Pair Recommendation</div>
            <h3>{escape(label)}</h3>
            <p class="note">Evidence status: {escape(standard)}. Concrete support sources: {support}. Use the copied-code spans, source hashes, and external-tool rows below as the decision record.</p>
        </div>
        """

    def _render_pair_provenance(self, pair: Dict[str, Any]) -> str:
        """Render file-level hashes for auditability."""
        file_a = str(pair.get("file_a", "File A"))
        file_b = str(pair.get("file_b", "File B"))
        hash_a = self._code_hash(str(pair.get("code_a") or ""))
        hash_b = self._code_hash(str(pair.get("code_b") or ""))
        return f"""
        <div class="signal" style="margin-bottom:12px;">
            <h3>Source File Provenance</h3>
            <div class="signal-row"><span>{escape(file_a)} SHA-256</span><strong class="hash">{escape(hash_a)}</strong></div>
            <div class="signal-row"><span>{escape(file_b)} SHA-256</span><strong class="hash">{escape(hash_b)}</strong></div>
        </div>
        """

    def _code_hash(self, code: str) -> str:
        """Return a stable hash for submitted source text."""
        if not code:
            return "unavailable"
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def _report_submission_hash(self, pairs: List[Dict[str, Any]]) -> str:
        """Return a stable hash over submitted code included in the report."""
        digest = hashlib.sha256()
        for pair in sorted(
            pairs,
            key=lambda item: (str(item.get("file_a", "")), str(item.get("file_b", ""))),
        ):
            digest.update(str(pair.get("file_a", "")).encode("utf-8"))
            digest.update(str(pair.get("code_a", "")).encode("utf-8"))
            digest.update(str(pair.get("file_b", "")).encode("utf-8"))
            digest.update(str(pair.get("code_b", "")).encode("utf-8"))
        return digest.hexdigest()

    def _pair_interpretation(self, score: float, engines: Dict[str, Any]) -> str:
        """Explain why the pair should be reviewed."""
        strong_engines = []
        for name, value in engines.items():
            try:
                if float(value) >= 0.7:
                    strong_engines.append(str(name).replace("_", " ").title())
            except (TypeError, ValueError):
                continue

        if strong_engines:
            return (
                f"The fused review score is {score:.1%}, with corroborating high signals "
                f"from {', '.join(strong_engines[:4])}. Strong agreement across "
                "different evidence types is more reliable than a single metric."
            )
        return (
            f"The fused review score is {score:.1%}. Treat this as a review cue and inspect "
            "the highlighted code spans before making an academic decision."
        )

    def _render_evidence_segments(
        self, code_a: str, code_b: str, file_a: Any, file_b: Any
    ) -> str:
        """Render concrete matching code spans for a pair."""
        if not code_a or not code_b:
            return (
                "<p class='note'>Submitted code was not available in this stored report. "
                "Run a new analysis to include line-level evidence.</p>"
            )

        matcher = CodeHighlighter(min_match_length=3, token_threshold=0.8)
        match_result = matcher.find_matching_segments(code_a, code_b)
        segments = match_result.segments[:3]
        if not segments:
            return (
                "<p class='note'>No exact three-line copied block was found. The score "
                "may be driven by token, AST, semantic, or external-tool evidence rather "
                "than a contiguous paste.</p>"
            )

        rendered = []
        for index, segment in enumerate(segments, 1):
            rendered.append(
                f"""
                <div class="section-body">
                    <h3>Evidence Block {index}: lines {segment.start_line_a}-{segment.end_line_a} match lines {segment.start_line_b}-{segment.end_line_b}</h3>
                    <p class="note">Clone type: {escape(segment.clone_type.value)} · local segment similarity {segment.similarity:.1%}</p>
                    <div class="evidence-grid">
                        {self._render_code_card(file_a, segment.text_a, segment.start_line_a)}
                        {self._render_code_card(file_b, segment.text_b, segment.start_line_b)}
                    </div>
                </div>
                """
            )
        return "".join(rendered)

    def _render_code_card(self, filename: Any, code: str, start_line: int) -> str:
        """Render a line-numbered code snippet."""
        rows = []
        for offset, line in enumerate(code.splitlines()):
            line_number = start_line + offset
            rows.append(
                "<tr class='matched'>"
                f"<td class='ln'>{line_number}</td>"
                f"<td class='src'>{escape(line)}</td>"
                "</tr>"
            )
        return (
            "<div class='code-card'>"
            f"<div class='code-title'>{escape(str(filename))}</div>"
            f"<table class='code'><tbody>{''.join(rows)}</tbody></table>"
            "</div>"
        )

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []
        summary = results.get("summary", {})

        suspicious_count = summary.get("suspicious_pairs", 0)
        total_pairs = summary.get("total_pairs", 0)

        if suspicious_count > 0:
            recommendations.append(
                f"Review {suspicious_count} suspicious pairs manually"
            )

        if total_pairs > 0 and suspicious_count / total_pairs > 0.3:
            recommendations.append(
                "High review rate detected - consider reviewing assignment design and evidence"
            )

        ai_data = results.get("ai_detection", {})
        if ai_data.get("flagged_count", 0) > 0:
            recommendations.append(
                f"Investigate {ai_data['flagged_count']} files for potential AI-generated code"
            )

        if not recommendations:
            recommendations.append("No significant issues detected")

        return recommendations
