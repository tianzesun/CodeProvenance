"""Minimal public FastAPI entrypoint used by the test suite."""

from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="IntegrityDesk")


@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple API welcome payload."""
    return {
        "message": "Welcome to IntegrityDesk API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a simple health response."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "IntegrityDesk",
    }
