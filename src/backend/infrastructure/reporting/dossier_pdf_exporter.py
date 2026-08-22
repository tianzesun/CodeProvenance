"""Dossier PDF exporter — printable evidence dossier for integrity hearings.

Renders the payload built by :class:`EvidenceDossierService` into a
self-contained HTML document and converts it to PDF with WeasyPrint. The
layout mirrors the ``/dossier/[id]`` page: one severity-banded card per
student with the cross-detector evidence list and the suggested viva
questions, plus the same decision-support disclaimer so a printed dossier
can never be read as proof of misconduct on its own.
"""

from __future__ import annotations

import html
import logging
from typing import Any

logger = logging.getLogger(__name__)

BAND_COLORS = {
    "high": "#b91c1c",
    "medium": "#b45309",
    "low": "#475569",
}
BAND_LABELS = {"high": "High concern", "medium": "Medium concern", "low": "Low"}
SEVERITY_DOTS = {"high": "#dc2626", "medium": "#f59e0b", "low": "#94a3b8"}
TYPE_LABELS = {
    "ai_detection": "AI detection",
    "peer_similarity": "Peer similarity",
    "web_provenance": "Web provenance",
}
OUTCOME_LABELS = {
    "authorship_confirmed": "Authorship confirmed",
    "concerns_unresolved": "Concerns unresolved",
    "breach_identified": "Breach identified",
    "inconclusive": "Inconclusive",
}
OUTCOME_COLORS = {
    "authorship_confirmed": "#15803d",
    "concerns_unresolved": "#b45309",
    "breach_identified": "#b91c1c",
    "inconclusive": "#475569",
}

DISCLAIMER = (
    "Evidence and questions are decision support for a human reviewer, never "
    "proof of misconduct on their own."
)

_PAGE_CSS = """
@page {
    size: A4;
    margin: 15mm 12mm 18mm 12mm;
    @bottom-center {
        content: "Evidence Dossier  ·  Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #64748b;
    }
}
body { font-family: 'DejaVu Sans', Helvetica, Arial, sans-serif; color: #1e293b; }
h1 { font-size: 18pt; margin: 0 0 2pt 0; }
.meta { color: #64748b; font-size: 9.5pt; margin-bottom: 10pt; }
.coverage { margin-bottom: 14pt; font-size: 9pt; color: #475569; }
.coverage span {
    border: 0.5pt solid #cbd5e1; border-radius: 8pt; padding: 1.5pt 6pt;
    margin-right: 4pt;
}
.student-card {
    border: 0.5pt solid #cbd5e1; border-radius: 6pt;
    padding: 8pt 10pt; margin-bottom: 10pt;
    page-break-inside: avoid;
}
.student-head { display: flex; justify-content: space-between; align-items: center; }
.student-name { font-size: 11pt; font-weight: bold; }
.band {
    color: #fff; border-radius: 8pt; padding: 1.5pt 7pt;
    font-size: 8.5pt; font-weight: bold;
}
.stats { color: #475569; font-size: 9pt; margin-top: 3pt; }
.evidence-item { margin: 5pt 0 0 0; font-size: 9.5pt; }
.viva-outcome { margin: 5pt 0 0 0; font-size: 9.5pt; }
.evidence-title { font-weight: 600; }
.evidence-detail { color: #64748b; font-size: 8.5pt; margin-top: 0.5pt; }
.questions {
    margin-top: 7pt; border: 0.5pt solid #c7d2fe; border-radius: 5pt;
    background: #eef2ff; padding: 6pt 8pt;
    page-break-inside: avoid;
}
.questions-title {
    font-size: 8pt; font-weight: bold; text-transform: uppercase;
    letter-spacing: 0.5pt; color: #4338ca; margin-bottom: 3pt;
}
.questions ol { margin: 0; padding-left: 14pt; font-size: 9.5pt; }
.questions li { margin-bottom: 2.5pt; }
.disclaimer {
    margin-top: 12pt; font-size: 8.5pt; color: #94a3b8;
    border-top: 0.5pt solid #e2e8f0; padding-top: 5pt;
}
.empty { color: #64748b; font-size: 10pt; }
"""


def _esc(value: Any) -> str:
    """HTML-escape any user-derived string for safe embedding."""
    return html.escape(str(value if value is not None else ""), quote=True)


