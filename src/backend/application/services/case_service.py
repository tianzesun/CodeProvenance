"""Case Management Service for Academic Integrity Investigation Platform."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc, or_
from sqlalchemy.orm import Session

from src.backend.models.database import Case, CaseResultLink, CaseComment
from src.backend.application.services.timeline_service import TimelineService, TimelineEventType


class CaseStatus(str):
    """Case status values."""
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class CasePriority(str):
    """Case priority values."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class CaseService:
    """Service for managing investigation cases."""
    
    def __init__(self, db: Session) -> None:
        self.db = db
        self.timeline = TimelineService(db)
    
    def create_case(
        self,
        organization_id: uuid.UUID,
        title: str,
        assignment_id: Optional[uuid.UUID] = None,
        created_by_id: Optional[uuid.UUID] = None,
        priority: str = "MEDIUM",
    ) -> Case:
        """Create a new investigation case."""
        case = Case(
            id=uuid.uuid4(),
            organization_id=organization_id,
            assignment_id=assignment_id,
            title=title,
            status=CaseStatus.OPEN,
            priority=priority,
            created_by_id=created_by_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        
        # Log timeline event
        self.timeline.create_event(
            case_id=case.id,
            user_id=created_by_id,
            event_type=TimelineEventType.SUBMISSION_UPLOADED,
            title="Case Created",
            description=title,
        )
        
        return case
    
    def get_case(self, case_id: uuid.UUID) -> Optional[Case]:
        """Get a case by ID."""
        result = self.db.execute(
            select(Case).where(Case.id == case_id)
        )
        return result.scalar_one_or_none()
    
    def get_cases_by_organization(
        self,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Case]:
        """Get cases for an organization, optionally filtered by status."""
        query = select(Case).where(Case.organization_id == organization_id)
        if status:
            query = query.where(Case.status == status)
        query = query.order_by(desc(Case.created_at)).limit(limit)
        result = self.db.execute(query)
        return list(result.scalars())
    
    def assign_reviewer(self, case_id: uuid.UUID, reviewer_id: uuid.UUID) -> Case:
        """Assign a reviewer to a case."""
        case = self.get_case(case_id)
        if case:
            case.investigator_id = reviewer_id
            case.status = CaseStatus.UNDER_REVIEW
            case.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(case)
            
            self.timeline.create_event(
                case_id=case_id,
                user_id=reviewer_id,
                event_type="reviewer_assigned",
                title="Reviewer Assigned",
                description=f"Assigned to {reviewer_id}",
            )
        return case
    
    def link_result(self, case_id: uuid.UUID, result_id: uuid.UUID) -> CaseResultLink:
        """Link a similarity result to a case."""
        link = CaseResultLink(
            id=uuid.uuid4(),
            case_id=case_id,
            similarity_result_id=result_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        
        self.timeline.create_event(
            case_id=case_id,
            event_type=TimelineEventType.RESULT_LINKED,
            title="Result Linked",
            description=f"Linked result {result_id}",
        )
        
        return link
    
    def add_comment(
        self,
        case_id: uuid.UUID,
        user_id: uuid.UUID,
        body: str,
    ) -> CaseComment:
        """Add a comment to a case."""
        comment = CaseComment(
            id=uuid.uuid4(),
            case_id=case_id,
            user_id=user_id,
            body=body,
            created_at=datetime.utcnow(),
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        
        self.timeline.create_event(
            case_id=case_id,
            user_id=user_id,
            event_type=TimelineEventType.REVIEWER_NOTE_ADDED,
            title="Note Added",
            description=body[:100],
        )
        
        return comment
    
    def update_status(
        self,
        case_id: uuid.UUID,
        status: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Case:
        """Update case status."""
        case = self.get_case(case_id)
        if case:
            case.status = status
            case.updated_at = datetime.utcnow()
            if status == CaseStatus.CLOSED:
                case.closed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(case)
            
            self.timeline.create_event(
                case_id=case_id,
                user_id=user_id,
                event_type="status_changed",
                title="Status Updated",
                description=f"Status changed to {status}",
            )
        return case
    
    def get_case_with_results(self, case_id: uuid.UUID) -> Dict[str, Any]:
        """Get a case with all linked results and comments."""
        case = self.get_case(case_id)
        if not case:
            return {}
        
        # Get linked results
        result_links = self.db.execute(
            select(CaseResultLink).where(CaseResultLink.case_id == case_id)
        ).scalars().all()
        
        result_ids = [link.similarity_result_id for link in result_links]
        
        # Get comments
        comments = self.db.execute(
            select(CaseComment)
            .where(CaseComment.case_id == case_id)
            .order_by(desc(CaseComment.created_at))
        ).scalars().all()
        
        # Serialize case and comments to avoid SQLAlchemy state issues
        case_dict = {}
        for key, value in case.__dict__.items():
            if key.startswith('__') or key == '_sa_instance_state':
                continue
            if isinstance(value, uuid.UUID):
                case_dict[key] = str(value)
            elif isinstance(value, datetime):
                case_dict[key] = value.isoformat()
            else:
                case_dict[key] = value
        
        comments_list = []
        for c in comments:
            comment_dict = {}
            for key, value in c.__dict__.items():
                if key.startswith('__') or key == '_sa_instance_state':
                    continue
                if isinstance(value, uuid.UUID):
                    comment_dict[key] = str(value)
                elif isinstance(value, datetime):
                    comment_dict[key] = value.isoformat()
                else:
                    comment_dict[key] = value
            comments_list.append(comment_dict)
        
        return {
            "case": case_dict,
            "result_ids": [str(rid) for rid in result_ids],
            "comments": comments_list,
        }