"""
Usage metering endpoints for IntegrityDesk API.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant, require_admin
from src.backend.api.schemas import usage as usage_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import UsageMetric
from src.backend.utils.database import TenantService, UsageMetricService

logger = logging.getLogger(__name__)

router = APIRouter()

# Built once; it used to be rebuilt on every /summary request.
TIER_LIMITS: dict[str, dict[str, int]] = {
    "free": {
        "jobs_processed": 100,
        "files_parsed": 1000,
        "total_size_mb": 100,
        "compute_seconds": 3600,  # 1 hour
        "api_calls": 1000,
    },
    "basic": {
        "jobs_processed": 1000,
        "files_parsed": 10000,
        "total_size_mb": 1000,
        "compute_seconds": 36000,  # 10 hours
        "api_calls": 10000,
    },
    "pro": {
        "jobs_processed": 10000,
        "files_parsed": 100000,
        "total_size_mb": 10000,
        "compute_seconds": 360000,  # 100 hours
        "api_calls": 100000,
    },
    "enterprise": {
        "jobs_processed": 100000,
        "files_parsed": 1000000,
        "total_size_mb": 100000,
        "compute_seconds": 3600000,  # 1000 hours
        "api_calls": 1000000,
    },
}


def current_period() -> str:
    """Current billing period (YYYY-MM, UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def limits_for_tier(tier: Any) -> dict[str, int]:
    """Limits for a tier name, tolerating None, odd casing and unknown tiers."""
    return TIER_LIMITS.get(str(tier or "free").strip().lower(), TIER_LIMITS["free"])


def remaining_quota(usage: Any, limits: dict[str, int]) -> dict[str, int]:
    """Quota left per metric. A NULL column counts as zero used, not a crash."""
    return {
        key: max(0, limit - (getattr(usage, key, 0) or 0)) for key, limit in limits.items()
    }


# Plain ``def`` handlers: the session is synchronous, so FastAPI runs them in a
# worker thread instead of blocking the event loop.


@router.get("/", response_model=usage_schema.UsageResponse)
def get_current_usage(request: Request, db: Session = Depends(get_db)):
    """
    Get current period usage for the authenticated tenant.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Get or create usage metric for current period
    return UsageMetricService.get_or_create_usage_metric(
        db=db, tenant_id=str(tenant_id), period=current_period()
    )


@router.get("/history", response_model=list[usage_schema.UsageResponse])
def get_usage_history(
    request: Request,
    months: int = Query(12, ge=1, le=120),
    db: Session = Depends(get_db),
):
    """
    Get usage history for the last N months.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    return (
        db.query(UsageMetric)
        .filter(UsageMetric.tenant_id == tenant_id)
        .order_by(UsageMetric.period.desc())
        .limit(months)
        .all()
    )


@router.get("/summary", response_model=usage_schema.UsageSummary)
def get_usage_summary(request: Request, db: Session = Depends(get_db)):
    """
    Get usage summary with limits and remaining quota.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    period = current_period()
    usage = UsageMetricService.get_or_create_usage_metric(
        db=db, tenant_id=str(tenant_id), period=period
    )

    # Tenant info for limits. A missing tenant used to fall back to the free
    # tier and then crash on ``tenant.id``.
    tenant = TenantService.get_tenant_by_id(db, str(tenant_id))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    limits = limits_for_tier(getattr(tenant, "tier", None))
    return usage_schema.UsageSummary(
        tenant_id=tenant.id,
        current_period=period,
        usage=usage,
        limits=limits,
        remaining=remaining_quota(usage, limits),
    )


# Resetting usage zeroes the metered counts that quotas are checked against, so
# it must be admin-only. The docstring said so but nothing enforced it: any
# authenticated user could reset their own usage and bypass their tier limits.
@router.post(
    "/reset", status_code=status.HTTP_200_OK, dependencies=[Depends(require_admin)]
)
def reset_usage(request: Request, db: Session = Depends(get_db)):
    """
    Reset usage metrics for current period (admin only).
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    period = current_period()
    deleted = (
        db.query(UsageMetric)
        .filter(UsageMetric.tenant_id == tenant_id, UsageMetric.period == period)
        .delete()
    )
    db.commit()

    # Metering changes affect billing, so leave a trace.
    logger.warning("Usage metrics reset: tenant=%s period=%s rows=%s", tenant_id, period, deleted)
    return {"message": "Usage metrics reset for current period"}
