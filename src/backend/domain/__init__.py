"""Domain Layer - Academic Integrity Case Management.

The system produces EVIDENCE. Humans make JUDGMENTS.
These are fundamentally different responsibilities.
"""
from src.backend.domain.models import (
    ImmutableSubmission, EvidenceBlock, Finding,
    AcademicIntegrityCase, CaseStatus, AuditEntry
)
from src.backend.domain.decision.policy import PolicyConfig, get_default_policy

__all__ = [
    # Case management
    'AcademicIntegrityCase', 'CaseStatus',
    'ImmutableSubmission', 'EvidenceBlock', 'Finding', 'AuditEntry',
    # Policy
    'PolicyConfig', 'get_default_policy',
]