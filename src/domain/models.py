"""Core domain models for Academic Integrity Case Management.

The system does NOT detect plagiarism. It detects similarity and
produces evidence packages for human review. The system NEVER auto-decides guilt.

Key design principles:
- Submissions are immutable (hash on ingest, never overwrite)
- Every action is logged with timestamp (for appeals)
- Findings are surfaced, verdicts are human
- FERPA/PIPEDA compliance by design
"""
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────
# Immutable Submission (chain of custody)
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class ImmutableSubmission:
    """A code submission that cannot be modified after ingestion.
    
    The hash serves as chain-of-custody evidence. If a student appeals,
    we must be able to prove the exact code that was compared.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_file: str = ""
    content_hash: str = ""  # SHA-256 of content
    content: str = ""
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    student_id: Optional[str] = None  # May be redacted for committee view
    course_code: Optional[str] = None
    assignment_name: Optional[str] = None
    
    def __post_init__(self):
        """Compute content hash if not provided."""
        if not self.content_hash and self.content:
            h = hashlib.sha256(self.content.encode()).hexdigest()
            object.__setattr__(self, 'content_hash', h)
    
    def redact_for_committee(self) -> 'ImmutableSubmission':
        """Return a copy with PII redacted for blind committee review."""
        return ImmutableSubmission(
            id=self.id,
            source_file=self.source_file,
            content_hash=self.content_hash,
            content="",  # Content redacted - only hash retained for verification
            received_at=self.received_at,
            student_id="[REDACTED]",
            course_code=self.course_code,
            assignment_name=self.assignment_name,
        )


# ─────────────────────────────────────────────
# Evidence / Findings
# ─────────────────────────────────────────────

@dataclass
class EvidenceBlock:
    """A specific piece of matching code evidence.
    
    "94% similar" is not evidence. This is:
    - Lines 10-25 in file A match lines 12-27 in file B
    - Variable renaming detected: 'x' -> 'y'
    - Engine that detected it: AST similarity
    - Confidence interval
    """
    engine: str  # Which engine flagged this
    score: float
    confidence: float
    a_start_line: int = 0
    a_end_line: int = 0
    b_start_line: int = 0
    b_end_line: int = 0
    a_snippet: str = ""
    b_snippet: str = ""
    transformation_notes: List[str] = field(default_factory=list)  # e.g., "variable renamed"


@dataclass
class Finding:
    """A finding from one similarity engine."""
    engine: str
    score: float
    confidence: float
    evidence_blocks: List[EvidenceBlock] = field(default_factory=list)
    methodology: str = ""  # How this engine works (for transparency)


# ─────────────────────────────────────────────
# Academic Integrity Case (the core domain object)
# ─────────────────────────────────────────────

class CaseStatus(str, Enum):
    """Case lifecycle status.
    
    NOTE: System NEVER sets VERDICT. It only manages status.
    The professor/committee determines guilt/innocence.
    """
    DETECTED = "detected"                # System flagged similarity
    REFERRED_FOR_REVIEW = "referred"     # Professor notified
    UNDER_REVIEW = "under_review"        # Professor is reviewing
    CLEARED = "cleared"                  # Professor found no issue
    REFER_TO_COMMITTEE = "referred_to_committee"  # Escalated
    APPEALED = "appealed"                # Student is appealing
    
    # NEVER: "guilty", "plagiarism_confirmed", etc.
    # Those are human decisions, not system states.


@dataclass
class AuditEntry:
    """An immutable audit log entry.
    
    Every action must be logged for appeals.
    """
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "system"  # system, professor_name, committee
    action: str = ""       # "flagged", "reviewed", "cleared", "referred"
    details: str = ""


@dataclass
class AcademicIntegrityCase:
    """The core domain object.
    
    This is NOT a "plagiarism detection result." It is a case file
    that may or may not lead to academic integrity proceedings.
    
    The system's job is to produce EVIDENCE.
    A human's job is to make a JUDGMENT.
    These are different things.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # The two submissions being compared
    submission_a: Optional[ImmutableSubmission] = None
    submission_b: Optional[ImmutableSubmission] = None
    
    # Evidence produced by the system
    findings: List[Finding] = field(default_factory=list)
    
    # Overall similarity (convenience field, not a verdict)
    max_similarity_score: float = 0.0
    
    # Case lifecycle
    status: CaseStatus = CaseStatus.DETECTED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Audit trail (immutable append-only)
    audit_log: List[AuditEntry] = field(default_factory=list)
    
    # Human decisions (never set by system)
    reviewed_by: Optional[str] = None      # Professor who reviewed
    committee_decision: Optional[str] = None  # Committee outcome
    
    def add_finding(self, finding: Finding) -> None:
        """Add an evidence finding."""
        self.findings.append(finding)
        if finding.score > self.max_similarity_score:
            self.max_similarity_score = finding.score
            self.audit_log.append(AuditEntry(
                actor="system",
                action="similarity_detected",
                details=f"Engine {finding.engine}: score={finding.score:.3f}",
            ))
    
    def review(self, reviewer: str) -> None:
        """Mark case as reviewed by a professor."""
        self.status = CaseStatus.UNDER_REVIEW
        self.reviewed_by = reviewer
        self.audit_log.append(AuditEntry(actor=reviewer, action="reviewed"))
    
    def clear(self, reviewer: str, rationale: str = "") -> None:
        """Professor clears the student of wrongdoing."""
        self.status = CaseStatus.CLEARED
        self.reviewed_by = reviewer
        self.audit_log.append(AuditEntry(actor=reviewer, action="cleared", details=rationale))
    
    def refer_to_committee(self, referrer: str, rationale: str = "") -> None:
        """Refer case to academic integrity committee."""
        self.status = CaseStatus.REFER_TO_COMMITTEE
        self.audit_log.append(AuditEntry(actor=referrer, action="referred_to_committee", details=rationale))
    
    def appeal(self, student_id: str, rationale: str = "") -> None:
        """Student appeals the decision."""
        self.status = CaseStatus.APPEALED
        self.audit_log.append(AuditEntry(actor=student_id, action="appealed", details=rationale))
    
    def export_committee_file(self) -> Dict[str, Any]:
        """Export a committee-ready case file with redacted PII."""
        return {
            "case_id": self.id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "submission_a": self.submission_a.redact_for_committee().__dict__ if self.submission_a else None,
            "submission_b": self.submission_b.redact_for_committee().__dict__ if self.submission_b else None,
            "findings": [
                {"engine": f.engine, "score": f.score, "confidence": f.confidence}
                for f in self.findings
            ],
            "audit_trail": [
                {"timestamp": e.timestamp.isoformat(), "actor": e.actor, "action": e.action, "details": e.details}
                for e in self.audit_log
            ],
            "reviewed_by": self.reviewed_by,
            "committee_decision": self.committee_decision,
            "note": "PII redacted for blind committee review. Full case file available upon request.",
        }