"""
Benchmark validation protocol.

Formal execution protocol for validating plagiarism detection tools against
standardized test cases, with controlled splits, baseline comparisons,
and pass/fail validation criteria.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum
import uuid
import datetime


class ValidationStatus(Enum):
    """Status of validation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PASSED = "passed"


@dataclass
class ValidationProtocol:
    """
    Defines the complete execution protocol for a benchmark validation run.
    All parameters required for reproducible execution are captured here.
    """
    protocol_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str = ""
    split_config: Dict[str, Any] = field(default_factory=dict)
    baseline_tools: List[str] = field(default_factory=list)
    candidate_tools: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    pass_thresholds: Dict[str, float] = field(default_factory=dict)
    timeout_seconds: int = 3600
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate protocol configuration is complete and valid."""
        if not self.dataset_id:
            return False
        if not self.candidate_tools:
            return False
        if not self.metrics:
            return False
        return True


@dataclass
class ValidationResult:
    """Result of a complete benchmark validation run."""
    protocol: ValidationProtocol
    status: ValidationStatus
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    tool_results: Dict[str, Any] = field(default_factory=dict)
    comparison_summary: Dict[str, Any] = field(default_factory=dict)
    pass_fail_outcomes: Dict[str, bool] = field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def all_passed(self) -> bool:
        """Return True if all pass/fail checks passed."""
        return all(self.pass_fail_outcomes.values())
