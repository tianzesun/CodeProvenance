"""Case management API endpoints for Academic Integrity Investigation Platform."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.backend.config.database import get_db
from src.backend.application.services.case_service import CaseService, CaseStatus, CasePriority
from src.backend.models.database import User, Case, CaseComment

router = APIRouter()
security = HTTPBearer(auto_error=False)


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


class CaseResponse(BaseModel):
    """Pydantic model for Case serialization."""
    id: str
    organization_id: str
    assignment_id: Optional[str] = None
    title: str
    status: str
    priority: str
    investigator_id: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None

    class Config:
        from_attributes = True


def _serialize_case(case: Any) -> dict:
    """Serialize a Case object to a dictionary, excluding SQLAlchemy state."""
    if case is None:
        return {}
    data = {}
    for key, value in case.__dict__.items():
        if key.startswith('__'):
            continue
        # Skip SQLAlchemy internal state
        if key in ('_sa_instance_state',):
            continue
        # Convert UUID to string for JSON serialization
        if isinstance(value, uuid.UUID):
            data[key] = str(value)
        # Convert datetime to ISO format
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        # Handle nested objects that might be ORM instances (relationships)
        elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, list, dict)):
            # Try to get the ID if it's a relationship
            if hasattr(value, 'id'):
                data[key] = str(value.id)
            else:
                data[key] = None
        else:
            data[key] = value
    return data


def _serialize_comment(comment: Any) -> dict:
    """Serialize a CaseComment object to a dictionary."""
    if comment is None:
        return {}
    data = {}
    for key, value in comment.__dict__.items():
        if key.startswith('__') or key in ('_sa_instance_state',):
            continue
        if isinstance(value, uuid.UUID):
            data[key] = str(value)
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        else:
            data[key] = value
    return data


def get_current_user() -> dict:
    """Get current user - for development, returns mock user."""
    return {"id": uuid.uuid4(), "email": "user@example.com", "role": "professor"}


def get_current_tenant() -> dict:
    """Get current tenant/organization - for development, returns mock tenant."""
    return {"id": uuid.UUID("2bde87ba-3ad4-4282-b199-02243991150e")}


@router.get("/cases", response_model=List[dict])
async def list_cases(
    status: Optional[str] = Query(None, pattern="^(OPEN|UNDER_REVIEW|ESCALATED|CLOSED)$"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List cases for the current tenant/organization."""
    user = get_current_user()
    tenant = get_current_tenant()
    service = CaseService(db)
    cases = service.get_cases_by_organization(
        organization_id=tenant["id"],
        status=status,
        limit=limit,
    )
    return [_serialize_case(c) for c in cases]


@router.post("/cases", response_model=dict, status_code=201)
async def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
):
    """Create a new investigation case."""
    user = get_current_user()
    tenant = get_current_tenant()
    service = CaseService(db)
    case = service.create_case(
        organization_id=tenant["id"],
        title=payload.title,
        assignment_id=payload.assignment_id,
        created_by_id=user["id"],
        priority=payload.priority,
    )
    return _serialize_case(case)


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
    # Serialize the case data
    case_obj = case_data.get("case")
    result = {
        "case": _serialize_case(case_obj) if isinstance(case_obj, Case) else case_obj,
        "result_ids": [str(rid) for rid in case_data.get("result_ids", [])],
        "comments": [_serialize_comment(c) if isinstance(c, CaseComment) else c for c in case_data.get("comments", [])],
    }
    return result


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
        case = service.update_status(case_id, payload.status, user["id"])
    if payload.investigator_id:
        case = service.assign_reviewer(case_id, payload.investigator_id)
    
    return _serialize_case(case)


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
    return _serialize_case(case)


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
    return _serialize_case(link)


@router.post("/cases/{case_id}/comments", response_model=dict, status_code=201)
async def add_comment(
    case_id: uuid.UUID,
    payload: CaseCommentCreate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a case."""
    service = CaseService(db)
    comment = service.add_comment(case_id, user["id"], payload.body)
    return _serialize_case(comment)


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
    return [_serialize_case(e) if hasattr(e, '__dict__') else e for e in events]


@router.get("/cases/{case_id}/export", response_model=dict)
async def export_case(
    case_id: uuid.UUID,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export case data as JSON for audit purposes."""
    service = CaseService(db)
    return service.get_case_with_results(case_id)