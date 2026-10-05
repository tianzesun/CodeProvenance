"""FastAPI endpoint for exporting evidence chain PDFs."""

from __future__ import annotations

import functools
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import dashboard_user
from src.backend.application.services.case_service import CaseService
from src.backend.config.database import get_db
from src.backend.infrastructure.reporting.evidence_pdf_exporter import (
    EvidenceChainPdfExporter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

#: The HTML report embeds submission content. Served from our origin it must not
#: be able to run script or load anything remote even if the exporter misses an
#: escape.
_HTML_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}


@functools.lru_cache(maxsize=1)
def get_exporter(output_dir: Path | None = None) -> EvidenceChainPdfExporter:
    """Shared exporter (the module-level global it replaces was not thread-safe)."""
    return EvidenceChainPdfExporter(output_dir=output_dir)


def _case_for_caller(db: Session, request: Request, case_id: str) -> Any:
    """Return the case if it exists in the caller's organization, else 404.

    These endpoints had no authentication or tenant check at all: with a real
    data source behind them, any caller could export any organization's case.
    Missing and other-organization cases both return 404.
    """
    user = dashboard_user(request)
    organization_id = (user or {}).get("organization_id")
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found") from None
    case = CaseService(db).get_case(case_uuid)
    if case is None or not organization_id or str(case.organization_id) != str(organization_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _build_case_data(case: Any) -> dict[str, Any]:
    """Assemble the dict EvidenceChainPdfExporter consumes for ``case``.

    Integration point. The previous version returned ``None`` unconditionally
    (and referenced an unbound ``db`` in ``finally`` when ``SessionLocal()``
    failed), so every export answered "Case not found". Implement this with the
    exporter's expected structure: case metadata, findings, tool comparison.
    """
    raise NotImplementedError


def _load_case_data(db: Session, request: Request, case_id: str) -> dict[str, Any]:
    case = _case_for_caller(db, request, case_id)
    try:
        return _build_case_data(case)
    except NotImplementedError:
        # Honest answer instead of a misleading 404.
        raise HTTPException(
            status_code=501, detail="Evidence export is not available yet."
        ) from None


def _html_response(html_path: Path | None) -> HTMLResponse:
    if html_path is None:
        raise HTTPException(status_code=500, detail="Failed to generate HTML report")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), headers=_HTML_HEADERS)


# Plain ``def`` handlers: report generation is CPU- and disk-bound, so FastAPI
# runs them in a worker thread instead of blocking the event loop.


@router.post("/export-pdf")
def export_evidence_pdf(
    request: Request,
    case_id: str = Query(..., description="Case identifier", max_length=64),
    format: str = Query("pdf", description="Output format: pdf or html", pattern="^(pdf|html)$"),
    db: Session = Depends(get_db),
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
    case_data = _load_case_data(db, request, case_id)
    exporter = get_exporter()

    if format == "html":
        return _html_response(exporter.export_html(case_data))

    pdf_path = exporter.export(case_data)
    if pdf_path is None:
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        # Built from the parsed UUID, never from raw user input.
        filename=f"evidence_{uuid.UUID(case_id)}.pdf",
    )


@router.get("/export-html/{case_id}")
def export_evidence_html(request: Request, case_id: str, db: Session = Depends(get_db)):
    """Export evidence report as standalone HTML."""
    case_data = _load_case_data(db, request, case_id)
    return _html_response(get_exporter().export_html(case_data))
