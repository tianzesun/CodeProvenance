"""Domain Layer - Academic Integrity Case Management.

The system produces EVIDENCE. Humans make JUDGMENTS.
These are fundamentally different responsibilities.
"""

from src.backend.domain.decision.policy import PolicyConfig, get_default_policy
from src.backend.domain.models import (
    AcademicIntegrityCase,
    AuditEntry,
    CaseStatus,
    EvidenceBlock,
    Finding,
    ImmutableSubmission,
)

__all__ = [
    # Case management
    "AcademicIntegrityCase",
    "AuditEntry",
    "CaseStatus",
    "EvidenceBlock",
    "Finding",
    "ImmutableSubmission",
    # Policy
    "PolicyConfig",
    "get_default_policy",
]
