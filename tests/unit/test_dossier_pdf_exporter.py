"""Unit tests for the dossier PDF exporter."""

import pytest

from src.backend.evaluation.evidence_dossier import EvidenceDossierService
from src.backend.infrastructure.reporting.dossier_pdf_exporter import DossierPdfExporter


def _job_payload() -> dict:
    return {
        "id": "job-1",
        "threshold": 0.6,
        "results": [
            {
                "file_a": "alice.py",
                "file_b": "bob.py",
                "score": 0.91,
                "risk_level": "high",
                "matching_blocks": [
                    {
                        "lines_a": "10-50",
                        "lines_b": "12-52",
                        "similarity": 0.93,
                        "block_type": "code",
                        "function_name": "dijkstra_shortest_path",
                    }
                ],
            },
        ],
        "ai_detection": {
            "submissions": [
                {
                    "name": "alice.py",
                    "ai_probability": 0.78,
                    "confidence": 0.62,
                    "status": "High Risk",
                    "indicators": ["LLM fingerprint patterns"],
                    "flagged_regions": [
                        {"start_line": 10, "end_line": 34, "reason": "low_perplexity"}
                    ],
                }
            ]
        },
        "web_analysis": {
            "submissions": [
                {
                    "name": "alice.py",
                    "max_similarity": 0.86,
                    "match_count": 1,
                    "sources": [
                        {
                            "name": "org/repo/dijkstra.py",
                            "url": "https://github.com/org/repo/blob/main/dijkstra.py",
                            "source": "github",
                            "similarity": 0.86,
                        }
                    ],
                }
            ]
        },
    }


def _dossier() -> dict:
    return EvidenceDossierService().build(_job_payload())


class TestRenderHtml:
    """HTML rendering of a built dossier payload."""

    def test_includes_job_summary_and_students(self):
        """Job id, coverage chips and every student name appear in the HTML."""
        html_content = DossierPdfExporter().render_html(_dossier())
        assert "job-1" in html_content
        assert "alice.py" in html_content
        assert "bob.py" in html_content
        assert "AI detection" in html_content
        assert "Web provenance" in html_content

    def test_includes_bands_evidence_and_questions(self):
        """Band labels, evidence titles and viva questions are rendered."""
        html_content = DossierPdfExporter().render_html(_dossier())
        assert "High concern" in html_content
        assert "similar region(s) with bob.py" in html_content
        assert "Suggested viva questions" in html_content
        assert "walk through their solution design" in html_content

    def test_includes_disclaimer(self):
        """The decision-support disclaimer is always present."""
        html_content = DossierPdfExporter().render_html(_dossier())
        assert "never proof of misconduct" in html_content

    def test_escapes_user_controlled_text(self):
        """Student names and details are HTML-escaped."""
        dossier = _dossier()
        dossier["students"][0]["student"] = "<script>alert(1)</script>"
        dossier["students"][0]["evidence"][0]["title"] = "<b>bold</b>"
        html_content = DossierPdfExporter().render_html(dossier)
        assert "<script>" not in html_content
        assert "&lt;script&gt;" in html_content
        assert "<b>bold</b>" not in html_content

    def test_empty_dossier_renders_placeholder(self):
        """A dossier with no students shows the empty-state message."""
        dossier = {
            "job_id": "job-empty",
            "generated_at": "2026-08-22T00:00:00",
            "coverage": {},
            "students": [],
        }
        html_content = DossierPdfExporter().render_html(dossier)
        assert "No evidence recorded" in html_content


class TestExportPdf:
    """End-to-end HTML-to-PDF conversion."""

    def test_pdf_bytes(self):
        """A full service-built dossier converts to a non-trivial PDF."""
        weasyprint = pytest.importorskip("weasyprint")
        pdf_bytes = DossierPdfExporter().export_pdf(_dossier())
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000
        assert weasyprint.__name__ == "weasyprint"


class TestVivaOutcomeRendering:
    """Recorded viva outcomes appear on the printed dossier."""

    def test_renders_recorded_outcome(self):
        """Outcome label, date and notes are rendered and escaped."""
        dossier = _dossier()
        dossier["students"][0]["viva_outcome"] = {
            "outcome": "authorship_confirmed",
            "notes": "Explained the design choices.",
            "conducted_at": "2026-08-22T10:00:00",
        }
        html_content = DossierPdfExporter().render_html(dossier)
        assert "Viva outcome: <strong>Authorship confirmed</strong>" in html_content
        assert "conducted 2026-08-22" in html_content
        assert "Explained the design choices." in html_content

    def test_no_outcome_renders_nothing(self):
        """Students without a recorded outcome get no outcome line."""
        html_content = DossierPdfExporter().render_html(_dossier())
        assert "Viva outcome:" not in html_content
