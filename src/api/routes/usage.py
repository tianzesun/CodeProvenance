"""
Usage metering endpoints for CodeProvenance API.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from src.config.database import get_db, set_tenant_context
from src.models.database import UsageMetric, Tenant
from src.utils.database import UsageMetricService, TenantService
from src.api.schemas import usage as usage_schema

router = APIRouter()


@router.get("/", response_model=usage_schema.UsageResponse)
async def get_current_usage(
    db: Session = Depends(get_db)
):
    """
    Get current period usage for the authenticated tenant.
    """
    # In a real implementation, we would extract tenant_id from API key
    # For now, we'll use a placeholder - this should come from authentication
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Get current period (YYYY-MM)
    current_period = datetime.utcnow().strftime("%Y-%m")
    
    # Get or create usage metric for current period
    usage = UsageMetricService.get_or_create_usage_metric(
        db=db,
        tenant_id=str(tenant_id),
        period=current_period
    )
    
    return usage


@router.get("/history", response_model=List[usage_schema.UsageResponse])
async def get_usage_history(
    months: int = 12,
    db: Session = Depends(get_db)
):
    """
    Get usage history for the last N months.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Get usage history
    usage_history = db.query(UsageMetric).filter(
        UsageMetric.tenant_id == tenant_id
    ).order_by(UsageMetric.period.desc()).limit(months).all()
    
    return usage_history


@router.get("/summary", response_model=usage_schema.UsageSummary)
async def get_usage_summary(
    db: Session = Depends(get_db)
):
    """
    Get usage summary with limits and remaining quota.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Get current period
    current_period = datetime.utcnow().strftime("%Y-%m")
    
    # Get usage for current period
    usage = UsageMetricService.get_or_create_usage_metric(
        db=db,
        tenant_id=str(tenant_id),
        period=current_period
    )
    
    # Get tenant info for limits
    tenant = TenantService.get_tenant_by_id(db, str(tenant_id))
    
    # Define limits based on tier
    tier_limits = {
        'free': {
            'jobs_processed': 100,
            'files_parsed': 1000,
            'total_size_mb': 100,
            'compute_seconds': 3600,  # 1 hour
            'api_calls': 1000
        },
        'basic': {
            'jobs_processed': 1000,
            'files_parsed': 10000,
            'total_size_mb': 1000,
            'compute_seconds': 36000,  # 10 hours
            'api_calls': 10000
        },
        'pro': {
            'jobs_processed': 10000,
            'files_parsed': 100000,
            'total_size_mb': 10000,
            'compute_seconds': 360000,  # 100 hours
            'api_calls': 100000
        },
        'enterprise': {
            'jobs_processed': 100000,
            'files_parsed': 1000000,
            'total_size_mb': 100000,
            'compute_seconds': 3600000,  # 1000 hours
            'api_calls': 1000000
        }
    }
    
    limits = tier_limits.get(tenant.tier if tenant else 'free', tier_limits['free'])
    
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
        remaining=remaining
    )


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_usage(
    db: Session = Depends(get_db)
):
    """
    Reset usage metrics for current period (admin only).
    """
    # In a real implementation, we would extract tenant_id from API key
    # and check for admin permissions
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Get current period
    current_period = datetime.utcnow().strftime("%Y-%m")
    
    # Delete existing usage metric for current period
    db.query(UsageMetric).filter(
        UsageMetric.tenant_id == tenant_id,
        UsageMetric.period == current_period
    ).delete()
    
    db.commit()
    
    return {"message": "Usage metrics reset for current period"}