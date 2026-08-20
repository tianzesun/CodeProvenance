"""
Usage metering endpoints for IntegrityDesk API.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import usage as usage_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import UsageMetric
from src.backend.utils.database import TenantService, UsageMetricService

router = APIRouter()


@router.get("/", response_model=usage_schema.UsageResponse)
async def get_current_usage(request: Request, db: Session = Depends(get_db)):
    """
    Get current period usage for the authenticated tenant.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Get current period (YYYY-MM)
    current_period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Get or create usage metric for current period
    usage = UsageMetricService.get_or_create_usage_metric(
        db=db, tenant_id=str(tenant_id), period=current_period
    )

    return usage


@router.get("/history", response_model=list[usage_schema.UsageResponse])
async def get_usage_history(
    request: Request, months: int = 12, db: Session = Depends(get_db)
):
    """
    Get usage history for the last N months.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Get usage history
    usage_history = (
        db.query(UsageMetric)
        .filter(UsageMetric.tenant_id == tenant_id)
        .order_by(UsageMetric.period.desc())
        .limit(months)
        .all()
    )

    return usage_history


@router.get("/summary", response_model=usage_schema.UsageSummary)
async def get_usage_summary(request: Request, db: Session = Depends(get_db)):
    """
    Get usage summary with limits and remaining quota.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Get current period
    current_period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Get usage for current period
    usage = UsageMetricService.get_or_create_usage_metric(
        db=db, tenant_id=str(tenant_id), period=current_period
    )

    # Get tenant info for limits
    tenant = TenantService.get_tenant_by_id(db, str(tenant_id))

    # Define limits based on tier
    tier_limits = {
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

    limits = tier_limits.get(tenant.tier if tenant else "free", tier_limits["free"])

    # Calculate remaining
    remaining = {}
    for key, limit in limits.items():
        used = getattr(usage, key, 0)
        remaining[key] = max(0, limit - used)

    return usage_schema.UsageSummary(
        tenant_id=tenant.id,
        current_period=current_period,
        usage=usage,
        limits=limits,
        remaining=remaining,
    )


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_usage(request: Request, db: Session = Depends(get_db)):
    """
    Reset usage metrics for current period (admin only).
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Get current period
    current_period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Delete existing usage metric for current period
    db.query(UsageMetric).filter(
        UsageMetric.tenant_id == tenant_id, UsageMetric.period == current_period
    ).delete()

    db.commit()

    return {"message": "Usage metrics reset for current period"}
