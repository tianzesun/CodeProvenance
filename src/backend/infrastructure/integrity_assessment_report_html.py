"""Integrity Assessment Report — HTML/PDF renderer.

Renders the IntegrityAssessmentReport dataclass into a self-contained
HTML document optimized for both screen viewing and PDF printing.
Uses inline CSS for portability (no external dependencies).
"""

from __future__ import annotations

import logging
from html import escape
from typing import Any

from src.backend.infrastructure.integrity_assessment_report import (
    IntegrityAssessmentReport,
    PLAGIARISM_TYPES,
    RISK_LEVELS,
    ENGINE_LABELS,
)

logger = logging.getLogger(__name__)


def render_integrity_report_html(report: IntegrityAssessmentReport) -> str:
    """Render a complete Integrity Assessment Report as self-contained HTML.

    Args:
        report: The fully populated IntegrityAssessmentReport.

    Returns:
        Complete HTML string ready for display or PDF conversion.
    """
    risk = RISK_LEVELS.get(report.risk_level, RISK_LEVELS["clean"])
    plagiarism_info = PLAGIARISM_TYPES.get(report.primary_plagiarism_type, {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Integrity Assessment Report — {escape(report.case_id)}</title>
<style>
{_build_css(risk)}
</style>
</head>
<body>
<div class="shell">

{_build_confidential_banner()}
{_build_cover_page(report, risk)}
{_build_executive_summary(report, risk)}
{_build_similarity_analysis(report)}
{_build_plagiarism_classification(report, plagiarism_info)}
{_build_ai_detection(report)}
{_build_historical_context(report)}
{_build_source_provenance(report)}
{_build_class_context(report)}
{_build_evidence_chain(report)}
{_build_student_response(report)}
{_build_policy_reference(report)}
{_build_appendix(report)}
{_build_footer(report)}

</div>
</body>
</html>"""


# ============================================================
# CSS
# ============================================================


def _build_css(risk: dict[str, Any]) -> str:
    color = risk.get("color", "#2563eb")
    return f"""
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{font-size:13px;-webkit-text-size-adjust:100%}}
body{{background:#f0f4f8;color:#0f172a;font-family:system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased}}
a{{color:{color};text-decoration:none}}
.shell{{max-width:1020px;margin:0 auto;background:#fff;box-shadow:0 0 0 1px #e2e8f0,0 24px 64px rgba(15,23,42,.10)}}

/* Print styles */
@media print{{
  body{{background:#fff}}
  .shell{{box-shadow:none;max-width:100%}}
  .no-print{{display:none!important}}
  @page{{size:A4;margin:15mm 12mm 18mm 12mm}}
}}

/* Confidential banner */
.conf-banner{{background:#0f172a;color:#94a3b8;text-align:center;padding:6px 16px;font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase}}

/* Cover page */
.cover{{background:linear-gradient(135deg,{color} 0%,#1557b0 100%);color:#fff;padding:32px 36px 28px}}
.cover-top{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}}
.cover-brand{{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;opacity:.85}}
.cover-title{{font-size:26px;font-weight:800;letter-spacing:-.02em;margin:12px 0 6px}}
.cover-subtitle{{font-size:13px;opacity:.8;margin-bottom:16px}}
.cover-meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:14px}}
.cover-meta-item{{background:rgba(255,255,255,.12);border-radius:8px;padding:10px 14px}}
.cover-meta-label{{font-size:9px;text-transform:uppercase;letter-spacing:.08em;opacity:.7;margin-bottom:2px}}
.cover-meta-value{{font-size:14px;font-weight:700}}

/* Risk banner */
.risk-banner{{margin:20px 0;padding:16px 20px;border-radius:12px;display:flex;align-items:center;gap:14px}}
.risk-icon{{font-size:28px;font-weight:900}}
.risk-label{{font-size:18px;font-weight:800}}
.risk-desc{{font-size:12px;opacity:.8;margin-top:2px}}
.risk-badge{{margin-left:auto;padding:6px 16px;border-radius:20px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}}

/* Section */
.section{{padding:24px 32px;border-top:1px solid #e2e8f0}}
.section-num{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{color};margin-bottom:4px}}
.section-title{{font-size:17px;font-weight:800;color:#0f172a;margin-bottom:14px}}

/* Cards */
.card-grid{{display:grid;gap:12px;margin:12px 0}}
.card-grid-2{{grid-template-columns:repeat(2,1fr)}}
.card-grid-3{{grid-template-columns:repeat(3,1fr)}}
.card-grid-4{{grid-template-columns:repeat(4,1fr)}}
.card{{border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;background:#fafbfc}}
.card-label{{font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600}}
.card-value{{font-size:22px;font-weight:800;margin:4px 0 2px;color:#0f172a}}
.card-sub{{font-size:11px;color:#64748b}}

/* Engine bars */
.engine-bar{{margin:8px 0}}
.engine-bar-header{{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px}}
.engine-bar-label{{font-weight:600;color:#334155}}
.engine-bar-score{{font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums}}
.engine-bar-track{{height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden}}
.engine-bar-fill{{height:100%;border-radius:4px;transition:width .6s}}

/* Tables */
table{{width:100%;border-collapse:collapse;font-size:12px;margin:10px 0}}
th{{background:#f1f5f9;padding:8px 10px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#475569;font-weight:700;border-bottom:2px solid #e2e8f0}}
td{{padding:7px 10px;border-bottom:1px solid #f1f5f9}}
tr:hover td{{background:#f8fafc}}

/* Code comparison */
.code-block{{background:#0f172a;color:#e2e8f0;border-radius:8px;padding:12px 14px;font-family:'JetBrains Mono','Fira Code',monospace;font-size:11px;line-height:1.6;overflow-x:auto;white-space:pre;margin:8px 0}}
.code-line-highlight{{background:rgba(234,88,12,.15);display:block}}
.code-header{{background:#1e293b;color:#94a3b8;padding:6px 12px;font-size:10px;font-weight:600;border-radius:8px 8px 0 0;text-transform:uppercase;letter-spacing:.06em}}
.code-diff{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.code-diff-left{{border-right:1px solid #334155}}

/* AI detection */
.ai-signal{{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #f1f5f9}}
.ai-signal-name{{width:140px;font-size:12px;font-weight:600;color:#334155}}
.ai-signal-bar{{flex:1;height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden}}
.ai-signal-fill{{height:100%;border-radius:3px}}
.ai-signal-value{{width:50px;text-align:right;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums}}

/* Evidence chain */
.hash{{font-family:'JetBrains Mono','Fira Code',monospace;font-size:11px;background:#f1f5f9;padding:4px 8px;border-radius:4px;word-break:break-all}}

/* Student response */
.response-area{{min-height:120px;border:1px dashed #cbd5e1;border-radius:8px;padding:12px;margin:10px 0;background:#fafbfc;color:#94a3b8;font-style:italic}}

/* Signature lines */
.sig-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px;margin:20px 0}}
.sig-line{{text-align:center}}
.sig-line hr{{border:none;border-top:1px solid #0f172a;margin:0 0 6px}}
.sig-label{{font-size:10px;color:#64748b}}

/* Footer */
.footer{{background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;font-size:10px;color:#94a3b8;display:flex;justify-content:space-between;align-items:center}}
"""


# ============================================================
# SECTION BUILDERS
# ============================================================


def _build_confidential_banner() -> str:
    return '<div class="conf-banner">Confidential — Academic Integrity Committee Only — FERPA Protected</div>'


def _build_cover_page(report: IntegrityAssessmentReport, risk: dict[str, Any]) -> str:
    return f"""
<div class="cover">
  <div class="cover-top">
    <div>
      <div class="cover-brand">{escape(report.institution_name)}</div>
      <div class="cover-title">Integrity Assessment Report</div>
      <div class="cover-subtitle">Multi-engine code forensics analysis with statistical confidence</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:10px;opacity:.7">Report ID</div>
      <div style="font-size:16px;font-weight:800;font-family:monospace">{escape(report.report_id)}</div>
    </div>
  </div>
  <div class="cover-meta">
    <div class="cover-meta-item">
      <div class="cover-meta-label">Case ID</div>
      <div class="cover-meta-value">{escape(report.case_id)}</div>
    </div>
    <div class="cover-meta-item">
      <div class="cover-meta-label">Assignment</div>
      <div class="cover-meta-value">{escape(report.assignment_name or 'N/A')}</div>
    </div>
    <div class="cover-meta-item">
      <div class="cover-meta-label">Course</div>
      <div class="cover-meta-value">{escape(report.course_name or 'N/A')}</div>
    </div>
    <div class="cover-meta-item">
      <div class="cover-meta-label">Student</div>
      <div class="cover-meta-value">{escape(report.student_display or 'Anonymous')}</div>
    </div>
    <div class="cover-meta-item">
      <div class="cover-meta-label">Generated</div>
      <div class="cover-meta-value">{escape(report.generated_at[:10])}</div>
    </div>
    <div class="cover-meta-item">
      <div class="cover-meta-label">Report Version</div>
      <div class="cover-meta-value">{escape(report.report_version)}</div>
    </div>
  </div>
</div>

<div class="section">
  <div class="risk-banner" style="background:{risk['bg']};border:1px solid {risk['border']}">
    <div class="risk-icon" style="color:{risk['color']}">{risk['icon']}</div>
    <div>
      <div class="risk-label" style="color:{risk['color']}">{escape(risk['label'])}</div>
      <div class="risk-desc">{escape(risk['description'])}</div>
    </div>
    <div class="risk-badge" style="background:{risk['color']};color:#fff">
      {report.overall_similarity:.1%} Similarity
    </div>
  </div>
</div>"""


def _build_executive_summary(report: IntegrityAssessmentReport, risk: dict[str, Any]) -> str:
    ci = report.confidence_interval
    return f"""
<div class="section">
  <div class="section-num">Section 2</div>
  <div class="section-title">Executive Summary</div>

  <div class="card-grid card-grid-4">
    <div class="card">
      <div class="card-label">Overall Similarity</div>
      <div class="card-value" style="color:{risk['color']}">{report.overall_similarity:.1%}</div>
      <div class="card-sub">Highest pair score</div>
    </div>
    <div class="card">
      <div class="card-label">Confidence Interval</div>
      <div class="card-value">{ci.lower:.1%} – {ci.upper:.1%}</div>
      <div class="card-sub">95% CI ({escape(ci.method)})</div>
    </div>
    <div class="card">
      <div class="card-label">Pairs Analyzed</div>
      <div class="card-value">{len(report.pair_results)}</div>
      <div class="card-sub">File comparison pairs</div>
    </div>
    <div class="card">
      <div class="card-label">Files Analyzed</div>
      <div class="card-value">{len(report.files)}</div>
      <div class="card-sub">Source files</div>
    </div>
  </div>

  <div style="margin-top:14px;padding:14px 16px;background:#f8fafc;border-radius:8px;border-left:3px solid {risk['color']}">
    <div style="font-size:13px;line-height:1.6;color:#334155">{escape(report.executive_summary)}</div>
  </div>

  <div style="margin-top:10px;padding:12px 16px;background:#fff;border:1px solid #e2e8f0;border-radius:8px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600;margin-bottom:4px">Recommended Action</div>
    <div style="font-size:12px;color:#334155;line-height:1.5">{escape(report.recommended_action)}</div>
  </div>
</div>"""


def _build_similarity_analysis(report: IntegrityAssessmentReport) -> str:
    engine_bars = ""
    for es in report.engine_scores:
        pct = es.score * 100
        bar_color = (
            "#dc2626" if es.score >= 0.7 else
            "#ea580c" if es.score >= 0.5 else
            "#d97706" if es.score >= 0.3 else
            "#2563eb"
        )
        engine_bars += f"""
    <div class="engine-bar">
      <div class="engine-bar-header">
        <span class="engine-bar-label">{escape(es.label or es.engine)}</span>
        <span class="engine-bar-score">{pct:.1f}%</span>
      </div>
      <div class="engine-bar-track">
        <div class="engine-bar-fill" style="width:{pct:.1f}%;background:{bar_color}"></div>
      </div>
    </div>"""

    # Pair results table
    pair_rows = ""
    for i, pr in enumerate(report.pair_results[:20]):
        score_pct = f"{pr.overall_score:.1%}"
        score_color = (
            "#dc2626" if pr.overall_score >= 0.7 else
            "#ea580c" if pr.overall_score >= 0.5 else
            "#d97706" if pr.overall_score >= 0.3 else
            "#16a34a"
        )
        pair_rows += f"""
      <tr>
        <td style="font-weight:600">{escape(pr.file_a)}</td>
        <td style="font-weight:600">{escape(pr.file_b)}</td>
        <td style="color:{score_color};font-weight:700">{score_pct}</td>
        <td>{pr.confidence:.1%}</td>
        <td>{len(pr.matched_blocks)}</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-num">Section 3</div>
  <div class="section-title">Similarity Analysis</div>

  <div style="margin-bottom:16px">
    <div style="font-size:12px;font-weight:700;color:#334155;margin-bottom:8px">Engine Score Breakdown</div>
    {engine_bars if engine_bars else '<div style="color:#94a3b8;font-size:12px">No per-engine scores available</div>'}
  </div>

  <div style="font-size:12px;font-weight:700;color:#334155;margin:16px 0 8px">Pairwise Comparison Results</div>
  <table>
    <thead>
      <tr>
        <th>File A</th>
        <th>File B</th>
        <th>Similarity</th>
        <th>Confidence</th>
        <th>Matched Blocks</th>
      </tr>
    </thead>
    <tbody>
      {pair_rows if pair_rows else '<tr><td colspan="5" style="color:#94a3b8;text-align:center;padding:20px">No pairwise results available</td></tr>'}
    </tbody>
  </table>
</div>"""


def _build_plagiarism_classification(
    report: IntegrityAssessmentReport, plagiarism_info: dict[str, Any]
) -> str:
    breakdown_rows = ""
    for ptype, ratio in sorted(report.plagiarism_type_breakdown.items(), key=lambda x: -x[1]):
        info = PLAGIARISM_TYPES.get(ptype, {})
        breakdown_rows += f"""
      <tr>
        <td style="font-weight:700">{escape(ptype)}</td>
        <td>{escape(info.get('name', ''))}</td>
        <td>{escape(info.get('description', ''))}</td>
        <td style="font-weight:700">{ratio:.1%}</td>
      </tr>"""

    current_info = PLAGIARISM_TYPES.get(report.primary_plagiarism_type, {})

    return f"""
<div class="section">
  <div class="section-num">Section 4</div>
  <div class="section-title">Plagiarism Type Classification</div>

  <div style="padding:14px 16px;background:#f8fafc;border-radius:8px;margin-bottom:14px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600;margin-bottom:4px">Primary Classification</div>
    <div style="font-size:16px;font-weight:800;color:#0f172a">
      {escape(report.primary_plagiarism_type)} — {escape(current_info.get('name', 'Unknown'))}
    </div>
    <div style="font-size:12px;color:#64748b;margin-top:4px">
      {escape(current_info.get('description', ''))}
    </div>
  </div>

  <table>
    <thead>
      <tr><th>Type</th><th>Name</th><th>Description</th><th>Ratio</th></tr>
    </thead>
    <tbody>
      {breakdown_rows if breakdown_rows else '<tr><td colspan="4" style="color:#94a3b8;text-align:center">No classification data</td></tr>'}
    </tbody>
  </table>
</div>"""


def _build_ai_detection(report: IntegrityAssessmentReport) -> str:
    ai = report.ai_detection_summary
    if not ai.get("available"):
        return ""

    flag_color = "#dc2626" if ai.get("flagged_count", 0) > 0 else "#16a34a"

    signals_html = ""
    for f in report.files:
        if not f.ai_signals:
            continue
        for signal_name, signal_val in sorted(f.ai_signals.items(), key=lambda x: -x[1]):
            pct = float(signal_val) * 100
            bar_color = "#dc2626" if pct >= 70 else "#ea580c" if pct >= 40 else "#2563eb"
            signals_html += f"""
      <div class="ai-signal">
        <div class="ai-signal-name">{escape(signal_name.replace('_', ' ').title())}</div>
        <div class="ai-signal-bar">
          <div class="ai-signal-fill" style="width:{pct:.1f}%;background:{bar_color}"></div>
        </div>
        <div class="ai-signal-value">{pct:.0f}%</div>
      </div>"""

    file_rows = ""
    for f in report.files:
        prob_pct = f"{f.ai_probability:.1%}"
        prob_color = "#dc2626" if f.ai_probability >= 0.7 else "#ea580c" if f.ai_probability >= 0.4 else "#16a34a"
        file_rows += f"""
      <tr>
        <td style="font-weight:600">{escape(f.filename)}</td>
        <td style="color:{prob_color};font-weight:700">{prob_pct}</td>
        <td>{f.ai_confidence:.1%}</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-num">Section 5</div>
  <div class="section-title">AI-Generated Code Detection</div>

  <div class="card-grid card-grid-3">
    <div class="card">
      <div class="card-label">Files Flagged</div>
      <div class="card-value" style="color:{flag_color}">{ai.get('flagged_count', 0)}</div>
      <div class="card-sub">of {ai.get('total_files', 0)} files</div>
    </div>
    <div class="card">
      <div class="card-label">Average AI Probability</div>
      <div class="card-value">{ai.get('average_probability', 0):.1%}</div>
      <div class="card-sub">Across all files</div>
    </div>
    <div class="card">
      <div class="card-label">Maximum AI Probability</div>
      <div class="card-value">{ai.get('max_probability', 0):.1%}</div>
      <div class="card-sub">Highest single file</div>
    </div>
  </div>

  <div style="margin-top:14px;font-size:12px;font-weight:700;color:#334155;margin-bottom:8px">Per-File AI Detection Scores</div>
  <table>
    <thead><tr><th>File</th><th>AI Probability</th><th>Confidence</th></tr></thead>
    <tbody>{file_rows}</tbody>
  </table>

  {f'<div style="margin-top:14px;font-size:12px;font-weight:700;color:#334155;margin-bottom:8px">Signal Breakdown</div>{signals_html}' if signals_html else ''}

  <div style="margin-top:12px;padding:10px 14px;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;font-size:11px;color:#92400e">
    <strong>Limitation:</strong> AI detection is probabilistic and should not be used as the sole basis for adverse actions.
    False positives can occur, especially with code that uses common patterns, auto-formatters, or code completion tools.
  </div>
</div>"""


def _build_historical_context(report: IntegrityAssessmentReport) -> str:
    h = report.historical
    if h.prior_submissions == 0 and not h.cross_assignment_matches:
        return ""

    match_rows = ""
    for m in h.cross_assignment_matches[:10]:
        match_rows += f"""
      <tr>
        <td>{escape(m.get('assignment', ''))}</td>
        <td>{m.get('similarity', 0):.1%}</td>
        <td>{escape(m.get('course', ''))}</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-num">Section 6</div>
  <div class="section-title">Historical Context</div>

  <div class="card-grid card-grid-3">
    <div class="card">
      <div class="card-label">Prior Submissions</div>
      <div class="card-value">{h.prior_submissions}</div>
    </div>
    <div class="card">
      <div class="card-label">Style Consistency</div>
      <div class="card-value">{h.style_consistency:.1%}</div>
    </div>
    <div class="card">
      <div class="card-label">Repeat Pattern</div>
      <div class="card-value" style="color:{'#dc2626' if h.repeat_offender else '#16a34a'}">
        {'Yes' if h.repeat_offender else 'No'}
      </div>
    </div>
  </div>

  {f'''
  <div style="margin-top:14px;font-size:12px;font-weight:700;color:#334155;margin-bottom:8px">Cross-Assignment Matches</div>
  <table>
    <thead><tr><th>Assignment</th><th>Similarity</th><th>Course</th></tr></thead>
    <tbody>{match_rows}</tbody>
  </table>
  ''' if match_rows else ''}
</div>"""


def _build_source_provenance(report: IntegrityAssessmentReport) -> str:
    if not report.sources:
        return ""

    rows = ""
    for s in report.sources:
        rows += f"""
      <tr>
        <td style="font-weight:600">{escape(s.filename)}</td>
        <td>{escape(s.language)}</td>
        <td>{s.line_count}</td>
        <td>{escape(s.editor)}</td>
        <td>{escape(s.last_modified)}</td>
        <td class="hash" style="font-size:9px">{escape(s.sha256[:16])}…</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-num">Section 7</div>
  <div class="section-title">Source Provenance</div>
  <table>
    <thead><tr><th>File</th><th>Language</th><th>Lines</th><th>Editor</th><th>Last Modified</th><th>SHA-256</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def _build_class_context(report: IntegrityAssessmentReport) -> str:
    cc = report.class_context
    if cc.total_students == 0 and cc.total_pairs == 0:
        return ""

    return f"""
<div class="section">
  <div class="section-num">Section 8</div>
  <div class="section-title">Class Context</div>

  <div class="card-grid card-grid-4">
    <div class="card">
      <div class="card-label">Total Students</div>
      <div class="card-value">{cc.total_students}</div>
    </div>
    <div class="card">
      <div class="card-label">Average Similarity</div>
      <div class="card-value">{cc.average_similarity:.1%}</div>
    </div>
    <div class="card">
      <div class="card-label">Percentile Rank</div>
      <div class="card-value">{cc.percentile_rank:.0f}th</div>
    </div>
    <div class="card">
      <div class="card-label">Flagged Ratio</div>
      <div class="card-value">{cc.flagged_ratio:.1%}</div>
    </div>
  </div>
</div>"""


def _build_evidence_chain(report: IntegrityAssessmentReport) -> str:
    engine_version_rows = ""
    for engine, version in report.engine_versions.items():
        engine_version_rows += f"""
      <tr>
        <td style="font-weight:600">{escape(engine)}</td>
        <td class="hash">{escape(version)}</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-num">Section 9</div>
  <div class="section-title">Evidence Chain & Reproducibility</div>

  <div style="margin-bottom:12px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600;margin-bottom:4px">Report Integrity Hash (SHA-256)</div>
    <div class="hash">{escape(report.evidence_chain_hash)}</div>
  </div>

  <div style="margin-bottom:12px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600;margin-bottom:4px">Analysis Timestamp</div>
    <div style="font-size:12px;color:#334155">{escape(report.analysis_timestamp or report.generated_at)}</div>
  </div>

  {f'''
  <div style="font-size:12px;font-weight:700;color:#334155;margin-bottom:8px">Engine Versions</div>
  <table>
    <thead><tr><th>Engine</th><th>Version / Hash</th></tr></thead>
    <tbody>{engine_version_rows}</tbody>
  </table>
  ''' if engine_version_rows else ''}
</div>"""


def _build_student_response(report: IntegrityAssessmentReport) -> str:
    return f"""
<div class="section">
  <div class="section-num">Section 10</div>
  <div class="section-title">Student Response</div>

  <div style="font-size:11px;color:#64748b;margin-bottom:8px">
    The student has the right to respond to the findings in this report.
    Their response should be documented here before any final determination is made.
  </div>

  <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600;margin-bottom:4px">Student's Response</div>
  <div class="response-area">{escape(report.student_response) if report.student_response else 'Student response to be recorded here after meeting.'}</div>

  <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600;margin-bottom:4px;margin-top:12px">Faculty Response to Student's Explanation</div>
  <div class="response-area">{escape(report.faculty_response) if report.faculty_response else 'Faculty response to be recorded here.'}</div>

  <div style="margin-top:12px">
    <span style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:600">Meeting Date: </span>
    <span style="font-size:12px;color:#334155">{escape(report.meeting_date) if report.meeting_date else '___/___/______'}</span>
  </div>
</div>"""


def _build_policy_reference(report: IntegrityAssessmentReport) -> str:
    policy_items = ""
    for p in report.policy_references:
        policy_items += f"<li style='margin:4px 0;font-size:12px;color:#334155'>{escape(p)}</li>"

    sanctions_rows = ""
    for s in report.sanctions_matrix:
        sanctions_rows += f"""
      <tr>
        <td style="font-weight:600">{escape(s.get('offense', ''))}</td>
        <td>{escape(s.get('range', ''))}</td>
        <td>{escape(s.get('note', ''))}</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-num">Section 11</div>
  <div class="section-title">Policy Reference & Sanctions Matrix</div>

  <div style="font-size:12px;font-weight:700;color:#334155;margin-bottom:6px">Applicable Policies</div>
  <ul style="padding-left:18px;margin-bottom:16px">{policy_items}</ul>

  <div style="font-size:12px;font-weight:700;color:#334155;margin-bottom:6px">Sanctions Matrix</div>
  <table>
    <thead><tr><th>Offense</th><th>Potential Range</th><th>Notes</th></tr></thead>
    <tbody>{sanctions_rows}</tbody>
  </table>
</div>"""


def _build_appendix(report: IntegrityAssessmentReport) -> str:
    if not report.full_code_comparison:
        return ""

    blocks_html = ""
    shown = 0
    for pr in report.pair_results:
        for mb in pr.matched_blocks:
            if shown >= 20:
                break
            if not mb.lines_a and not mb.lines_b:
                continue
            blocks_html += f"""
    <div style="margin:12px 0">
      <div class="code-header">
        {escape(mb.file_a)} ↔ {escape(mb.file_b)}
        {f' | Similarity: {mb.similarity:.1%}' if mb.similarity else ''}
        {f' | Type: {escape(mb.clone_type)}' if mb.clone_type else ''}
      </div>
      <div class="code-diff">
        <div class="code-diff-left code-block">{escape(mb.lines_a) if mb.lines_a else '(no code)'}</div>
        <div class="code-block">{escape(mb.lines_b) if mb.lines_b else '(no code)'}</div>
      </div>
    </div>"""
            shown += 1

    if not blocks_html:
        return ""

    return f"""
<div class="section">
  <div class="section-num">Section 12</div>
  <div class="section-title">Appendix — Code Comparison Evidence</div>
  <div style="font-size:11px;color:#64748b;margin-bottom:10px">
    Showing top {min(shown, 20)} matched code blocks with highest similarity scores.
  </div>
  {blocks_html}
</div>"""


def _build_footer(report: IntegrityAssessmentReport) -> str:
    return f"""
<div class="footer">
  <div>IntegrityDesk v{escape(report.report_version)} — {escape(report.institution_name)}</div>
  <div>Generated {escape(report.generated_at[:19])} — Hash {escape(report.evidence_chain_hash[:16])}…</div>
</div>"""
