"""Integrity Assessment Report — PDF exporter.

Renders the HTML report to PDF using the best available backend:
  1. weasyprint (preferred)
  2. pdfkit / wkhtmltopdf (fallback)
  3. Raw HTML (last resort)

Also provides a convenience function for the API layer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backend.infrastructure.integrity_assessment_report import (
        IntegrityAssessmentReport,
    )

logger = logging.getLogger(__name__)


def export_integrity_report_pdf(
    report: "IntegrityAssessmentReport",
    html_content: str | None = None,
) -> bytes:
    """Export an IntegrityAssessmentReport to PDF bytes.

    Tries weasyprint → pdfkit → returns raw HTML as bytes.

    Args:
        report: The populated report dataclass.
        html_content: Pre-rendered HTML (optional, will render if not provided).

    Returns:
        PDF bytes, or HTML bytes if PDF generation fails.
    """
    if html_content is None:
        from src.backend.infrastructure.integrity_assessment_report_html import (
            render_integrity_report_html,
        )

        html_content = render_integrity_report_html(report)

    # Attempt 1: weasyprint
    pdf_bytes = _try_weasyprint(html_content)
    if pdf_bytes:
        return pdf_bytes

    # Attempt 2: pdfkit
    pdf_bytes = _try_pdfkit(html_content)
    if pdf_bytes:
        return pdf_bytes

    # Attempt 3: return HTML as bytes (caller should serve as text/html)
    logger.warning(
        "No PDF backend available; returning raw HTML for report %s",
        report.report_id,
    )
    return html_content.encode("utf-8")


def export_integrity_report_html(report: "IntegrityAssessmentReport") -> str:
    """Export report as self-contained HTML string."""
    from src.backend.infrastructure.integrity_assessment_report_html import (
        render_integrity_report_html,
    )

    return render_integrity_report_html(report)


def _try_weasyprint(html: str) -> bytes | None:
    """Attempt PDF generation with weasyprint."""
    try:
        import weasyprint

        doc = weasyprint.HTML(string=html)
        pdf = doc.write_pdf()
        if pdf and len(pdf) > 100:
            logger.info("PDF generated via weasyprint (%d bytes)", len(pdf))
            return pdf
    except ImportError:
        logger.debug("weasyprint not installed")
    except Exception:
        logger.exception("weasyprint PDF generation failed")
    return None


def _try_pdfkit(html: str) -> bytes | None:
    """Attempt PDF generation with pdfkit (wkhtmltopdf)."""
    try:
        import pdfkit

        options = {
            "page-size": "A4",
            "margin-top": "15mm",
            "margin-right": "12mm",
            "margin-bottom": "18mm",
            "margin-left": "12mm",
            "encoding": "UTF-8",
            "enable-local-file-access": "",
            "print-media-type": "",
        }
        pdf = pdfkit.from_string(html, False, options=options)
        if pdf and len(pdf) > 100:
            logger.info("PDF generated via pdfkit (%d bytes)", len(pdf))
            return pdf
    except ImportError:
        logger.debug("pdfkit not installed")
    except Exception:
        logger.exception("pdfkit PDF generation failed")
    return None
