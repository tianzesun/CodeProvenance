"""Centralized Threshold Configuration - Deterministic evaluation pipeline.

This module provides centralized threshold management.
No thresholds embedded in multiple files.
No runtime tuning logic inside engines.
No implicit defaults.

All thresholds come from this single source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ThresholdConfig:
    """Threshold configuration for similarity decisions.

    Attributes:
        global_threshold: Default threshold for binary decisions.
        type1_threshold: Threshold for Type-1 clones.
        type2_threshold: Threshold for Type-2 clones.
        type3_threshold: Threshold for Type-3 clones.
        type4_threshold: Threshold for Type-4 clones.
    """

    global_threshold: float = 0.7
    type1_threshold: float = 0.9
    type2_threshold: float = 0.8
    type3_threshold: float = 0.6
    type4_threshold: float = 0.5

    def __post_init__(self) -> None:
        """Validate thresholds."""
        for name, value in [
            ("global_threshold", self.global_threshold),
            ("type1_threshold", self.type1_threshold),
            ("type2_threshold", self.type2_threshold),
            ("type3_threshold", self.type3_threshold),
            ("type4_threshold", self.type4_threshold),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")

    def get_threshold(self, clone_type: Optional[int] = None) -> float:
        """Get threshold for a specific clone type.

        Args:
            clone_type: Clone type (0-4) or None for global.

        Returns:
            Threshold value.
        """
        if clone_type is None:
            return self.global_threshold

        thresholds = {
            0: self.global_threshold,
            1: self.type1_threshold,
            2: self.type2_threshold,
            3: self.type3_threshold,
            4: self.type4_threshold,
        }
        return thresholds.get(clone_type, self.global_threshold)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "global_threshold": self.global_threshold,
            "type1_threshold": self.type1_threshold,
            "type2_threshold": self.type2_threshold,
            "type3_threshold": self.type3_threshold,
            "type4_threshold": self.type4_threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ThresholdConfig:
        """Create from dictionary."""
        return cls(
            global_threshold=data.get("global_threshold", 0.7),
            type1_threshold=data.get("type1_threshold", 0.9),
            type2_threshold=data.get("type2_threshold", 0.8),
            type3_threshold=data.get("type3_threshold", 0.6),
            type4_threshold=data.get("type4_threshold", 0.5),
        )


@dataclass(frozen=True)
class CalibrationConfig:
    """Calibration configuration.

    Attributes:
        method: Calibration method (none, isotonic, sigmoid).
        threshold_strategy: Strategy for threshold optimization.
    """

    method: str = "none"
    threshold_strategy: str = "f1_max"

    def __post_init__(self) -> None:
        """Validate calibration config."""
        valid_methods = {"none", "isotonic", "sigmoid"}
        if self.method not in valid_methods:
            raise ValueError(f"method must be one of {valid_methods}")

        valid_strategies = {"f1_max", "precision_fixed", "recall_fixed"}
        if self.threshold_strategy not in valid_strategies:
            raise ValueError(f"threshold_strategy must be one of {valid_strategies}")


@dataclass
class PipelineThresholdConfig:
    """Complete threshold configuration for pipeline.

    This is the SINGLE SOURCE OF TRUTH for all thresholds.

    Attributes:
        thresholds: Threshold configuration.
        calibration: Calibration configuration.
        version: Configuration version.
    """

    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "thresholds": self.thresholds.to_dict(),
            "calibration": {
                "method": self.calibration.method,
                "threshold_strategy": self.calibration.threshold_strategy,
            },
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PipelineThresholdConfig:
        """Create from dictionary."""
        return cls(
            thresholds=ThresholdConfig.from_dict(data.get("thresholds", {})),
            calibration=CalibrationConfig(
                method=data.get("calibration", {}).get("method", "none"),
                threshold_strategy=data.get("calibration", {}).get(
                    "threshold_strategy", "f1_max"
                ),
            ),
            version=data.get("version", "1.0"),
        )

    def save(self, path: Path) -> None:
        """Save configuration to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> PipelineThresholdConfig:
        """Load configuration from file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


def compute_decision(
    score: float,
    threshold: Optional[float] = None,
) -> bool:
    """Compute binary decision from score and threshold.

    This is the DETERMINISTIC decision function.
    No exceptions. No implicit logic.

    Args:
        score: Similarity score in [0, 1].
        threshold: Decision threshold. If None, uses active global threshold.

    Returns:
        True if score >= threshold, False otherwise.
    """
    if threshold is None:
        from src.backend.evaluation.threshold_analysis import global_threshold_override

        threshold = global_threshold_override()

    return score >= threshold


# Default configuration
DEFAULT_CONFIG = PipelineThresholdConfig()
