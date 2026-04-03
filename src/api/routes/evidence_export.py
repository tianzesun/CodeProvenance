"""FastAPI endpoint for exporting evidence chain PDFs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse

from src.infrastructure.reporting.evidence_pdf_exporter import (
    EvidenceChainPdfExporter,
    PDF_BACKEND,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

_exporter: Optional[EvidenceChainPdfExporter] = None


def get_exporter(output_dir: Optional[Path] = None) -> EvidenceChainPdfExporter:
    global _exporter
    if _exporter is None:
        _exporter = EvidenceChainPdfExporter(output_dir=output_dir)
    return _exporter


@router.post("/export-pdf")
async def export_evidence_pdf(
    case_id: str = Query(..., description="Case identifier"),
    format: str = Query("pdf", description="Output format: pdf or html"),
):
    """
    Export a complete evidence chain report as PDF or HTML.

    The report includes:
    - Cover page with case metadata
    - Executive summary with risk assessment
    - Similarity heatmap
    - Code diff visualization
    - AI generation analysis
    - Tool comparison with statistical significance
    - Digital signature (SHA-256)
    """
    if PDF_BACKEND is None and format == "pdf":
        raise HTTPException(
            status_code=503,
            detail="No PDF backend available. Install weasyprint or pdfkit.",
        )

    # Fetch case data from database (placeholder — replace with actual query)
    case_data = _fetch_case_data(case_id)
    if case_data is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    exporter = get_exporter()

    if format == "html":
        html_path = exporter.export_html(case_data)
        if html_path is None:
            raise HTTPException(status_code=500, detail="Failed to generate HTML report")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    pdf_path = exporter.export(case_data)
    if pdf_path is None:
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"evidence_{case_id}.pdf",
    )


@router.get("/export-html/{case_id}")
async def export_evidence_html(case_id: str):
    """Export evidence report as standalone HTML."""
    case_data = _fetch_case_data(case_id)
    if case_data is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    exporter = get_exporter()
    html_path = exporter.export_html(case_data)
    if html_path is None:
        raise HTTPException(status_code=500, detail="Failed to generate HTML report")

    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


def _fetch_case_data(case_id: str) -> Optional[dict]:
    """
    Fetch case data from the database.

    Replace this with actual database query.
    Returns a dict compatible with EvidenceChainPdfExporter.
    """
    # Placeholder — implement actual database query
    from src.models.database import SessionLocal

    try:
        db = SessionLocal()
        # Query case, findings, tools, etc.
        # Build case_data dict
        return None
    except Exception:
        return None
    finally:
        db.close()
