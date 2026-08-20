"""
Main API router for IntegrityDesk.
"""

from fastapi import APIRouter

from src.backend.api.routes import (
    auth,
    cases,
    cluster_detection,
    evidence_export,
    evidence_view,
    health,
    historical_fingerprint,
    jobs,
    results,
    submissions,
    usage,
    users,
    visualize,
    webhooks,
)

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(
    submissions.router, prefix="/submissions", tags=["submissions"]
)
api_router.include_router(results.router, prefix="/results", tags=["results"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(visualize.router, prefix="/visualize", tags=["visualize"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(
    cluster_detection.router, prefix="/cluster-detection", tags=["cluster-detection"]
)
api_router.include_router(
    evidence_view.router, prefix="/evidence-view", tags=["evidence-view"]
)
api_router.include_router(
    historical_fingerprint.router,
    prefix="/historical-fingerprint",
    tags=["historical-fingerprint"],
)
api_router.include_router(evidence_export.router, prefix="/evidence", tags=["evidence"])


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
        "redoc_url": "/redoc",
    }
