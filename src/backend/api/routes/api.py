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

# Routers whose route paths are relative: mounted under a prefix here.
for _router, _prefix in (
    (auth.router, "/auth"),
    (jobs.router, "/jobs"),
    (submissions.router, "/submissions"),
    (results.router, "/results"),
    (webhooks.router, "/webhooks"),
    (usage.router, "/usage"),
    (health.router, "/health"),
):
    api_router.include_router(_router, prefix=_prefix, tags=[_prefix.lstrip("/")])

# Routers that already carry their own paths. Adding another prefix here doubled
# them: "/cases/cases", "/users/users", "/visualize/v1/visualize" (their routes
# are "/cases...", "/users", "/v1/visualize") and
# "/cluster-detection/api/cluster-detection/..." (they declare an absolute
# "/api/<name>" prefix themselves). They are included as-is, with the tags the
# router does not declare.
api_router.include_router(cases.router, tags=["cases"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(visualize.router, tags=["visualize"])
api_router.include_router(cluster_detection.router)
api_router.include_router(evidence_view.router)
api_router.include_router(historical_fingerprint.router)
api_router.include_router(evidence_export.router)


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
