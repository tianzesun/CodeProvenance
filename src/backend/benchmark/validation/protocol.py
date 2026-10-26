"""
Benchmark validation protocol.

Formal execution protocol for validating plagiarism detection tools against
standardized test cases, with controlled splits, baseline comparisons,
and pass/fail validation criteria.
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    split_config: dict[str, Any] = field(default_factory=dict)
    baseline_tools: list[str] = field(default_factory=list)
    candidate_tools: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    pass_thresholds: dict[str, float] = field(default_factory=dict)
    timeout_seconds: int = 3600
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

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
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    tool_results: dict[str, Any] = field(default_factory=dict)
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    pass_fail_outcomes: dict[str, bool] = field(default_factory=dict)
    error_message: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def all_passed(self) -> bool:
        """Return True if all pass/fail checks passed."""
        return all(self.pass_fail_outcomes.values())
