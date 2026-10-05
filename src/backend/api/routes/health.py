"""
Health check endpoints.

``/``, ``/ping`` and ``/live`` are liveness probes: they touch nothing external
and stay ``async`` (no thread hop). ``/ready`` checks the database, so an
orchestrator can hold traffic back until the service can actually serve it.
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.backend.config.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

_STARTED_MONOTONIC = time.monotonic()
_NO_STORE = "no-store"


def _liveness_body() -> dict:
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "IntegrityDesk",
        "uptime_seconds": int(time.monotonic() - _STARTED_MONOTONIC),
    }


@router.get("/")
async def health_check(response: Response):
    """
    Health check endpoint.
    """
    response.headers["Cache-Control"] = _NO_STORE
    return _liveness_body()


@router.get("/live")
async def live(response: Response):
    """Liveness probe: the process is up and serving requests."""
    response.headers["Cache-Control"] = _NO_STORE
    return _liveness_body()


@router.get("/ping")
async def ping(response: Response):
    """
    Simple ping endpoint.
    """
    response.headers["Cache-Control"] = _NO_STORE
    return {"message": "pong"}


# Plain ``def``: the database call is blocking, so it runs in a worker thread.
@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    """Readiness probe: the database answers a trivial query."""
    response.headers["Cache-Control"] = _NO_STORE
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        # Details stay in the log; a probe response should not describe the DB.
        logger.exception("Readiness check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "checks": {"database": "failed"}}
    return {"status": "ready", "checks": {"database": "ok"}}
