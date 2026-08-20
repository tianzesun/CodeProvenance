"""Investigation Timeline service for tracking case actions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.models.database import TimelineEvent


class TimelineEventType(str):
    """Types of timeline events."""

    SUBMISSION_UPLOADED = "submission_uploaded"
    SIMILARITY_ANALYSIS_COMPLETED = "similarity_analysis_completed"
    EVIDENCE_REVIEWED = "evidence_reviewed"
    REVIEWER_NOTE_ADDED = "reviewer_note_added"
    CASE_ESCALATED = "case_escalated"
    REPORT_GENERATED = "report_generated"
    CASE_CLOSED = "case_closed"
    RESULT_LINKED = "result_linked"


class TimelineService:
    """Service for managing investigation timeline events."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_event(
        self,
        case_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        event_type: str = "",
        title: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        """Create a new timeline event."""
        from src.backend.models.database import TimelineEvent

        event = TimelineEvent(
            id=uuid.uuid4(),
            case_id=case_id,
            job_id=job_id,
            user_id=user_id,
            event_type=event_type,
            title=title,
            description=description,
            event_metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_case_timeline(self, case_id: uuid.UUID) -> list[TimelineEvent]:
        """Get all events for a case, ordered chronologically."""
        result = self.db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.case_id == case_id)
            .order_by(TimelineEvent.created_at)
        )
        return list(result.scalars())

    def get_job_timeline(self, job_id: uuid.UUID) -> list[TimelineEvent]:
        """Get all events for a job."""
        result = self.db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.job_id == job_id)
            .order_by(TimelineEvent.created_at)
        )
        return list(result.scalars())

    def export_timeline(self, case_id: uuid.UUID) -> list[dict[str, Any]]:
        """Export timeline as list of dictionaries."""
        events = self.get_case_timeline(case_id)
        return [
            {
                "id": str(e.id),
                "type": e.event_type,
                "title": e.title,
                "description": e.description,
                "user_id": str(e.user_id) if e.user_id else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "metadata": e.metadata,
            }
            for e in events
        ]
