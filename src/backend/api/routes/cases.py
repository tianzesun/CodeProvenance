"""Case management API endpoints for Academic Integrity Investigation Platform."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.backend.config.database import get_db
from src.backend.application.services.case_service import CaseService, CaseStatus, CasePriority
from src.backend.api.dependencies import get_current_user, get_current_tenant

router = APIRouter()


# Pydantic schemas
class CaseCreate(BaseModel):
    """Schema for creating a case."""
    title: str = Field(..., min_length=1, max_length=255)
    assignment_id: Optional[uuid.UUID] = None
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|URGENT)$")


class CaseUpdate(BaseModel):
    """Schema for updating a case."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern="^(OPEN|UNDER_REVIEW|ESCALATED|CLOSED)$")
    priority: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|URGENT)$")
    investigator_id: Optional[uuid.UUID] = None


class CaseAssign(BaseModel):
    """Schema for assigning a reviewer."""
    reviewer_id: uuid.UUID


class CaseCommentCreate(BaseModel):
    """Schema for adding a comment."""
    body: str = Field(..., min_length=1)


class ResultLinkCreate(BaseModel):
    """Schema for linking a result."""
    result_id: uuid.UUID


@router.get("/cases", response_model=List[dict])
async def list_cases(
    status: Optional[str] = Query(None, pattern="^(OPEN|UNDER_REVIEW|ESCALATED|CLOSED)$"),
    limit: int = Query(100, ge=1, le=1000),
    user = Depends(get_current_user),
    tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """List cases for the current tenant/organization."""
    service = CaseService(db)
    cases = service.get_cases_by_organization(
        organization_id=tenant.id,
        status=status,
        limit=limit,
    )
    return [c.__dict__ for c in cases]


@router.post("/cases", response_model=dict, status_code=201)
async def create_case(
    payload: CaseCreate,
    user = Depends(get_current_user),
    tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Create a new investigation case."""
    service = CaseService(db)
    case = service.create_case(
        organization_id=tenant.id,
        title=payload.title,
        assignment_id=payload.assignment_id,
        created_by_id=user.id,
        priority=payload.priority,
    )
    return case.__dict__


@router.get("/cases/{case_id}", response_model=dict)
async def get_case(
    case_id: uuid.UUID,
    user = Depends(get_current_user),
    tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Get a case with all linked results and comments."""
    service = CaseService(db)
    case_data = service.get_case_with_results(case_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found")
    return case_data


@router.patch("/cases/{case_id}", response_model=dict)
async def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a case."""
    service = CaseService(db)
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if payload.status:
        case = service.update_status(case_id, payload.status, user.id)
    if payload.investigator_id:
        case = service.assign_reviewer(case_id, payload.investigator_id)
    
    return case.__dict__


@router.post("/cases/{case_id}/assign", response_model=dict)
async def assign_reviewer(
    case_id: uuid.UUID,
    payload: CaseAssign,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign a reviewer to a case."""
    service = CaseService(db)
    case = service.assign_reviewer(case_id, payload.reviewer_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.__dict__


@router.post("/cases/{case_id}/link", response_model=dict, status_code=201)
async def link_result(
    case_id: uuid.UUID,
    payload: ResultLinkCreate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Link a similarity result to a case."""
    service = CaseService(db)
    link = service.link_result(case_id, payload.result_id)
    return link.__dict__


@router.post("/cases/{case_id}/comments", response_model=dict, status_code=201)
async def add_comment(
    case_id: uuid.UUID,
    payload: CaseCommentCreate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a case."""
    service = CaseService(db)
    comment = service.add_comment(case_id, user.id, payload.body)
    return comment.__dict__


@router.get("/cases/{case_id}/timeline", response_model=List[dict])
async def get_timeline(
    case_id: uuid.UUID,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get timeline events for a case."""
    service = CaseService(db)
    timeline_service = service.timeline
    events = timeline_service.get_case_timeline(case_id)
    return [e.__dict__ for e in events]


@router.get("/cases/{case_id}/export", response_model=dict)
async def export_case(
    case_id: uuid.UUID,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export case data as JSON for audit purposes."""
    service = CaseService(db)
    return service.get_case_with_results(case_id)