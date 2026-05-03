from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .schemas import Sample


class Loader(ABC):
    """Base interface for loading raw dataset files."""

    @abstractmethod
    def load(self, path: str) -> List[Dict[str, Any]]:
        """Load raw dataset rows from disk."""
        pass


class Normalizer(ABC):
    """Base interface for normalizing raw rows into unified Sample format."""

    @abstractmethod
    def normalize(self, raw_rows: List[Dict[str, Any]]) -> List[Sample]:
        """Convert raw dataset rows to standardized Sample objects."""
        pass


class Runner(ABC):
    """Base interface for running models/engines against benchmark samples."""

    @abstractmethod
    def predict(self, samples: List[Sample], **kwargs: Any) -> List[Dict[str, Any]]:
        """Run predictions against sample inputs."""
        pass


class Evaluator(ABC):
    """Base interface for evaluating predictions against ground truth."""

    @abstractmethod
    def evaluate(self, samples: List[Sample], predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate evaluation metrics."""
        pass
