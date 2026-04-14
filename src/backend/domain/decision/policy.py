"""Policy Configuration - Per-institution policy config for academic integrity.

Thresholds, decision rules, and review workflows are configured via YAML,
not hardcoded. Different institutions have different academic integrity standards.

Compliance notes:
- FERPA (US) / PIPEDA (Canada) require student data protection
- Evidence documents must be reproducible for appeals
- All threshold decisions must be logged with rationale
"""
import dataclasses
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CaseStatus(str, Enum):
    """Status of an academic integrity case.
    
    IMPORTANT: System NEVER sets status to GUILTY.
    It only surfaces findings and refers for human review.
    The professor/committee makes the actual decision.
    """
    PENDING_REVIEW = "pending_review"          # Needs professor review
    REQUIRES_REVIEW = "requires_review"        # Flagged for attention
    UNDER_REVIEW = "under_review"              # Professor is reviewing
    CLEARED = "cleared"                        # Professor cleared student
    REFER_TO_COMMITTEE = "referred_to_committee"  # Referred to academic integrity committee
    APPEALED = "appealed"                      # Student appealed decision


@dataclass
class PolicyConfig:
    """Institution-specific policy configuration.
    
    This is the single source of truth for academic integrity policy.
    Thresholds are set by the institution, not by developers.
    
    FERPA/PIPEDA compliance:
    - pII_masking_enabled: Required for US/Canada compliance
    - data_retention_days: Evidence retention period
    - audit_enabled: All actions must be logged for appeals
    """
    institution_name: str = ""
    
    # === Threshold configuration ===
    # These values should be set by academic integrity policy committee
    identical_threshold: float = 0.85          # >85% = essentially identical
    high_similarity_threshold: float = 0.70    # >70% = high similarity
    medium_similarity_threshold: float = 0.50  # >50% = moderate similarity
    low_similarity_threshold: float = 0.30     # >30% = possible shared code
    
    # === Decision rules ===
    auto_refer_threshold: float = 0.90         # Auto-flag for committee review
    require_human_review: bool = True          # NEVER auto-decide guilt
    
    # === Privacy/retention (FERPA/PIPEDA) ===
    data_retention_days: int = 365             # Keep evidence for appeals
    pII_masking_enabled: bool = True           # Mask student names in PDFs
    anonymize_for_committee: bool = True       # Blind review for committee
    
    # === Workflow timing ===
    review_deadline_days: int = 14             # Professor must review within 14 days
    appeal_period_days: int = 30               # Student has 30 days to appeal
    evidence_export_format: str = "pdf"        # Committee-ready format


def save_policy(config: PolicyConfig, path: Path) -> None:
    """Save policy to YAML file for audit trail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    with open(path, 'w') as f:
        yaml.dump(dataclasses.asdict(config), f, default_flow_style=False)


def load_policy(path: Path) -> PolicyConfig:
    """Load policy from YAML file. Returns default if file doesn't exist."""
    import yaml
    if path.exists():
        with open(path) as f:
            try:
                data = yaml.safe_load(f)
                if data:
                    return PolicyConfig(**{
                        k: v for k, v in data.items()
                        if k in PolicyConfig.__dataclass_fields__
                    })
            except Exception:
                pass
    return PolicyConfig()


def get_default_policy() -> PolicyConfig:
    """Return default policy with safe defaults."""
    return PolicyConfig(
        institution_name="Academic Integrity System",
        identical_threshold=0.85,
        high_similarity_threshold=0.70,
        medium_similarity_threshold=0.50,
        low_similarity_threshold=0.30,
        auto_refer_threshold=0.90,
        require_human_review=True,
        data_retention_days=365,
        pII_masking_enabled=True,
        anonymize_for_committee=True,
        review_deadline_days=14,
        appeal_period_days=30,
        evidence_export_format="pdf",
    )