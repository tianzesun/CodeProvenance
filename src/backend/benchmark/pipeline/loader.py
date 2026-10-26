"""Dataset loader contract.

All dataset loaders must implement the CanonicalDataset interface.
This ensures datasets are pluggable and comparable.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Re-export canonical definitions from schema.py
from src.backend.benchmark.datasets.schema import CanonicalDataset, CodePair


@dataclass
class CodeSample:
    """A single code sample from a dataset."""
    id: str
    code: str
    language: str = "java"
    metadata: dict[str, Any] = field(default_factory=dict)


class DatasetLoader(ABC):
    """Abstract base class for all dataset loaders.
    
    All dataset loaders must implement this interface.
    This ensures datasets are pluggable and comparable.
    
    Usage:
        class MyDatasetLoader(DatasetLoader):
            def name(self) -> str:
                return "my_dataset"
            
            def version(self) -> str:
                return "1.0"
            
            def load(self, path) -> CanonicalDataset:
                ...
    """
    
    @abstractmethod
    def name(self) -> str:
        """Return dataset name."""
    
    @abstractmethod
    def version(self) -> str:
        """Return dataset version."""
    
    @abstractmethod
    def load(self, path: str) -> CanonicalDataset:
        """Load dataset from path.
        
        Args:
            path: Path to dataset.
            
        Returns:
            CanonicalDataset with pairs and/or submissions.
        """
    
    def load_submissions(self, path: str) -> list[CodeSample]:
        """Load individual submissions (optional).
        
        Args:
            path: Path to submissions.
            
        Returns:
            List of CodeSample objects.
        """
        return []
    
    def load_pairs(self, path: str) -> list[CodePair]:
        """Load code pairs with labels.
        
        Args:
            path: Path to pairs.
            
        Returns:
            List of CodePair objects.
        """
        return []
