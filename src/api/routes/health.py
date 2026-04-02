"""
Health check endpoints.
"""

from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()

@router.get("/")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "IntegrityDesk"
    }

@router.get("/ping")
async def ping():
    """
    Simple ping endpoint.
    """
    return {"message": "pong"}
