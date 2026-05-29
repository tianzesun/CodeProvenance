"""AI Detector originality report generator.

Builds a Turnitin-grade HTML report for AI-generated code detection results.
Kept in a separate module so the CSS/HTML strings never conflict with
Python 3.12 f-string parsing rules.
"""

from datetime import datetime
from html import escape as _esc
from typing import Any, Dict


def _pct(value: Any) -> str:
    """Format a 0-1 float as a percentage string."""
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "0%"


def _coerce(value: Any) -> float:
    """Safe float coercion."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_SIGNAL_LABELS: Dict[str, str] = {
    "perplexity": "Token Entropy",
    "burstiness": "Code Burstiness",
    "stylometry": "Style Profile",
    "pattern_library": "LLM Fingerprints",
    "structural_entropy": "AST Uniformity",
    "vocabulary_richness": "Vocabulary Diversity",
    "whitespace_rhythm": "Whitespace Rhythm",
    "docstring_density": "Docstring Density",
}

# Plain CSS — no f-string, no {{ }} escaping needed
_BASE_CSS = (
    "*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}"
    "html{font-size:14px}"
    "body{background:#f0f4f8;color:#0f172a;"
    "font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;line-height:1.55}"
    ".shell{max-width:960px;margin:0 auto;background:#fff;"
    "box-shadow:0 0 0 1px #e2e8f0,0 24px 64px rgba(15,23,42,.10)}"
    ".conf-banner{background:#0f172a;color:#94a3b8;text-align:center;"
    "padding:7px 16px;font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase}"
    ".rpt-header{background:linear-gradient(135deg,#2563eb 0%,#1557b0 100%);"
    "color:#fff;padding:28px 36px 24px}"
    ".chips{display:flex;gap:10px;flex-wrap:wrap;margin-left:auto}"
    ".chip{display:inline-flex;flex-direction:column;align-items:center;"
    "background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 14px;min-width:72px}"
    ".chip-val{font-size:18px;font-weight:800;color:#0f172a;line-height:1}"
    ".chip-lbl{font-size:9px;font-weight:700;text-transform:uppercase;"
    "letter-spacing:.08em;color:#64748b;margin-top:3px}"
    "main{padding:24px 36px 48px}"
    ".sec{border:1px solid #e2e8f0;border-radius:10px;background:#fff;"
    "margin-top:20px;overflow:hidden}"
    ".sec-head{padding:12px 18px;border-bottom:1px solid #e2e8f0;background:#f8fafc;"
    "display:flex;justify-content:space-between;align-items:center}"
    ".sec-head h2{font-size:13px;font-weight:700;color:#0f172a}"
    ".sec-body{padding:18px}"
    ".notice{border:1px solid #bfdbfe;background:#eff6ff;border-radius:8px;"
    "padding:12px 16px;color:#1e40af;font-size:12px;line-height:1.6;margin-top:20px}"
    "footer{border-top:1px solid #e2e8f0;padding:14px 36px;font-size:11px;"
    "color:#94a3b8;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}"
    "@media print{"
    "body{background:#fff}"
    ".shell{box-shadow:none;max-width:100%}"
    ".no-print{display:none!important}"
    "}"
    "@media(max-width:640px){"
    ".rpt-header,.score-banner,main,footer{padding-left:16px;padding-right:16px}"
    "}"
)


def _bar(value: float, color: str) -> str:
    """Render a small inline progress bar."""
    w = int(value * 100)
    return (
        "<div style='display:flex;align-items:center;gap:8px'>"
        "<div style='flex:1;height:6px;background:#e2e8f0;border-radius:999px;overflow:hidden'>"
        "<div style='width:"
        + str(w)
        + "%;height:100%;background:"
        + color
        + ";border-radius:999px'></div>"
        "</div>"
        "<span style='font-size:12px;font-weight:700;color:#0f172a;"
        "min-width:36px;text-align:right'>" + _pct(value) + "</span>"
        "</div>"
    )


def _risk_color(score: float) -> str:
    """Return hex color for a risk score."""
    if score >= 0.70:
        return "#dc2626"
    if score >= 0.40:
        return "#d97706"
    return "#16a34a"


def _signal_rows(signal_summary: Dict[str, Any]) -> str:
    """Build HTML rows for the signal summary table."""
    rows = ""
    for key, data in signal_summary.items():
        label = _SIGNAL_LABELS.get(key, key.replace("_", " ").title())
        avg = _coerce(data.get("average") if isinstance(data, dict) else data)
        peak = _coerce(data.get("peak") if isinstance(data, dict) else data)
        color = _risk_color(avg)
        rows += (
            "<tr>"
            "<td style='padding:9px 12px;font-size:12px;color:#334155'>"
            + _esc(label)
            + "</td>"
            "<td style='padding:9px 12px'>" + _bar(avg, color) + "</td>"
            "<td style='padding:9px 12px;font-size:12px;font-weight:700;"
            "color:#0f172a;text-align:right'>" + _pct(peak) + "</td>"
            "</tr>"
        )
    return rows


def _submission_card(entry: Dict[str, Any]) -> str:
    """Build HTML for one submission evidence card."""
    name = _esc(str(entry.get("name") or "Submission"))
    prob = _coerce(entry.get("ai_probability"))
    conf = _coerce(entry.get("confidence"))
    status = _esc(str(entry.get("status") or "Review Signal"))
    language = _esc(str(entry.get("language") or ""))
    indicators = entry.get("indicators") or []
    signals = entry.get("signals") or {}
    annotated = entry.get("annotated_snippet") or []

    border = _risk_color(prob)
    if prob >= 0.70:
        bg = "#fef2f2"
        badge_bg = "#fee2e2"
        badge_fg = "#991b1b"
    elif prob >= 0.40:
        bg = "#fffbeb"
        badge_bg = "#fef3c7"
        badge_fg = "#92400e"
    else:
        bg = "#f0fdf4"
        badge_bg = "#dcfce7"
        badge_fg = "#166534"

    # Indicator pills
    pills = "".join(
        "<span style='display:inline-block;background:#f1f5f9;"
        "border:1px solid #e2e8f0;border-radius:999px;"
        "padding:3px 10px;font-size:11px;color:#475569;margin:2px'>"
        + _esc(str(ind))
        + "</span>"
        for ind in indicators[:5]
    )

    # Signal mini-bars
    sig_html = ""
    for sig_key, sig_val in list(signals.items())[:6]:
        lbl = _SIGNAL_LABELS.get(sig_key, sig_key.replace("_", " ").title())
        sv = _coerce(sig_val)
        color = _risk_color(sv)
        w = int(sv * 100)
        sig_html += (
            "<div style='margin-bottom:6px'>"
            "<div style='display:flex;justify-content:space-between;"
            "font-size:11px;color:#64748b;margin-bottom:3px'>"
            "<span>" + _esc(lbl) + "</span>"
            "<span style='font-weight:700;color:#0f172a'>" + _pct(sv) + "</span>"
            "</div>"
            "<div style='height:5px;background:#e2e8f0;border-radius:999px;overflow:hidden'>"
            "<div style='width:"
            + str(w)
            + "%;height:100%;background:"
            + color
            + ";border-radius:999px'></div>"
            "</div>"
            "</div>"
        )

    # Annotated code snippet
    code_rows = ""
    for line_info in annotated[:30]:
        ln_num = int(line_info.get("line", 0))
        ln_text = _esc(str(line_info.get("text", "")))
        flagged = bool(line_info.get("flagged"))
        row_bg = "#2d1f06" if flagged else "#0f172a"
        ln_color = "#fbbf24" if flagged else "#475569"
        text_color = "#fef3c7" if flagged else "#cbd5e1"
        code_rows += (
            "<tr style='background:" + row_bg + "'>"
            "<td style='width:40px;text-align:right;color:"
            + ln_color
            + ";background:#111827;border-right:1px solid #1e293b;"
            "padding:1px 8px;font-size:11px;user-select:none;vertical-align:top'>"
            + str(ln_num)
            + "</td>"
            "<td style='color:"
            + text_color
            + ";white-space:pre-wrap;overflow-wrap:anywhere;"
            "padding:1px 10px;font-size:11px;vertical-align:top'>" + ln_text + "</td>"
            "</tr>"
        )

    snippet = ""
    if code_rows:
        snippet = (
            "<div style='margin-top:14px;border:1px solid #1e293b;"
            "border-radius:8px;overflow:hidden'>"
            "<div style='background:#1e293b;color:#94a3b8;font-size:10px;"
            "font-weight:700;padding:7px 12px;display:flex;"
            "justify-content:space-between'>"
            "<span>" + name + "</span>"
            "<span style='color:#64748b'>Amber lines matched LLM fingerprints</span>"
            "</div>"
            "<table style='width:100%;border-collapse:collapse;"
            "font-family:SFMono-Regular,Consolas,monospace;background:#0f172a'>"
            + code_rows
            + "</table>"
            "</div>"
        )

    return (
        "<div style='border:1px solid " + border + ";border-radius:12px;"
        "background:" + bg + ";margin-bottom:16px;overflow:hidden'>"
        "<div style='padding:14px 18px;display:flex;align-items:flex-start;"
        "justify-content:space-between;gap:16px;flex-wrap:wrap'>"
        "<div>"
        "<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>"
        "<span style='font-size:14px;font-weight:700;color:#0f172a'>" + name + "</span>"
        "<span style='background:"
        + badge_bg
        + ";color:"
        + badge_fg
        + ";border-radius:999px;padding:3px 10px;font-size:11px;font-weight:800'>"
        + status
        + "</span>"
        + (
            "<span style='background:#f1f5f9;color:#64748b;border-radius:999px;"
            "padding:3px 10px;font-size:11px'>" + language + "</span>"
            if language
            else ""
        )
        + "</div>"
        "<div style='margin-top:8px;display:flex;gap:16px;flex-wrap:wrap'>"
        "<div>"
        "<div style='font-size:10px;font-weight:700;text-transform:uppercase;"
        "letter-spacing:.08em;color:#64748b'>AI Probability</div>"
        "<div style='font-size:22px;font-weight:900;color:"
        + border
        + "'>"
        + _pct(prob)
        + "</div>"
        "</div>"
        "<div>"
        "<div style='font-size:10px;font-weight:700;text-transform:uppercase;"
        "letter-spacing:.08em;color:#64748b'>Confidence</div>"
        "<div style='font-size:22px;font-weight:900;color:#0f172a'>"
        + _pct(conf)
        + "</div>"
        "</div>"
        "</div>"
        + ("<div style='margin-top:10px'>" + pills + "</div>" if pills else "")
        + "</div>"
        "<div style='min-width:200px;flex:1;max-width:320px'>" + sig_html + "</div>"
        "</div>" + snippet + "</div>"
    )


def build_ai_originality_report_html(job: Dict[str, Any]) -> str:
    """Build a Turnitin-grade printable AI Detector originality report.

    Args:
        job: The job dict from _jobs / job.json, must have job_type == 'ai_detector'.

    Returns:
        Complete HTML string ready for WeasyPrint or browser rendering.
    """
    ai = job.get("ai_detection") if isinstance(job.get("ai_detection"), dict) else {}
    submissions = (
        ai.get("submissions") if isinstance(ai.get("submissions"), list) else []
    )
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M UTC")
    report_id = str(job.get("id") or "")
    assignment = _esc(str(job.get("assignment_name") or "AI Generated Code Review"))
    course = _esc(str(job.get("course_name") or "Course"))
    total_files = int(ai.get("total_files") or job.get("file_count") or 0)
    flagged = int(ai.get("flagged_count") or 0)
    highest = _coerce(ai.get("highest_score"))
    average = _coerce(ai.get("average_score"))

    risk_color = _risk_color(highest)
    if highest >= 0.70:
        risk_bg = "#fef2f2"
        risk_label = "High Risk"
    elif highest >= 0.40:
        risk_bg = "#fffbeb"
        risk_label = "Needs Review"
    else:
        risk_bg = "#f0fdf4"
        risk_label = "Low Risk"

    # Dynamic CSS rules that need variable values
    dynamic_css = (
        ".score-banner{background:"
        + risk_bg
        + ";border-bottom:3px solid "
        + risk_color
        + ";padding:18px 36px;display:flex;align-items:center;"
        "gap:20px;flex-wrap:wrap}"
        ".score-circle{width:72px;height:72px;border-radius:50%;background:"
        + risk_color
        + ";display:grid;place-items:center;flex-shrink:0}"
        ".score-circle span{font-size:20px;font-weight:900;color:#fff}"
    )

    # Signal summary section
    signal_summary = ai.get("signal_summary") or {}
    sig_rows = _signal_rows(signal_summary)
    signal_section = ""
    if sig_rows:
        signal_section = (
            "<div class='sec'>"
            "<div class='sec-head'><h2>Signal Summary</h2>"
            "<span style='font-size:11px;color:#64748b'>Batch averages and peaks</span></div>"
            "<div class='sec-body'>"
            "<table style='width:100%;border-collapse:collapse'>"
            "<thead><tr>"
            "<th style='padding:8px 12px;text-align:left;font-size:11px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:.08em;color:#64748b;"
            "background:#f8fafc;border-bottom:1px solid #e2e8f0'>Signal</th>"
            "<th style='padding:8px 12px;text-align:left;font-size:11px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:.08em;color:#64748b;"
            "background:#f8fafc;border-bottom:1px solid #e2e8f0'>Batch Average</th>"
            "<th style='padding:8px 12px;text-align:right;font-size:11px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:.08em;color:#64748b;"
            "background:#f8fafc;border-bottom:1px solid #e2e8f0'>Peak</th>"
            "</tr></thead>"
            "<tbody>" + sig_rows + "</tbody>"
            "</table></div></div>"
        )

    # Submission cards
    cards = "".join(_submission_card(e) for e in submissions if isinstance(e, dict))
    if not cards:
        cards = "<div style='color:#64748b;font-size:13px'>No AI evidence stored for this report.</div>"

    return (
        "<!doctype html>"
        "<html lang='en'>"
        "<head>"
        "<meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<title>AI Detection Report — " + assignment + "</title>"
        "<style>" + _BASE_CSS + dynamic_css + "</style>"
        "</head>"
        "<body>"
        "<div class='shell'>"
        "<div class='conf-banner'>"
        "Confidential \u2014 AI Detector Evidence Report \u2014 Authorized Use Only"
        "</div>"
        "<header class='rpt-header'>"
        "<div style='display:flex;align-items:flex-start;"
        "justify-content:space-between;gap:20px;flex-wrap:wrap'>"
        "<div style='display:flex;align-items:center;gap:14px'>"
        "<div style='width:44px;height:44px;background:rgba(255,255,255,.18);"
        "border-radius:10px;display:grid;place-items:center;font-weight:900;"
        "font-size:16px;border:1.5px solid rgba(255,255,255,.25)'>ID</div>"
        "<div>"
        "<div style='font-size:10px;font-weight:700;letter-spacing:.12em;"
        "text-transform:uppercase;color:rgba(255,255,255,.75);margin-bottom:4px'>"
        "AI Detection Evidence</div>"
        "<h1 style='font-size:20px;font-weight:800;color:#fff'>" + assignment + "</h1>"
        "<div style='font-size:12px;color:rgba(255,255,255,.75);margin-top:3px'>"
        + course
        + "</div>"
        "</div></div>"
        "<div style='text-align:right;font-size:11px;color:rgba(255,255,255,.80);line-height:1.7'>"
        "<div><strong style='color:#fff'>Generated</strong><br>" + timestamp + "</div>"
        "<div style='margin-top:6px'><strong style='color:#fff'>Report ID</strong><br>"
        + _esc(report_id)
        + "</div>"
        "</div></div>"
        "</header>"
        "<div class='score-banner'>"
        "<div class='score-circle'><span>" + _pct(highest) + "</span></div>"
        "<div>"
        "<div style='font-size:17px;font-weight:800;color:"
        + risk_color
        + "'>"
        + risk_label
        + " \u2014 Highest AI Probability</div>"
        "<div style='font-size:12px;color:#475569;margin-top:3px;max-width:480px'>"
        "Fused score from 8 independent detection signals. "
        "This is a triage signal \u2014 review the evidence cards before taking action."
        "</div>"
        "</div>"
        "<div class='chips'>"
        "<div class='chip'><span class='chip-val'>"
        + str(total_files)
        + "</span><span class='chip-lbl'>Files</span></div>"
        "<div class='chip'><span class='chip-val'>"
        + str(flagged)
        + "</span><span class='chip-lbl'>Flagged</span></div>"
        "<div class='chip'><span class='chip-val'>"
        + _pct(highest)
        + "</span><span class='chip-lbl'>Highest</span></div>"
        "<div class='chip'><span class='chip-val'>"
        + _pct(average)
        + "</span><span class='chip-lbl'>Average</span></div>"
        "</div>"
        "</div>"
        "<main>"
        "<div class='sec'>"
        "<div class='sec-head'><h2>Detection Methodology</h2>"
        "<span style='font-size:11px;color:#64748b'>8-signal ensemble</span></div>"
        "<div class='sec-body' style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px'>"
        "<div style='border-left:3px solid #2563eb;background:#f8fafc;padding:10px 12px;"
        "border-radius:0 6px 6px 0;font-size:12px;color:#334155'>"
        "<strong style='display:block;color:#0f172a;margin-bottom:3px'>"
        "Token Entropy &amp; Perplexity</strong>"
        "LLMs produce lower-entropy token streams. We measure bigram entropy and invert it."
        "</div>"
        "<div style='border-left:3px solid #2563eb;background:#f8fafc;padding:10px 12px;"
        "border-radius:0 6px 6px 0;font-size:12px;color:#334155'>"
        "<strong style='display:block;color:#0f172a;margin-bottom:3px'>"
        "Burstiness &amp; Rhythm</strong>"
        "Human code has irregular complexity bursts. LLM code is uniformly structured."
        "</div>"
        "<div style='border-left:3px solid #2563eb;background:#f8fafc;padding:10px 12px;"
        "border-radius:0 6px 6px 0;font-size:12px;color:#334155'>"
        "<strong style='display:block;color:#0f172a;margin-bottom:3px'>"
        "LLM Fingerprint Library</strong>"
        "40+ regex patterns matching GPT-4 / Claude / Copilot comment and naming conventions."
        "</div>"
        "<div style='border-left:3px solid #2563eb;background:#f8fafc;padding:10px 12px;"
        "border-radius:0 6px 6px 0;font-size:12px;color:#334155'>"
        "<strong style='display:block;color:#0f172a;margin-bottom:3px'>"
        "AST Structural Entropy</strong>"
        "LLMs produce ASTs with very uniform node-type distributions."
        "</div>"
        "<div style='border-left:3px solid #2563eb;background:#f8fafc;padding:10px 12px;"
        "border-radius:0 6px 6px 0;font-size:12px;color:#334155'>"
        "<strong style='display:block;color:#0f172a;margin-bottom:3px'>"
        "Vocabulary Richness</strong>"
        "Type-Token Ratio and hapax legomena ratio. LLMs reuse a smaller vocabulary."
        "</div>"
        "<div style='border-left:3px solid #2563eb;background:#f8fafc;padding:10px 12px;"
        "border-radius:0 6px 6px 0;font-size:12px;color:#334155'>"
        "<strong style='display:block;color:#0f172a;margin-bottom:3px'>"
        "Stylometry Profile</strong>"
        "Comment formality, generic naming, type-hint saturation, docstring density."
        "</div>"
        "</div></div>" + signal_section + "<div class='sec'>"
        "<div class='sec-head'><h2>Submission Evidence</h2>"
        "<span style='font-size:11px;color:#64748b'>"
        + str(len(submissions))
        + " submission(s) \u2014 flagged lines highlighted in amber</span></div>"
        "<div class='sec-body'>" + cards + "</div>"
        "</div>"
        "<div class='notice'>"
        "&#9432; AI Detector results are review signals and should not be used as "
        "standalone misconduct findings. All flagged submissions require human review "
        "before any academic action is taken."
        "</div>"
        "</main>"
        "<footer>"
        "<span style='font-weight:700;color:#64748b'>IntegrityDesk</span>"
        "<span>Report ID: " + _esc(report_id) + " &middot; " + timestamp + "</span>"
        "<span>Prepared as an institutional evidence packet. Requires authorized sign-off.</span>"
        "</footer>"
        "</div>"
        "</body>"
        "</html>"
    )
