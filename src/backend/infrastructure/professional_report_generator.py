"""Professional report generator for code similarity analysis.

Generates HTML, PDF, and JSON reports with:
- Side-by-side code highlighting
- Similarity heatmaps
- Risk level indicators
- AI detection results
- Professional formatting comparable to Turnitin

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
        """Generate a comprehensive, Turnitin-grade HTML originality report."""
        now = datetime.now()
        timestamp = now.strftime("%B %d, %Y at %H:%M UTC")
        timestamp_short = now.strftime("%Y-%m-%d %H:%M")
        summary = results.get("summary", {})
        pairs = results.get("pairs", [])

        # Resolve report_id from top-level or metadata
        report_id = str(
            results.get("report_id")
            or results.get("metadata", {}).get("report_id")
            or ""
        )
        if not report_id:
            report_id = (
                hashlib.sha256(timestamp_short.encode()).hexdigest()[:12].upper()
            )

        sorted_pairs = sorted(
            pairs, key=lambda p: p.get("similarity_score", 0), reverse=True
        )
        top_pair = sorted_pairs[0] if sorted_pairs else {}
        top_score = top_pair.get("similarity_score", 0)

        total_files = summary.get("total_files", 0)
        total_pairs_count = summary.get("total_pairs", 0)
        flagged = summary.get("suspicious_pairs", 0)
        avg_score = summary.get("average_similarity", 0)

        if top_score >= 0.85:
            risk_color = "#dc2626"
            risk_label = "Critical Risk"
            risk_bg = "#fef2f2"
        elif top_score >= 0.65:
            risk_color = "#ea580c"
            risk_label = "High Risk"
            risk_bg = "#fff7ed"
        elif top_score >= 0.40:
            risk_color = "#d97706"
            risk_label = "Medium Risk"
            risk_bg = "#fffbeb"
        else:
            risk_color = "#16a34a"
            risk_label = "Low Risk"
            risk_bg = "#f0fdf4"

        score_pct = f"{top_score:.0%}"
        avg_pct = f"{avg_score:.0%}"
        brand = self.branding_color

        selected_tools = results.get("selected_tools", [])
        tools_str = escape(
            ", ".join(str(t) for t in selected_tools)
            if selected_tools
            else "IntegrityDesk"
        )

        pairs_html = self._generate_pair_details(sorted_pairs)
        heatmap_html = self._generate_heatmap(sorted_pairs)
        ai_html = self._generate_ai_summary(results.get("ai_detection", {}))
        exec_html = self._generate_executive_decision(results, top_pair)
        custody_html = self._generate_chain_of_custody(
            results, timestamp_short, report_id
        )
        signoff_html = self._generate_signoff_section()

        css = (
            f"*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}"
            f"html{{font-size:14px;-webkit-text-size-adjust:100%}}"
            f"body{{background:#f0f4f8;color:#0f172a;font-family:system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased}}"
            f"a{{color:{brand};text-decoration:none}}"
            f".shell{{max-width:1020px;margin:0 auto;background:#fff;box-shadow:0 0 0 1px #e2e8f0,0 24px 64px rgba(15,23,42,.10)}}"
            f".conf-banner{{background:#0f172a;color:#94a3b8;text-align:center;padding:7px 16px;font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase}}"
            f".rpt-header{{background:linear-gradient(135deg,{brand} 0%,#1557b0 100%);color:#fff;padding:28px 36px 24px}}"
            f".rpt-header-top{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}}"
            f".rpt-brand{{display:flex;align-items:center;gap:14px}}"
            f".rpt-logo{{width:46px;height:46px;background:rgba(255,255,255,.18);border-radius:10px;display:grid;place-items:center;font-weight:900;font-size:17px;flex-shrink:0;border:1.5px solid rgba(255,255,255,.25)}}"
            f".rpt-title-block .eyebrow{{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.75);margin-bottom:4px}}"
            f".rpt-title-block h1{{font-size:22px;font-weight:800;letter-spacing:-.02em;line-height:1.2;color:#fff}}"
            f".rpt-title-block .subtitle{{font-size:12px;color:rgba(255,255,255,.75);margin-top:3px}}"
            f".rpt-meta-block{{text-align:right;font-size:11px;color:rgba(255,255,255,.80);line-height:1.7}}"
            f".rpt-meta-block strong{{color:#fff;font-weight:700}}"
            f".action-bar{{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}}"
            f".btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:7px;font-size:12px;font-weight:700;cursor:pointer;border:none;transition:all .18s;text-decoration:none;line-height:1}}"
            f".btn-dl{{background:rgba(255,255,255,.95);color:{brand}}}"
            f".btn-dl:hover{{background:#fff;box-shadow:0 4px 14px rgba(0,0,0,.18);transform:translateY(-1px)}}"
            f".btn-pr{{background:rgba(255,255,255,.12);color:#fff;border:1.5px solid rgba(255,255,255,.30)}}"
            f".btn-pr:hover{{background:rgba(255,255,255,.22)}}"
            f".score-banner{{background:{risk_bg};border-bottom:3px solid {risk_color};padding:20px 36px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}}"
            f".score-circle{{width:80px;height:80px;border-radius:50%;background:{risk_color};display:grid;place-items:center;flex-shrink:0;box-shadow:0 4px 16px rgba(0,0,0,.15)}}"
            f".score-circle span{{font-size:22px;font-weight:900;color:#fff;letter-spacing:-.03em}}"
            f".score-info h2{{font-size:18px;font-weight:800;color:{risk_color};margin-bottom:3px}}"
            f".score-info p{{font-size:12px;color:#475569;max-width:480px;line-height:1.5}}"
            f".score-chips{{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}}"
            f".chip{{display:inline-flex;flex-direction:column;align-items:center;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 14px;min-width:72px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}"
            f".chip-val{{font-size:18px;font-weight:800;color:#0f172a;line-height:1}}"
            f".chip-lbl{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-top:3px}}"
            f"main{{padding:28px 36px 48px}}"
            f".sec{{border:1px solid #e2e8f0;border-radius:10px;background:#fff;margin-top:20px;overflow:hidden}}"
            f".sec-head{{padding:14px 18px;border-bottom:1px solid #e2e8f0;background:#f8fafc;display:flex;justify-content:space-between;align-items:center;gap:12px}}"
            f".sec-head h2{{font-size:14px;font-weight:700;color:#0f172a;letter-spacing:-.01em}}"
            f".sec-body{{padding:18px}}"
            f".method-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}"
            f".method-card{{border-left:3px solid {brand};background:#f8fafc;padding:12px 14px;border-radius:0 6px 6px 0;font-size:12px;color:#334155;line-height:1.6}}"
            f".method-card strong{{display:block;color:#0f172a;margin-bottom:4px;font-size:12px}}"
            f".heat-row{{display:grid;grid-template-columns:32px 1fr 70px 90px;gap:10px;align-items:center;padding:9px 0;border-bottom:1px solid #f1f5f9}}"
            f".heat-row:last-child{{border-bottom:0}}"
            f".rank-badge{{width:28px;height:28px;border-radius:6px;display:grid;place-items:center;background:{brand};color:#fff;font-weight:800;font-size:11px}}"
            f".heat-files{{min-width:0}}"
            f".heat-files .pair-names{{font-size:12px;font-weight:600;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f".heat-bar{{height:6px;background:#e2e8f0;border-radius:999px;overflow:hidden;margin-top:5px}}"
            f".heat-bar span{{display:block;height:100%;border-radius:999px}}"
            f".heat-score{{font-size:14px;font-weight:800;color:#0f172a;text-align:right}}"
            f".badge{{display:inline-flex;align-items:center;border-radius:999px;padding:3px 9px;font-size:10px;font-weight:800;letter-spacing:.03em;white-space:nowrap}}"
            f".badge-critical,.badge-high{{background:#fee2e2;color:#991b1b}}"
            f".badge-review{{background:#dbeafe;color:#1e40af}}"
            f".badge-medium{{background:#fef3c7;color:#92400e}}"
            f".badge-low{{background:#dcfce7;color:#166534}}"
            f"details.finding{{border-top:1px solid #f1f5f9}}"
            f"details.finding:first-child{{border-top:0}}"
            f"details.finding summary{{cursor:pointer;list-style:none;padding:14px 18px;display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;user-select:none}}"
            f"details.finding summary::-webkit-details-marker{{display:none}}"
            f"details.finding summary::after{{content:'\\25B8 Show';color:{brand};font-size:11px;font-weight:800;white-space:nowrap}}"
            f"details.finding[open] summary::after{{content:'\\25BE Hide'}}"
            f"details.finding summary:hover{{background:#f8fafc}}"
            f".finding-body{{padding:0 18px 18px}}"
            f".signals{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}}"
            f".signal-card{{border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px}}"
            f".signal-card h3{{font-size:12px;font-weight:700;color:#0f172a;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #f1f5f9}}"
            f".sig-row{{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:4px 0;font-size:12px;border-bottom:1px solid #f8fafc}}"
            f".sig-row:last-child{{border-bottom:0}}"
            f".sig-row .engine-name{{color:#475569;text-transform:capitalize}}"
            f".sig-row .engine-score{{font-weight:700;color:#0f172a;flex-shrink:0}}"
            f".sig-bar-wrap{{flex:1;height:5px;background:#f1f5f9;border-radius:999px;overflow:hidden;margin:0 8px}}"
            f".sig-bar{{height:100%;border-radius:999px;background:{brand}}}"
            f".evidence-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}}"
            f".code-card{{border:1px solid #1e293b;border-radius:8px;overflow:hidden}}"
            f".code-card-header{{background:#1e293b;color:#e2e8f0;font-size:11px;font-weight:700;padding:8px 12px;display:flex;align-items:center;justify-content:space-between}}"
            f".code-card-header .file-name{{font-family:'SFMono-Regular',Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}"
            f".code-card-header .line-range{{font-size:10px;color:#94a3b8;flex-shrink:0;margin-left:8px}}"
            f"table.code-tbl{{width:100%;border-collapse:collapse;font:11.5px/1.55 'SFMono-Regular',Consolas,'Liberation Mono',monospace;background:#0f172a}}"
            f".code-tbl .ln{{width:44px;text-align:right;color:#475569;background:#111827;border-right:1px solid #1e293b;padding:0 8px;user-select:none;vertical-align:top}}"
            f".code-tbl .src{{color:#cbd5e1;white-space:pre-wrap;overflow-wrap:anywhere;padding:0 10px;vertical-align:top}}"
            f".code-tbl tr.matched .ln{{background:#3b2a0a;color:#fbbf24}}"
            f".code-tbl tr.matched .src{{background:#2d1f06;color:#fef3c7}}"
            f".prov-card{{border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;margin-bottom:10px}}"
            f".prov-card h3{{font-size:12px;font-weight:700;color:#0f172a;margin-bottom:8px}}"
            f".prov-row{{display:flex;justify-content:space-between;gap:12px;padding:4px 0;font-size:11px;border-bottom:1px solid #f8fafc}}"
            f".prov-row:last-child{{border-bottom:0}}"
            f".prov-row .prov-key{{color:#64748b;flex-shrink:0}}"
            f".prov-row .prov-hash{{font-family:'SFMono-Regular',Consolas,monospace;color:#334155;overflow-wrap:anywhere;text-align:right}}"
            f".sig-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:16px}}"
            f".sig-line{{border-top:1.5px solid #334155;padding-top:8px;color:#64748b;font-size:11px}}"
            f".ai-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}"
            f".note{{color:#64748b;font-size:12px;line-height:1.6}}"
            # Keep legacy class names so helper methods still work
            f".decision-panel{{border:1px solid #bfdbfe;background:#eff6ff;border-radius:8px;padding:18px}}"
            f".decision-title{{color:#1e3a8a;font-size:20px;font-weight:900;margin:4px 0 8px}}"
            f".two-col{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:14px}}"
            f".label{{color:#64748b;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}}"
            f".value{{margin-top:6px;font-size:24px;font-weight:800}}"
            f".card{{border:1px solid #e2e8f0;border-radius:8px;background:#fff;padding:16px}}"
            f".card.soft{{background:#f8fafc}}"
            f".section{{border:1px solid #e2e8f0;border-radius:8px;background:#fff;margin-top:18px;overflow:hidden}}"
            f".section-head{{padding:16px 18px;border-bottom:1px solid #e2e8f0;background:#f8fafc;display:flex;justify-content:space-between;gap:16px;align-items:center}}"
            f".section-body{{padding:18px}}"
            f".hash{{font:11px/1.45 'SFMono-Regular',Consolas,'Liberation Mono',monospace;color:#475569;overflow-wrap:anywhere}}"
            f".decision-box{{border:1px solid #c7d2fe;background:#eef2ff;border-radius:8px;padding:12px;margin-bottom:12px}}"
            f".signature-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:18px}}"
            f".signature-line{{border-top:1px solid #334155;padding-top:7px;color:#475569;font-size:12px}}"
            f".signal{{border:1px solid #e2e8f0;border-radius:8px;padding:12px}}"
            f".signal-row{{display:flex;justify-content:space-between;gap:12px;padding:5px 0;font-size:13px;border-bottom:1px solid #f1f5f9}}"
            f".signal-row:last-child{{border-bottom:0}}"
            f".audit-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}"
            f".audit-item{{border:1px solid #e2e8f0;border-radius:8px;padding:11px 12px;background:#fff}}"
            f"footer{{border-top:1px solid #e2e8f0;padding:16px 36px;font-size:11px;color:#94a3b8;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}"
            f"footer .footer-brand{{font-weight:700;color:#64748b}}"
            f"@media print{{body{{background:#fff}}.shell{{box-shadow:none;max-width:100%}}.action-bar,.no-print{{display:none!important}}details.finding summary::after{{display:none}}details.finding>.finding-body{{display:block!important}}details.finding{{page-break-inside:avoid}}.code-card{{page-break-inside:avoid}}.sec{{page-break-inside:avoid}}}}"
            f"@media(max-width:760px){{.rpt-header,.score-banner,main,footer{{padding-left:16px;padding-right:16px}}.method-grid,.signals,.evidence-grid,.sig-grid,.ai-grid,.two-col,.audit-grid{{grid-template-columns:1fr}}.score-chips{{margin-left:0}}.heat-row{{grid-template-columns:28px 1fr 60px}}}}"
        )

        js = (
            "function downloadPDF(el){"
            "var jobId=el.getAttribute('data-job-id');"
            "var url='/report/'+jobId+'/download-pdf';"
            "var orig=el.innerHTML;"
            "el.textContent='Generating\u2026';"
            "el.style.opacity='0.7';el.style.pointerEvents='none';"
            "fetch(url)"
            ".then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.blob();})"
            ".then(function(blob){"
            "var a=document.createElement('a');"
            "a.href=URL.createObjectURL(blob);"
            "a.download='integritydesk_report_'+jobId+'.pdf';"
            "document.body.appendChild(a);a.click();"
            "document.body.removeChild(a);URL.revokeObjectURL(a.href);})"
            ".catch(function(err){alert('PDF generation failed: '+err.message+'\\nTry the Print button instead.');})"
            ".finally(function(){el.innerHTML=orig;el.style.opacity='';el.style.pointerEvents='';});}"
        )

        return (
            f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"<title>IntegrityDesk Originality Report \u2014 {escape(self.institution_name)}</title>\n"
            f'<style>{css}</style>\n</head>\n<body>\n<div class="shell">\n\n'
            f'<div class="conf-banner">Confidential \u2014 Academic Integrity Evidence Report \u2014 Authorized Use Only</div>\n\n'
            f'<header class="rpt-header">\n'
            f'  <div class="rpt-header-top">\n'
            f'    <div class="rpt-brand">\n'
            f'      <div class="rpt-logo">ID</div>\n'
            f'      <div class="rpt-title-block">\n'
            f'        <div class="eyebrow">{escape(self.institution_name)} \u2014 Evidence Packet</div>\n'
            f"        <h1>IntegrityDesk Originality Report</h1>\n"
            f'        <div class="subtitle">Seven-engine fusion analysis &middot; {tools_str}</div>\n'
            f"      </div>\n    </div>\n"
            f'    <div class="rpt-meta-block">\n'
            f"      <div><strong>Generated</strong><br>{timestamp}</div>\n"
            f'      <div style="margin-top:6px"><strong>Report ID</strong><br>{escape(report_id)}</div>\n'
            f"    </div>\n  </div>\n"
            f'  <div class="action-bar no-print">\n'
            f'    <a href="/report/{escape(report_id)}/download-pdf"\n'
            f'       class="btn btn-dl"\n'
            f'       onclick="event.preventDefault();downloadPDF(this)"\n'
            f'       data-job-id="{escape(report_id)}">\n'
            f'      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>\n'
            f"      Download PDF\n    </a>\n"
            f'    <button class="btn btn-pr" onclick="window.print()">\n'
            f'      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>\n'
            f"      Print Report\n    </button>\n  </div>\n</header>\n\n"
            f'<div class="score-banner">\n'
            f'  <div class="score-circle"><span>{score_pct}</span></div>\n'
            f'  <div class="score-info">\n'
            f"    <h2>{risk_label} \u2014 Highest Pair Score</h2>\n"
            f'    <p>{escape(str(top_pair.get("file_a","—")))} vs {escape(str(top_pair.get("file_b","—")))}<br>\n'
            f"    Fused score from all active detection engines. This is a triage signal \u2014 review the evidence blocks before taking action.</p>\n"
            f"  </div>\n"
            f'  <div class="score-chips">\n'
            f'    <div class="chip"><span class="chip-val">{total_files}</span><span class="chip-lbl">Files</span></div>\n'
            f'    <div class="chip"><span class="chip-val">{total_pairs_count}</span><span class="chip-lbl">Pairs</span></div>\n'
            f'    <div class="chip"><span class="chip-val">{flagged}</span><span class="chip-lbl">Flagged</span></div>\n'
            f'    <div class="chip"><span class="chip-val">{avg_pct}</span><span class="chip-lbl">Avg Score</span></div>\n'
            f"  </div>\n</div>\n\n"
            f"<main>\n\n{exec_html}\n\n{custody_html}\n\n"
            f'<div class="sec">\n'
            f'  <div class="sec-head"><h2>Detection Methodology</h2><span class="note">Multi-engine corroboration</span></div>\n'
            f'  <div class="sec-body">\n'
            f'    <div class="method-grid">\n'
            f'      <div class="method-card"><strong>Lexical &amp; Token Analysis</strong>Token normalization, n-gram fingerprinting, and Winnowing find copied or lightly edited source even when spacing, comments, and variable names change.</div>\n'
            f'      <div class="method-card"><strong>Structural &amp; AST Analysis</strong>Abstract Syntax Tree and control-flow graph comparison detects structural plagiarism where code has been reorganized or identifiers renamed.</div>\n'
            f'      <div class="method-card"><strong>Semantic Embedding</strong>CodeBERT-style embeddings capture functional equivalence \u2014 code that does the same thing differently is still flagged even after heavy rewriting.</div>\n'
            f"    </div>\n  </div>\n</div>\n\n"
            f"{ai_html}\n\n"
            f'<div class="sec">\n'
            f'  <div class="sec-head"><h2>Similarity Heatmap \u2014 Top Pairs</h2><span class="note">Sorted by fused score</span></div>\n'
            f'  <div class="sec-body">{heatmap_html}</div>\n</div>\n\n'
            f'<div class="sec">\n'
            f'  <div class="sec-head"><h2>Detailed Findings &amp; Evidence</h2>'
            f'<span class="note">{len(pairs)} pair(s) \u2014 click a row to expand</span></div>\n'
            f"  {pairs_html}\n</div>\n\n"
            f"{signoff_html}\n\n</main>\n\n"
            f"<footer>\n"
            f'  <span class="footer-brand">IntegrityDesk</span>\n'
            f"  <span>Report ID: {escape(report_id)} &middot; {timestamp}</span>\n"
            f"  <span>Prepared as an institutional evidence packet. Decision fields require authorized sign-off.</span>\n"
            f"</footer>\n\n</div>\n<script>{js}</script>\n</body>\n</html>"
        )

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
        self, results: Dict[str, Any], timestamp: str, report_id: str = ""
    ) -> str:
        """Render chain-of-custody and reproducibility fields."""
        # Accept report_id as explicit param (preferred) or fall back to results
        if not report_id:
            report_id = str(
                results.get("report_id")
                or results.get("metadata", {}).get("report_id")
                or "—"
            )
        selected_tools = results.get("selected_tools", [])
        tool_names = ", ".join(str(tool) for tool in selected_tools) or "IntegrityDesk"
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
        <div class="sec">
            <div class="sec-head">
                <h2>Chain of Custody</h2>
                <span class="note">Reproducibility and audit metadata</span>
            </div>
            <div class="sec-body">
                <div class="audit-grid">
                    <div class="audit-item"><div class="a-lbl">Report ID</div><div class="a-val">{escape(report_id)}</div></div>
                    <div class="audit-item"><div class="a-lbl">Generated</div><div class="a-val">{escape(timestamp)}</div></div>
                    <div class="audit-item"><div class="a-lbl">Assignment Mode</div><div class="a-val">{escape(mode_name)}</div></div>
                    <div class="audit-item"><div class="a-lbl">Tools Used</div><div class="a-val">{escape(tool_names)}</div></div>
                    <div class="audit-item"><div class="a-lbl">Submission Set Hash</div><div class="a-val">{escape(submission_hash[:64])}</div></div>
                    <div class="audit-item"><div class="a-lbl">Evidence Policy</div><div class="a-val">Score is triage; decision is based on listed evidence blocks and external-tool support.</div></div>
                </div>
            </div>
        </div>
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
            return "<p class='note'>No pairs to display.</p>"

        rows = []
        for i, pair in enumerate(pairs[:20]):  # already sorted by caller
            score = pair.get("similarity_score", 0)
            file_a = pair.get("file_a", "Unknown")
            file_b = pair.get("file_b", "Unknown")
            review_label = self._review_label(pair)
            bar_color = (
                "#dc2626"
                if score >= 0.85
                else (
                    "#ea580c"
                    if score >= 0.65
                    else "#d97706" if score >= 0.40 else "#16a34a"
                )
            )
            rows.append(
                f'<div class="heat-row">'
                f'<div class="rank-badge">{i+1}</div>'
                f'<div class="heat-files">'
                f'<div class="pair-names">{escape(str(file_a))} &nbsp;vs&nbsp; {escape(str(file_b))}</div>'
                f'<div class="heat-bar"><span style="width:{score*100:.1f}%;background:{bar_color}"></span></div>'
                f"</div>"
                f'<strong class="heat-score">{score:.1%}</strong>'
                f'<span class="badge {self._risk_class(review_label)}">{escape(review_label)}</span>'
                f"</div>"
            )

        return "<div>" + "".join(rows) + "</div>"

    def _generate_pair_details(self, pairs: List[Dict[str, Any]]) -> str:
        """Generate detailed pair comparison sections."""
        if not pairs:
            return "<div class='sec-body note'>No pairs to display.</div>"

        details = []
        for pair in pairs:  # already sorted by caller
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
            signal_html = self._render_engine_scores_new(engines)
            external_html = self._render_external_evidence(external_evidence)
            decision_html = self._render_pair_decision_box(pair)
            provenance_html = self._render_pair_provenance(pair)

            details.append(
                f'<details class="finding">'
                f"<summary>"
                f'<div><strong style="font-size:13px">{escape(str(file_a))} vs {escape(str(file_b))}</strong>'
                f'<div class="note" style="font-size:11px;margin-top:2px">Click to expand evidence, engine scores, and code spans</div></div>'
                f'<strong style="font-size:15px">{score:.1%}</strong>'
                f'<span class="badge {self._risk_class(review_label)}">{escape(review_label)}</span>'
                f"</summary>"
                f'<div class="finding-body">'
                f"{decision_html}"
                f'<div class="signals">'
                f'<div class="signal-card"><h3>Engine Agreement</h3>{signal_html}</div>'
                f'<div class="signal-card"><h3>Interpretation</h3>'
                f'<p class="note">{self._pair_interpretation(score, engines)}</p>'
                f"{ai_html}</div>"
                f"</div>"
                f"{external_html}"
                f"{provenance_html}"
                f"{evidence_html}"
                f"</div></details>"
            )

        return "".join(details)

    def _risk_class(self, risk: Any) -> str:
        """Return a CSS badge class for a risk label."""
        normalized = str(risk or "").strip().lower()
        if "evidence" in normalized or "review" in normalized:
            return "badge-review"
        if normalized in {"critical", "high"}:
            return "badge-critical"
        if normalized == "medium":
            return "badge-medium"
        if normalized == "low":
            return "badge-low"
        return "badge-medium"

    def _render_engine_scores_new(self, engines: Dict[str, Any]) -> str:
        """Render per-engine scores with mini bar charts."""
        if not engines:
            return "<p class='note'>No engine breakdown stored for this pair.</p>"
        rows = []
        for name, val in sorted(engines.items(), key=lambda x: -self._safe_float(x[1])):
            try:
                score = float(val)
                pct = f"{score:.1%}"
                bar_w = f"{min(score * 100, 100):.1f}%"
            except (TypeError, ValueError):
                pct = escape(str(val))
                bar_w = "0%"
            rows.append(
                f'<div class="sig-row">'
                f'<span class="engine-name">{escape(str(name).replace("_", " "))}</span>'
                f'<div class="sig-bar-wrap"><div class="sig-bar" style="width:{bar_w}"></div></div>'
                f'<span class="engine-score">{pct}</span>'
                f"</div>"
            )
        return "".join(rows)

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
                "<p class='note' style='margin-top:10px'>Submitted code was not available in this stored report. "
                "Run a new analysis to include line-level evidence.</p>"
            )

        try:
            matcher = CodeHighlighter(min_match_length=3, token_threshold=0.8)
            match_result = matcher.find_matching_segments(code_a, code_b)
            segments = match_result.segments[:3]
        except Exception:
            segments = []

        if not segments:
            return (
                "<p class='note' style='margin-top:10px'>No exact three-line copied block was found. "
                "The score may be driven by token, AST, semantic, or external-tool evidence rather "
                "than a contiguous paste.</p>"
            )

        rendered = []
        for index, segment in enumerate(segments, 1):
            rendered.append(
                f'<div style="margin-top:14px">'
                f'<p style="font-size:12px;font-weight:700;color:#0f172a;margin-bottom:4px">'
                f"Evidence Block {index} &mdash; "
                f"lines {segment.start_line_a}&ndash;{segment.end_line_a} match "
                f"lines {segment.start_line_b}&ndash;{segment.end_line_b}</p>"
                f'<p class="note" style="margin-bottom:8px">Clone type: {escape(segment.clone_type.value)} '
                f"&middot; local similarity {segment.similarity:.1%}</p>"
                f'<div class="evidence-grid">'
                f"{self._render_code_card(file_a, segment.text_a, segment.start_line_a)}"
                f"{self._render_code_card(file_b, segment.text_b, segment.start_line_b)}"
                f"</div></div>"
            )
        return "".join(rendered)

    def _render_code_card(self, filename: Any, code: str, start_line: int) -> str:
        """Render a line-numbered code snippet with new CSS classes."""
        rows = []
        for offset, line in enumerate(code.splitlines()):
            line_number = start_line + offset
            rows.append(
                f"<tr class='matched'>"
                f"<td class='ln'>{line_number}</td>"
                f"<td class='src'>{escape(line)}</td>"
                f"</tr>"
            )
        return (
            f"<div class='code-card'>"
            f"<div class='code-card-header'>"
            f"<span class='file-name'>{escape(str(filename))}</span>"
            f"<span class='line-range'>L{start_line}&ndash;{start_line + len(rows) - 1}</span>"
            f"</div>"
            f"<table class='code-tbl'><tbody>{''.join(rows)}</tbody></table>"
            f"</div>"
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
