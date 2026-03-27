"""
Health check endpoints.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "CodeProvenance"
    }

@router.get("/ping")
async def ping():
    """
    Simple ping endpoint.
    """
    return {"message": "pong"}
