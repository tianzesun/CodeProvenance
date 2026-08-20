"""
Health check endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "IntegrityDesk",
    }


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint.
    """
    return {"message": "pong"}