def _pct(value: Any) -> str:
    """Format an optional similarity/probability as a percentage label."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "n/a"


class DossierPdfExporter:
    """Render an evidence dossier payload to print-ready HTML and PDF."""

    def render_html(self, dossier: dict[str, Any]) -> str:
        """Build the self-contained HTML document for a dossier payload."""
        coverage = dossier.get("coverage") or {}
        students = dossier.get("students") or []

        coverage_chips = " ".join(
            f"<span>{'&#10003;' if covered else '&#8212;'} {_esc(label)}</span>"
            for label, covered in (
                ("AI detection", coverage.get("ai_detection")),
                ("Pairwise similarity", coverage.get("pairwise")),
                ("Web provenance", coverage.get("web_analysis")),
            )
        )

        if students:
            cards = "".join(self._render_student(student) for student in students)
        else:
            cards = '<p class="empty">No evidence recorded for this job.</p>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Evidence Dossier {_esc(dossier.get("job_id", ""))}</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
<h1>Evidence Dossier</h1>
<p class="meta">
Job {_esc(dossier.get("job_id", ""))} &middot; {len(students)} student
{"s" if len(students) != 1 else ""} &middot; generated
{_esc(str(dossier.get("generated_at") or "")[:19].replace("T", " "))}
</p>
<p class="coverage">{coverage_chips}</p>
{cards}
<p class="disclaimer">{_esc(DISCLAIMER)}</p>
</body>
</html>"""

    def _render_student(self, student: dict[str, Any]) -> str:
        """Render one student's severity-banded card with evidence and questions."""
        band = str(student.get("band") or "low")
        band_color = BAND_COLORS.get(band, BAND_COLORS["low"])

        stats = [
            f"AI: <strong>{_pct(student.get('ai_probability'))}</strong>",
            (
                f"Peer: <strong>{_pct(student.get('peer_max_similarity'))}</strong>"
                + (
                    f" ({_esc(student.get('peer_partner'))})"
                    if student.get("peer_partner")
                    else ""
                )
            ),
        ]
        if student.get("web_max_similarity") is not None:
            stats.append(
                f"Web: <strong>{_pct(student.get('web_max_similarity'))}</strong>"
                + (
                    f" ({_esc(student.get('web_best_match_source'))})"
                    if student.get("web_best_match_source")
                    else ""
                )
            )

        viva_outcome = student.get("viva_outcome") or {}
        outcome_html = ""
        if viva_outcome.get("outcome"):
            key = str(viva_outcome.get("outcome"))
            label = OUTCOME_LABELS.get(key, key)
            conducted = str(viva_outcome.get("conducted_at") or "")[:10]
            notes = viva_outcome.get("notes")
            outcome_html = (
                '<p class="viva-outcome">'
                f'<span style="color:{OUTCOME_COLORS.get(key, "#475569")}">'
                "&#9679;</span> Viva outcome: "
                f"<strong>{_esc(label)}</strong>"
                + (f" &middot; conducted {conducted}" if conducted else "")
                + (
                    f'<br><span class="evidence-detail">{_esc(notes)}</span>'
                    if notes
                    else ""
                )
                + "</p>"
            )

        evidence_items = "".join(
            (
                f'<p class="evidence-item">'
                f'<span style="color:{SEVERITY_DOTS.get(item.get("severity"), "#94a3b8")}'
                '">&#9679;</span> '
                f'<span class="evidence-title">{_esc(item.get("title"))}</span>'
                f' <span style="color:#94a3b8;font-size:8pt">'
                f'[{_esc(TYPE_LABELS.get(item.get("type"), str(item.get("type"))))}'
                f' / {_esc(item.get("severity"))}]</span>'
                + (
                    f'<br><span class="evidence-detail">{_esc(item.get("detail"))}</span>'
                    if item.get("detail")
                    else ""
                )
                + "</p>"
            )
            for item in student.get("evidence") or []
        )

        questions = student.get("viva_questions") or []
        questions_html = ""
        if questions:
            items = "".join(f"<li>{_esc(question)}</li>" for question in questions)
            questions_html = (
                '<div class="questions">'
                '<p class="questions-title">Suggested viva questions</p>'
                f"<ol>{items}</ol></div>"
            )

        return (
            '<div class="student-card">'
            '<div class="student-head">'
            f'<span class="student-name">{_esc(student.get("student"))}</span>'
            f'<span class="band" style="background:{band_color}">'
            f"{_esc(BAND_LABELS.get(band, band))}</span>"
            "</div>"
            f'<p class="stats">{" &middot; ".join(stats)}</p>'
            f"{outcome_html}{evidence_items}{questions_html}"
            "</div>"
        )

    def export_pdf(self, dossier: dict[str, Any]) -> bytes:
        """Render the dossier payload to PDF bytes via WeasyPrint."""
        import weasyprint

        html_content = self.render_html(dossier)
        return weasyprint.HTML(string=html_content).write_pdf()
