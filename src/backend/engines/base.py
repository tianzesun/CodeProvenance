"""Base Interfaces - strict plugin contracts for engines."""

from abc import ABC, abstractmethod
from typing import Any


class BaseSimilarityEngine(ABC):
    """All similarity engines MUST implement this."""

    @abstractmethod
    def compute(self, code_a: dict[str, Any], code_b: dict[str, Any]) -> float:
        """Compute similarity between two code samples."""


class BaseFeatureExtractor(ABC):
    """All feature extractors MUST implement this."""

    @abstractmethod
    def extract(self, code_a: str, code_b: str) -> dict[str, float]:
        """Extract features from two code samples."""
