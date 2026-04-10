"""
Main API router for IntegrityDesk.
"""

from fastapi import APIRouter
from src.api.routes import auth, jobs, submissions, results, webhooks, usage, health, visualize

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(submissions.router, prefix="/submissions", tags=["submissions"])
api_router.include_router(results.router, prefix="/results", tags=["results"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(visualize.router, prefix="/visualize", tags=["visualize"])

# Root endpoint
@api_router.get("/")
async def root():
    """
    Root endpoint returning API information.
    """
    return {
        "name": "IntegrityDesk API",
        "version": "1.0.0",
        "description": "Software Similarity Detection Service",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
