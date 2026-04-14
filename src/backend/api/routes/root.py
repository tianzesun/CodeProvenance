"""Root endpoint for the API."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "message": "Welcome to IntegrityDesk API",
        "version": "1.0.0",
        "docs": "/docs",
    }