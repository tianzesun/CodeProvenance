"""Base Interfaces - strict plugin contracts for engines."""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseSimilarityEngine(ABC):
    """All similarity engines MUST implement this."""
    @abstractmethod
    def compute(self, code_a: Dict[str, Any], code_b: Dict[str, Any]) -> float:
        """Compute similarity between two code samples."""
        pass

class BaseFeatureExtractor(ABC):
    """All feature extractors MUST implement this."""
    @abstractmethod
    def extract(self, code_a: str, code_b: str) -> Dict[str, float]:
        """Extract features from two code samples."""
        pass
